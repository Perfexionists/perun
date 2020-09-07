"""SystemTap script generator module. Assembles the SystemTap script according to the specified
rules such as function or USDT locations and sampling.
"""


from perun.collect.trace.watchdog import WATCH_DOG
from perun.collect.trace.values import RecordType


# names of the global arrays used throughout the script
ARRAY_PROBE_ID = 'probe_id'
ARRAY_SAMPLE_THRESHOLD = 'sampling_threshold'
ARRAY_SAMPLE_COUNTER = 'sampling_counter'
ARRAY_SAMPLE_FLAG = 'sampling_flag'
ARRAY_RECURSION_DEPTH = 'recursion_depth'
ARRAY_RECURSION_SAMPLE_HIT = 'recursion_sample_hit'

# Template of the global arrays declaration
ARRAYS_TEMPLATE = """
{id_array}
{sampling_arrays}
{recursion_arrays}
"""

# Template of the sampling global arrays declaration
ARRAYS_SAMPLING_TEMPLATE = """
global {sampling_thr}{{size}}
global {sampling_cnt}{{size}}
global {sampling_flag}{{size}}
""".format(
    sampling_thr=ARRAY_SAMPLE_THRESHOLD,
    sampling_cnt=ARRAY_SAMPLE_COUNTER,
    sampling_flag=ARRAY_SAMPLE_FLAG
)

# Template of the recursion sampling global arrays declaration
ARRAYS_RECURSION_TEMPLATE = """
global {recursion_depth}{{size}}
global {recursion_hit}{{size}}
""".format(
    recursion_depth=ARRAY_RECURSION_DEPTH,
    recursion_hit=ARRAY_RECURSION_SAMPLE_HIT,
)

# Template of a function event
FUNC_EVENT_TEMPLATE = 'process("{binary}").function("{name}"){{suffix}}'
# Template of an USDT event
USDT_EVENT_TEMPLATE = 'process("{binary}").mark("{loc}")?'
# Template of a record creation within a probe handler
HANDLER_TEMPLATE = \
    'printf("{type} %d %d {id_type}\\n", tid(), read_stopwatch_ns("timestamp"), {id_get})'
# Template of a probe event declaration and handler definition
PROBE_TEMPLATE = """
probe {probe_events}
{{
    pname = ppfunc()
    {probe_handler}
}}
"""

# Template of a sampled entry probe handler that is imprecise for sampled recursive functions
ENTRY_APPROX_SAMPLE_TEMPLATE = """
    {sampling_cnt}[pname] ++
    if ({sampling_cnt}[pname] == {sampling_thr}[pname]) {{{{
        {sampling_flag}[pname] ++
        {sampling_cnt}[pname] = 0
        {{probe_handler}}
    }}}}
""".format(
    sampling_cnt=ARRAY_SAMPLE_COUNTER,
    sampling_thr=ARRAY_SAMPLE_THRESHOLD,
    sampling_flag=ARRAY_SAMPLE_FLAG
)

# Template of a sampled exit probe handler that is imprecise for sampled recursive functions
EXIT_APPROX_SAMPLE_TEMPLATE = """
    if ({sampling_flag}[pname] > 0) {{{{
        {{probe_handler}}
        {sampling_flag}[pname] --
    }}}}
""".format(
    sampling_flag=ARRAY_SAMPLE_FLAG
)

# Template of a sampled entry probe handler that can precisely measure even sampled recursive
# functions - however, it is sensitive to call nesting errors (e.g., omitted retprobe calls etc.)
ENTRY_PRECISE_SAMPLE_TEMPLATE = """
    {sampling_cnt}[pname] ++
    {recursion_depth}[pname] ++
    if ({sampling_cnt}[pname] == {sampling_thr}[pname]) {{{{
        {recursion_hit}[pname, {recursion_depth}[pname]] = 1
        {sampling_cnt}[pname] = 0
        {{probe_handler}}
    }}}}
""".format(
    sampling_cnt=ARRAY_SAMPLE_COUNTER,
    recursion_depth=ARRAY_RECURSION_DEPTH,
    sampling_thr=ARRAY_SAMPLE_THRESHOLD,
    recursion_hit=ARRAY_RECURSION_SAMPLE_HIT
)

