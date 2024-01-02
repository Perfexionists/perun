"""SystemTap script generator module. Assembles the SystemTap script according to the specified
rules such as function or USDT locations and sampling.
"""


from perun.collect.trace.watchdog import WATCH_DOG
from perun.collect.trace.values import RecordType
from perun.collect.trace.optimizations.structs import Optimizations, Parameters


# Names of the global arrays used throughout the script
ARRAY_PROBE_ID = "probe_id"
ARRAY_SAMPLE_THRESHOLD = "sampling_threshold"
ARRAY_SAMPLE_COUNTER = "sampling_counter"
ARRAY_SAMPLE_FLAG = "sampling_flag"
ARRAY_RECURSION_DEPTH = "recursion_depth"
ARRAY_RECURSION_SAMPLE_HIT = "recursion_sample_hit"

# Names of other used global variables
STOPWATCH_ON = "stopwatch_on"
STOPWATCH_NAME = "timestamp"
TIMED_SWITCH = "timed_switch"

# Default MAP size
MAX_MAP_ENTRIES = 2048

# Template of the global arrays declaration
ARRAYS_TEMPLATE = """
{id_array}
{sampling_arrays}
{recursion_arrays}
"""

# Template of the sampling global arrays declaration
ARRAYS_SAMPLING_TEMPLATE = """
global {sampling_thr}[{{size}}]
global {sampling_cnt}[{{max_size}}]
global {sampling_flag}[{{max_size}}]
""".format(
    sampling_thr=ARRAY_SAMPLE_THRESHOLD,
    sampling_cnt=ARRAY_SAMPLE_COUNTER,
    sampling_flag=ARRAY_SAMPLE_FLAG,
)

# Template of the recursion sampling global arrays declaration
ARRAYS_RECURSION_TEMPLATE = """
global {recursion_depth}
global {recursion_hit}
""".format(
    recursion_depth=ARRAY_RECURSION_DEPTH,
    recursion_hit=ARRAY_RECURSION_SAMPLE_HIT,
)

# Template of a function event
FUNC_EVENT_TEMPLATE = 'process("{binary}").function("{name}"){{suffix}}{timed_switch}'
# Template of an USDT event
USDT_EVENT_TEMPLATE = 'process("{binary}").mark("{loc}")?'
# Template of a process begin / end handler
PROCESS_HANDLER_TEMPLATE = (
    'printf("{type} %d %d %d %d;%s\\n", '
    'tid(), pid(), ppid(), read_stopwatch_ns("{timestamp}"), execname())'
)
THREAD_HANDLER_TEMPLATE = (
    'printf("{type} %d %d %d;%s\\n", tid(), pid(), read_stopwatch_ns("{timestamp}"), execname())'
)
# Template of a record creation within a probe handler
HANDLER_TEMPLATE = (
    'printf("{type} %d %d;{id_type}\\n", tid, read_stopwatch_ns("{timestamp}"), {id_get})'
)
# Template of a probe event declaration and handler definition
PROBE_TEMPLATE = """
probe {probe_events}
{{
    pname = ppfunc()
    tid = tid()
    {probe_handler}
}}
"""

# Template of a sampled entry probe handler that is imprecise for sampled recursive functions
ENTRY_APPROX_SAMPLE_TEMPLATE = """
    counter = {sampling_cnt}[tid, pname]
    if (counter == 0 || counter == {sampling_thr}[pname]) {{{{
        {sampling_cnt}[tid, pname] = 0
        {sampling_flag}[tid, pname] ++
        {{probe_handler}}
    }}}}
    {sampling_cnt}[tid, pname] ++
""".format(
    sampling_cnt=ARRAY_SAMPLE_COUNTER,
    sampling_thr=ARRAY_SAMPLE_THRESHOLD,
    sampling_flag=ARRAY_SAMPLE_FLAG,
)

# Template of a sampled exit probe handler that is imprecise for sampled recursive functions
EXIT_APPROX_SAMPLE_TEMPLATE = """
    if ({sampling_flag}[tid, pname] > 0) {{{{
        {{probe_handler}}
        {sampling_flag}[tid, pname] --
    }}}}
""".format(
    sampling_flag=ARRAY_SAMPLE_FLAG
)

# Template of a sampled entry probe handler that can precisely measure even sampled recursive
# functions - however, it is sensitive to call nesting errors (e.g., omitted retprobe calls etc.)
ENTRY_PRECISE_SAMPLE_TEMPLATE = """
    {sampling_cnt}[tid, pname] ++
    {recursion_depth}[tid, pname] ++
    if ({sampling_cnt}[tid, pname] == {sampling_thr}[pname]) {{{{
        {recursion_hit}[tid, pname, {recursion_depth}[tid, pname]] = 1
        {sampling_cnt}[tid, pname] = 0
        {{probe_handler}}
    }}}}
""".format(
    sampling_cnt=ARRAY_SAMPLE_COUNTER,
    recursion_depth=ARRAY_RECURSION_DEPTH,
    sampling_thr=ARRAY_SAMPLE_THRESHOLD,
    recursion_hit=ARRAY_RECURSION_SAMPLE_HIT,
)

# Template of a sampled exit probe handler that can precisely measure even sampled recursive
# functions - however, it is sensitive to call nesting errors (e.g., omitted retprobe calls etc.
EXIT_PRECISE_SAMPLE_TEMPLATE = """
    if ([tid, pname, {recursion_depth}[tid, pname]] in {recursion_hit}) {{{{
        {{probe_handler}}
        delete {recursion_hit}[tid, pname, {recursion_depth}[tid, pname]]
    }}}}
    {recursion_depth}[tid, pname] -- 
""".format(
    recursion_depth=ARRAY_RECURSION_DEPTH, recursion_hit=ARRAY_RECURSION_SAMPLE_HIT
)


# TODO: solve func name / USDT name collision in the arrays
# TODO: solve precise / approx sampling switching
def assemble_system_tap_script(script_file, config, probes, **_):
    """Assembles SystemTap script according to the configuration and probes specification.

    :param str script_file: path to the script file, that should be generated
    :param Configuration config: the configuration parameters
    :param Probes probes: the probes specification
    """
    WATCH_DOG.info(f"Attempting to assembly the SystemTap script '{script_file}'")

    # Add unique probe and sampling ID to the probes
    probes.add_probe_ids()

    # Open the script file in write mode
    with open(script_file, "w") as script_handle:
        # Obtain configuration for the timed sampling optimization
        timed_sampling = Optimizations.TIMED_SAMPLING.value in config.run_optimizations
        # Declare and init arrays, create the begin / end probes
        _add_script_init(script_handle, config, probes, timed_sampling)
        # Add the thread begin / end probes
        _add_thread_probes(script_handle, config.binary, bool(probes.sampled_probes_len()))
        # Add the timed sampling timer probe if needed
        if timed_sampling:
            sampling_freq = config.run_optimization_parameters[Parameters.TIMEDSAMPLE_FREQ.value]
            _add_timer_probe(script_handle, sampling_freq)
        # Create the timing probes for functions and USDT probes
        _add_program_probes(script_handle, probes, config.verbose_trace, timed_sampling)

    # Success
    WATCH_DOG.info("SystemTap script successfully assembled")
    WATCH_DOG.log_probes(len(probes.func), len(probes.usdt), script_file)