# Template of a sampled exit probe handler that can precisely measure even sampled recursive
# functions - however, it is sensitive to call nesting errors (e.g., omitted retprobe calls etc.
EXIT_PRECISE_SAMPLE_TEMPLATE = """
    if ([pname, {recursion_depth}[pname]] in {recursion_hit}) {{{{
        {{probe_handler}}
        delete {recursion_hit}[pname, {recursion_depth}[pname]]
    }}}}
    {recursion_depth}[pname] -- 
""".format(
    recursion_depth=ARRAY_RECURSION_DEPTH,
    recursion_hit=ARRAY_RECURSION_SAMPLE_HIT
)


# TODO: solve func name / USDT name collision in the arrays
# TODO: solve precise / approx sampling switching
# TODO: solve array size definition and unused warnings
def assemble_system_tap_script(script_file, config, probes, **_):
    """Assembles SystemTap script according to the configuration and probes specification.

    :param str script_file: path to the script file, that should be generated
    :param Configuration config: the configuration parameters
    :param Probes probes: the probes specification
    """
    WATCH_DOG.info("Attempting to assembly the SystemTap script '{}'".format(script_file))

    # Add unique probe and sampling ID to the probes
    probes.add_probe_ids()

    # Open the script file in write mode
    with open(script_file, 'w') as script_handle:
        # Declare and init arrays, create the begin probe
        _add_script_init(script_handle, config.binary, probes, config.verbose_trace)
        # Create the timing probes for functions and USDT probes
        _add_program_probes(script_handle, probes, config.binary, config.verbose_trace)
        _add_end_probe(script_handle, config.binary, config.verbose_trace)

    # Success
    WATCH_DOG.info("SystemTap script successfully assembled")
    WATCH_DOG.log_probes(len(probes.func), len(probes.usdt), script_file)


def _add_script_init(handle, binary, probes, verbose_trace):
    """ Add the process begin probe, sampling array declaration and initialization.

    :param TextIO handle: the script file handle
    :param str binary: the name of the binary file
    :param Probes probes: the probes specification
    """
    script_init = """
{array_declaration}

probe process("{binary}").begin {{
{id_init}
{sampling_init}
    start_stopwatch("timestamp");
    {sentinel}
}}
""".format(
        array_declaration=_build_array_declaration(probes, verbose_trace),
        id_init=_build_id_init(probes, verbose_trace),
        sampling_init=_build_sampling_init(probes),
        binary=binary,
        sentinel=_build_probe_handler(RecordType.SentinelBegin, binary, verbose_trace)
    )
    handle.write(script_init)


def _add_end_probe(handle, binary, verbose_trace):
    """Adds marker to the collection output indicating the end of collection. This is needed to
    determine that the output file is fully written and can be further analyzed and processed.

    :param TextIO handle: the script file handle
    :param str binary: the name of the binary file
    """
    end_probe = """
probe process("{binary}").end {{
    {sentinel}
    stop_stopwatch("timestamp")
    delete_stopwatch("timestamp")
}}
""".format(
        binary=binary,
        sentinel=_build_probe_handler(RecordType.SentinelEnd, binary, verbose_trace)
    )
    handle.write(end_probe)


def _add_program_probes(handle, probes, binary, verbose_trace):
    """ Add the probe definitions to the script.

    :param TextIO handle: the script file handle
    :param Probes probes: the Probes configuration
    :param str binary: the path to the profiled binary
    :param bool verbose_trace: the verbosity level of the data output
    """
    # Obtain the distinct set of function and usdt probes
    sampled_func, nonsampled_func = probes.get_partitioned_func_probes()
    sampled_usdt, nonsampled_usdt, single_usdt = probes.get_partitioned_usdt_probes()
    # Pre-build events and handlers based on the probe sets
    prebuilt = {
        'e': {
            'sampled_func': _build_func_events(sampled_func, binary),
            'sampled_usdt': _build_usdt_events(sampled_usdt, binary),
            'sampled_usdt_exit': _build_usdt_events(sampled_usdt, binary, 'pair'),
            'nonsampled_func': _build_func_events(nonsampled_func, binary),
            'nonsampled_usdt': _build_usdt_events(nonsampled_usdt, binary),
            'nonsampled_usdt_exit': _build_usdt_events(nonsampled_usdt, binary, 'pair'),
            'single_usdt': _build_usdt_events(single_usdt, binary)
        },
        'h': {
            'func_begin': _build_probe_handler(RecordType.FuncBegin, binary, verbose_trace),
            'func_exit': _build_probe_handler(RecordType.FuncEnd, binary, verbose_trace),
            'usdt_begin': _build_probe_handler(RecordType.USDTBegin, binary, verbose_trace),
            'usdt_exit': _build_probe_handler(RecordType.USDTEnd, binary, verbose_trace),
            'usdt_single': _build_probe_handler(RecordType.USDTSingle, binary, verbose_trace)
        }
    }
    # Create pairs of events-handlers to add to the script
    # Nonsampled: function entry, function exit, USDT entry, USDT exit
    # Sampled: function entry, function exit, USDT entry, USDT exit
    # Single: USDT single
    specification = [
        (prebuilt['e']['nonsampled_func'].format(suffix='.call?'), prebuilt['h']['func_begin']),
        (prebuilt['e']['nonsampled_func'].format(suffix='.return?'), prebuilt['h']['func_exit']),
        (prebuilt['e']['nonsampled_usdt'], prebuilt['h']['usdt_begin']),
        (prebuilt['e']['nonsampled_usdt_exit'], prebuilt['h']['usdt_exit']),
        (prebuilt['e']['single_usdt'], prebuilt['h']['usdt_single']),
        (prebuilt['e']['sampled_func'].format(suffix='.call?'),
         ENTRY_APPROX_SAMPLE_TEMPLATE.format(probe_handler=prebuilt['h']['func_begin'])),
        (prebuilt['e']['sampled_func'].format(suffix='.return?'),
         EXIT_APPROX_SAMPLE_TEMPLATE.format(probe_handler=prebuilt['h']['func_exit'])),
        (prebuilt['e']['sampled_usdt'],
         ENTRY_APPROX_SAMPLE_TEMPLATE.format(probe_handler=prebuilt['h']['usdt_begin'])),
        (prebuilt['e']['sampled_usdt_exit'],
         EXIT_APPROX_SAMPLE_TEMPLATE.format(probe_handler=prebuilt['h']['usdt_exit'])),
    ]

    for spec_event, spec_handler in specification:
        # Add the new events + handler only if there are some associated events
        if spec_event:
            probe = PROBE_TEMPLATE.format(probe_events=spec_event, probe_handler=spec_handler)
            handle.write(probe)


def _build_array_declaration(probes, verbose_trace):
    """ Build only the array declarations necessary for the given script, i.e.,
    create / omit probe ID mapping array based on the verbosity
    create / omit sampling arrays based on the presence / absence of sampled probes, etc.

    :param Probes probes: the Probes object
    :param bool verbose_trace: the verbosity level of the output

    :return str: the built array declaration string
    """
    # Currently three types of arrays
    id_array = '# ID array omitted'
    sampling_arrays = '# Sampling arrays omitted'
    recursion_arrays = '# Recursion arrays omitted'
    # Verbose mode controls the ID array
    if not verbose_trace:
        id_array = 'global {}[{}]'.format(ARRAY_PROBE_ID, probes.total_probes_len())
    # Sampled probes control the presence of sampling arrays
    if probes.sampled_probes_len() > 0:
        array_size = '[{}]'.format(probes.sampled_probes_len())
        sampling_arrays = ARRAYS_SAMPLING_TEMPLATE.format(size=array_size)
    # TODO: Recursion sampling switch on / off
    return ARRAYS_TEMPLATE.format(
        id_array=id_array,
        sampling_arrays=sampling_arrays,
        recursion_arrays=recursion_arrays
    )