def _add_script_init(handle, config, probes, timed_sampling):
    """Declare and initialize ID, sampling and recursion arrays (certain arrays may be omitted
    when e.g., sampling is turned off), necessary global variables, as well as add the process
    begin and end probe.

    :param TextIO handle: the script file handle
    :param Configuration config: the configuration parameters
    :param Probes probes: the probes specification
    :param bool timed_sampling: specifies whether Timed Sampling is on or off
    """
    script_init = """
{array_declaration}
{timed_sampling}
global {stopwatch} = 0

probe process("{binary}").begin {{
{id_init}
{sampling_init}
    if (!{stopwatch}) {{
        {stopwatch} = 1
        start_stopwatch("{timestamp}")
    }}
    {begin_handler}
}}

probe process("{binary}").end
{{
    {end_handler}
}}

""".format(
        array_declaration=_build_array_declaration(
            probes, config.verbose_trace, config.maximum_threads
        ),
        stopwatch=STOPWATCH_ON,
        id_init=_build_id_init(probes, config.verbose_trace),
        sampling_init=_build_sampling_init(probes),
        binary=config.binary,
        timestamp=STOPWATCH_NAME,
        begin_handler=PROCESS_HANDLER_TEMPLATE.format(
            type=int(RecordType.PROCESS_BEGIN), timestamp=STOPWATCH_NAME
        ),
        end_handler=PROCESS_HANDLER_TEMPLATE.format(
            type=int(RecordType.PROCESS_END), timestamp=STOPWATCH_NAME
        ),
        timed_sampling=(
            f"global {TIMED_SWITCH} = 1" if timed_sampling else "# Timed Sampling omitted"
        ),
    )
    handle.write(script_init)


def _add_thread_probes(handle, binary, sampling_on):
    """Add thread begin and end probes.

    :param TextIO handle: the script file handle
    :param str binary: the name of the binary file
    :param bool sampling_on: specifies whether per-function sampling is on
    """
    end_probe = """
probe process("{binary}").thread.begin {{
    {begin_handler}
}}
    
probe process("{binary}").thread.end {{
    {end_handler}
    {sampling_cleanup}
}}
""".format(
        binary=binary,
        begin_handler=THREAD_HANDLER_TEMPLATE.format(
            type=int(RecordType.THREAD_BEGIN), timestamp=STOPWATCH_NAME
        ),
        end_handler=THREAD_HANDLER_TEMPLATE.format(
            type=int(RecordType.THREAD_END), timestamp=STOPWATCH_NAME
        ),
        sampling_cleanup=(
            "delete {sampling_cnt}[tid(), *]\n    delete {sampling_flag}[tid(), *]".format(
                sampling_cnt=ARRAY_SAMPLE_COUNTER, sampling_flag=ARRAY_SAMPLE_FLAG
            )
            if sampling_on
            else "# Sampling cleanup omitted"
        ),
    )
    handle.write(end_probe)


# TODO: frequency to ns timer
def _add_timer_probe(handle, sampling_frequency):
    """Add a probe for timed event that enables / disables function probes.

    :param TextIO handle: the script file handle
    :param int sampling_frequency: timer (ns) value of the timer probe firing
    """
    # Create the sampling timer
    timer_probe = """
probe timer.ns({freq}) if ({stopwatch}) {{
    {switch} = !{switch}
}}
""".format(
        freq=sampling_frequency, stopwatch=STOPWATCH_ON, switch=TIMED_SWITCH
    )
    handle.write(timer_probe)


def _add_program_probes(handle, probes, verbose_trace, timed_sampling):
    """Add function and USDT probe definitions to the script.

    :param TextIO handle: the script file handle
    :param Probes probes: the Probes configuration
    :param bool verbose_trace: the verbosity level of the data output
    :param bool timed_sampling: specifies whether timed sampling is on or off
    """
    # Obtain the distinct set of function and usdt probes
    sampled_func, nonsampled_func = probes.get_partitioned_func_probes()
    sampled_usdt, nonsampled_usdt, single_usdt = probes.get_partitioned_usdt_probes()
    # Pre-build events and handlers based on the probe sets
    prebuilt = {
        "e": {
            "sampled_func": _build_func_events(sampled_func, timed_sampling),
            "sampled_usdt": _build_usdt_events(sampled_usdt),
            "sampled_usdt_exit": _build_usdt_events(sampled_usdt, "pair"),
            "nonsampled_func": _build_func_events(nonsampled_func, timed_sampling),
            "nonsampled_usdt": _build_usdt_events(nonsampled_usdt),
            "nonsampled_usdt_exit": _build_usdt_events(nonsampled_usdt, "pair"),
            "single_usdt": _build_usdt_events(single_usdt),
        },
        "h": {
            "func_begin": _build_probe_body(RecordType.FUNC_BEGIN, verbose_trace),
            "func_exit": _build_probe_body(RecordType.FUNC_END, verbose_trace),
            "usdt_begin": _build_probe_body(RecordType.USDT_BEGIN, verbose_trace),
            "usdt_exit": _build_probe_body(RecordType.USDT_END, verbose_trace),
            "usdt_single": _build_probe_body(RecordType.USDT_SINGLE, verbose_trace),
        },
    }
    # Create pairs of events-handlers to add to the script
    # Nonsampled: function entry, function exit, USDT entry, USDT exit
    # Sampled: function entry, function exit, USDT entry, USDT exit
    # Single: USDT single
    specification = [
        (
            prebuilt["e"]["nonsampled_func"].format(suffix=".call?"),
            prebuilt["h"]["func_begin"],
        ),
        (
            prebuilt["e"]["nonsampled_func"].format(suffix=".return?"),
            prebuilt["h"]["func_exit"],
        ),
        (prebuilt["e"]["nonsampled_usdt"], prebuilt["h"]["usdt_begin"]),
        (prebuilt["e"]["nonsampled_usdt_exit"], prebuilt["h"]["usdt_exit"]),
        (prebuilt["e"]["single_usdt"], prebuilt["h"]["usdt_single"]),
        (
            prebuilt["e"]["sampled_func"].format(suffix=".call?"),
            ENTRY_APPROX_SAMPLE_TEMPLATE.format(probe_handler=prebuilt["h"]["func_begin"]),
        ),
        (
            prebuilt["e"]["sampled_func"].format(suffix=".return?"),
            EXIT_APPROX_SAMPLE_TEMPLATE.format(probe_handler=prebuilt["h"]["func_exit"]),
        ),
        (
            prebuilt["e"]["sampled_usdt"],
            ENTRY_APPROX_SAMPLE_TEMPLATE.format(probe_handler=prebuilt["h"]["usdt_begin"]),
        ),
        (
            prebuilt["e"]["sampled_usdt_exit"],
            EXIT_APPROX_SAMPLE_TEMPLATE.format(probe_handler=prebuilt["h"]["usdt_exit"]),
        ),
    ]

    for spec_event, spec_handler in specification:
        # Add the new events + handler only if there are some associated events
        if spec_event:
            probe = PROBE_TEMPLATE.format(probe_events=spec_event, probe_handler=spec_handler)
            handle.write(probe)


def _build_array_declaration(probes, verbose_trace, max_threads):
    """Build only the array declarations necessary for the given script, i.e.,
    create / omit probe ID mapping array based on the verbosity
    create / omit sampling arrays based on the presence / absence of sampled probes, etc.

    :param Probes probes: the Probes object
    :param bool verbose_trace: the verbosity level of the output
    :param int max_threads: maximum number of expected simultaneous threads

    :return str: the built array declaration string
    """
    # Currently three types of arrays
    id_array = "# ID array omitted"
    sampling_arrays = "# Sampling arrays omitted"
    recursion_arrays = "# Recursion arrays omitted"
    # Verbose mode controls the ID array
    if not verbose_trace:
        id_array = f"global {ARRAY_PROBE_ID}[{probes.total_probes_len()}]"
    # Sampled probes control the presence of sampling arrays
    if probes.sampled_probes_len() > 0:
        array_size = probes.sampled_probes_len()
        max_array_size = array_size * max_threads
        max_array_size = max_array_size if max_array_size > MAX_MAP_ENTRIES else MAX_MAP_ENTRIES
        sampling_arrays = ARRAYS_SAMPLING_TEMPLATE.format(size=array_size, max_size=max_array_size)
    # TODO: Recursion sampling switch on / off
    return ARRAYS_TEMPLATE.format(
        id_array=id_array,
        sampling_arrays=sampling_arrays,
        recursion_arrays=recursion_arrays,
    )