def _build_id_init(probes, verbose_trace):
    """ Build the probe name -> ID mapping initialization code

    :param Probes probes: the Probes object
    :param bool verbose_trace: the verbosity level of the output

    :return str: the built ID array initialization code
    """
    # The name -> ID mapping is not used in verbose mode
    if verbose_trace:
        return '    # Probe name -> Probe ID is not used in verbose mode\n'
    # For each probe, map the name to the probe ID for compact output
    init_string = '    # Probe name -> Probe ID\n'
    for probe_set in [probes.get_func_probes(), probes.get_usdt_probes()]:
        for probe in probe_set:
            init_string += '    {}["{}"] = {}\n'.format(ARRAY_PROBE_ID, probe['name'], probe['id'])
    return init_string


def _build_sampling_init(probes):
    """ Build the sampling arrays initialization code

    :param Probes probes: the Probes object

    :return str: the built sampling array initialization code
    """
    # The threshold array contains the sampling values for each function
    # When the threshold is reached, the probe generates a data record
    threshold_string = '    # Probe name -> Probe sampling threshold\n'
    # The counter array keeps track of the function calls before the threshold is reached
    counter_string = '    # Probe name -> Probe trigger counter\n'
    # Generate the initialization code for both the function and USDT sampled probes
    for probe_set in [probes.get_sampled_func_probes(), probes.get_sampled_usdt_probes()]:
        for probe in probe_set:
            threshold_string += '    {}["{}"] = {}\n'.format(
                ARRAY_SAMPLE_THRESHOLD, probe['name'], probe['sample']
            )
            counter_string += '    {}["{}"] = {}\n'.format(
                ARRAY_SAMPLE_COUNTER, probe['name'], probe['sample'] - 1
            )
    return threshold_string + counter_string


def _build_probe_handler(probe_type, binary, verbose_trace):
    """ Build the probe innermost body.

    :param RecordType probe_type: the probe type
    :param str binary: the path to the profiled binary
    :param bool verbose_trace: the verbosity level of the data output

    :return str: the probe handler code
    """
    # Set how the probe will be identified in the output and how we obtain the identification
    # Based on the type of probe and trace verbosity
    if probe_type in (RecordType.SentinelBegin, RecordType.SentinelEnd):
        _id_type, _id_get = _id_type_value(('-1', '"{}"'.format(binary)), verbose_trace)
    else:
        _id_type, _id_get = _id_type_value(
            ('{}[pname]'.format(ARRAY_PROBE_ID), 'pname'), verbose_trace
        )
    # Format the template for the required probe type
    return HANDLER_TEMPLATE.format(type=int(probe_type), id_type=_id_type, id_get=_id_get)


def _build_func_events(probe_iter, binary):
    """ Build function probe events code, which is basically a list of events that share some
    common handler.

    :param iter probe_iter: iterator of probe configurations
    :param str binary: path to the profiled binary

    :return str: the built probe events code
    """
    return ',\n      '.join(
        FUNC_EVENT_TEMPLATE.format(binary=binary, name=prb['name']) for prb in probe_iter
    )


def _build_usdt_events(probe_iter, binary, probe_id='name'):
    """ Build USDT probe events code, which is basically a list of events that share some
    common handler.

    :param iter probe_iter: iterator of probe configurations
    :param str binary: path to the profiled binary

    :return str: the built probe events code
    """
    return ',\n      '.join(
        USDT_EVENT_TEMPLATE.format(binary=binary, name=prb[probe_id]) for prb in probe_iter
    )


def _id_type_value(value_set, verbose_trace):
    """ Select the type and value of printed data based on the verbosity level of the output.

    :param tuple value_set: a set of nonverbose / verbose data output
    :param bool verbose_trace: the verbosity level of the output

    :return tuple (str, str): the 'type' and 'value' objects for the print statement
    """
    if verbose_trace:
        return '%s', value_set[1]
    else:
        return '%d', value_set[0]