def _array_assign(arr_id, arr_idx, arr_value):
    return f'    {arr_id}["{arr_idx}"] = {arr_value}\n'


def _build_id_init(probes, verbose_trace):
    """Build the probe name -> ID mapping initialization code

    :param Probes probes: the Probes object
    :param bool verbose_trace: the verbosity level of the output

    :return str: the built ID array initialization code
    """
    # The name -> ID mapping is not used in verbose mode
    if verbose_trace:
        return "    # Probe name -> Probe ID is not used in verbose mode\n"
    # For each probe, map the name to the probe ID for compact output
    init_string = "    # Probe name -> Probe ID\n"
    for probe in probes.get_probes():
        init_string += _array_assign(ARRAY_PROBE_ID, probe["name"], probe["id"])
    return init_string


def _build_sampling_init(probes):
    """Build the sampling arrays initialization code

    :param Probes probes: the Probes object

    :return str: the built sampling array initialization code
    """
    # The threshold array contains the sampling values for each function
    # When the threshold is reached, the probe generates a data record
    threshold_string = "    # Probe name -> Probe sampling threshold\n"
    # Generate the initialization code for both the function and USDT sampled probes
    for probe in probes.get_sampled_probes():
        threshold_string += _array_assign(ARRAY_SAMPLE_THRESHOLD, probe["name"], probe["sample"])
    return threshold_string


def _build_probe_body(probe_type, verbose_trace):
    """Build the probe innermost body.

    :param RecordType probe_type: the probe type
    :param bool verbose_trace: the verbosity level of the data output

    :return str: the probe handler code
    """
    # Set how the probe will be identified in the output and how we obtain the identification
    # based on the trace verbosity
    id_t, id_get = ("%s", "pname") if verbose_trace else ("%d", f"{ARRAY_PROBE_ID}[pname]")
    # Format the template for the required probe type
    return HANDLER_TEMPLATE.format(
        type=int(probe_type), id_type=id_t, id_get=id_get, timestamp=STOPWATCH_NAME
    )


def _build_func_events(probe_iter, timed_sampling):
    """Build function probe events code, which is basically a list of events that share some
    common handler.

    :param iter probe_iter: iterator of probe configurations
    :param bool timed_sampling: specifies whether Timed Sampling is on or off

    :return str: the built probe events code
    """

    def timed_switch(func_name):
        return f" if ({TIMED_SWITCH})" if timed_sampling and func_name != "main" else ""

    return ",\n      ".join(
        FUNC_EVENT_TEMPLATE.format(
            binary=prb["lib"], name=prb["name"], timed_switch=timed_switch(prb["name"])
        )
        for prb in probe_iter
    )


def _build_usdt_events(probe_iter, probe_id="name"):
    """Build USDT probe events code, which is basically a list of events that share some
    common handler.

    :param iter probe_iter: iterator of probe configurations

    :return str: the built probe events code
    """
    return ",\n      ".join(
        USDT_EVENT_TEMPLATE.format(binary=prb["lib"], loc=prb[probe_id]) for prb in probe_iter
    )


def _id_type_value(value_set, verbose_trace):
    """Select the type and value of printed data based on the verbosity level of the output.

    :param tuple value_set: a set of nonverbose / verbose data output
    :param bool verbose_trace: the verbosity level of the output

    :return tuple (str, str): the 'type' and 'value' objects for the print statement
    """
    if verbose_trace:
        return "%s", value_set[1]
    return "%d", value_set[0]
