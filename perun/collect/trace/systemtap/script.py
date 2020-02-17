"""SystemTap script generator module. Assembles the SystemTap script according to the specified
rules such as function or USDT locations and sampling.
"""

from perun.collect.trace.watchdog import WATCH_DOG
from perun.collect.trace.values import RecordType
from perun.collect.trace.probes import ProbeType


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
        # Create the begin probe and initialize the sampling array
        _add_script_init(script_handle, config.binary, probes)

        # Iterate both function and USDT probes
        probe_iter = [(probes.func, _add_function_probe), (probes.usdt, _add_usdt_probe)]
        for probe_provider, probe_builder in probe_iter:
            # Sort the functions and USDT probes by name to ensure deterministic scripts
            for probe in sorted(probe_provider.values(), key=lambda value: value['name']):
                probe_builder(script_handle, config.binary, probe, config.verbose_trace)

        _add_end_probe(script_handle, config.binary)

    # Success
    WATCH_DOG.info("SystemTap script successfully assembled")
    WATCH_DOG.log_probes(len(probes.func), len(probes.usdt), script_file)


def _add_script_init(handle, binary, probes):
    """ Add the process begin probe, sampling array definition and initialization.

    :param TextIO handle: the script file handle
    :param str binary: the name of the binary file
    :param Probes probes: the probes specification
    """
    sampled_probes = len(probes.sampled_func) + len(probes.sampled_usdt)
    script_init = """{sampling_array}

probe process("{binary}").begin {{
{array_init}
    printf("begin {binary}\\n")
}}
""".format(sampling_array=_define_sampling_array(sampled_probes),
           array_init=_init_sampling_array(probes), binary=binary
           )
    handle.write(script_init)


def _add_end_probe(handle, binary):
    """Adds marker to the collection output indicating the end of collection. This is needed to
    determine that the output file is fully written and can be further analyzed and processed.

    :param TextIO handle: the script file handle
    :param str binary: the name of the binary file
    """
    end_probe = """
probe process("{binary}").end {{
    printf("end {binary}\\n")
}}
""".format(binary=binary)
    handle.write(end_probe)


def _define_sampling_array(size):
    """Defines the sampling array as a global variable

    :param int size: the number of elements in the sampling array

    :return str: the script component for array definition
    """
    # Create sampling array variable for given process
    if size:
        return 'global sample_array[{}]'.format(str(size))
    return '# sampling array omitted'


def _init_sampling_array(probes):
    """Handles the sampling array initialization during process startup.

    :param Probes probes: the probes specification

    :return str: the script component for array initialization
    """
    # initialize the array values according to the sampling specification during process startup
    array_init = ""
    for probe in probes.get_sampled_probes():
        sample_idx, sample_val = str(probe['sample_index']), str(probe['sample'] - 1)
        array_init += '    sample_array[{}] = {}\n'.format(sample_idx, sample_val)
    if not array_init:
        array_init = '    # sampling array initialization omitted\n'
    return array_init


def _add_function_probe(handle, binary, probe, verbose_trace):
    """ Add function entry and exit probes to the SystemTap script

    :param TextIO handle: the script file handle
    :param str binary: the name of the binary file
    :param dict probe: the function probe specification
    :param bool verbose_trace: output trace verbosity on / off
    """
    entry_body, exit_body = _build_probe_body(probe, verbose_trace)

    func_probes = """
probe process("{binary}").function("{name}").call? {{
{entry_body}
}}
probe process("{binary}").function("{name}").return? {{
{exit_body}
}}
""".format(binary=binary, name=probe['name'], entry_body=entry_body, exit_body=exit_body)
    handle.write(func_probes)


def _add_usdt_probe(handle, binary, probe, verbose_trace):
    """ Add USDT start and end (optionally) probes to the SystemTap script

        :param TextIO handle: the script file handle
        :param str binary: the name of the binary file
        :param dict probe: the function probe specification
        :param bool verbose_trace: output trace verbosity on / off
        """
    entry_body, exit_body = _build_probe_body(probe, verbose_trace)

    usdt_template = """
probe process("{binary}").mark("{loc}")? {{
{body}
}}
"""
    # Create the starting USDT probe
    usdt_start = usdt_template.format(binary=binary, loc=probe['name'], body=entry_body)
    handle.write(usdt_start)
    if exit_body is not None:
        # Create the end USDT probe (i.e. the paired probe) if needed
        usdt_end = usdt_template.format(binary=binary, loc=probe['pair'], body=exit_body)
        handle.write(usdt_end)


def _build_function_body(probe, verbose_trace):
    """ Create the function probe innermost body.

    :param dict probe: the function probe specification
    :param bool verbose_trace: output trace verbosity on / off

    :return tuple (str, str): entry probe body, exit probe body
    """
    # Build the body template for both entry and exit probes
    template = '    printf("{type} %s{func}\\n", thread_indent({indent}))'
    func_entry = template.format(type=int(RecordType.FuncBegin), func=probe['name'], indent=1)
    # The exit body differs based on the verbose trace
    func_exit = template.format(
        type=int(RecordType.FuncEnd), func=probe['name'] if verbose_trace else '', indent=-1
    )
    return func_entry, func_exit


def _build_usdt_body(probe, _):
    """ Create the USDT probe innermost body.

    :param dict probe: the USDT probe specification

    :return tuple (str, str or None): entry probe body, exit probe body or None
    """
    template = '    printf("{type} %s {loc}\\n", thread_indent(0))'
    # No paired probe = no exit body
    if probe['pair'] == probe['name']:
        begin_body = template.format(type=int(RecordType.USDTSingle), loc=probe['name'])
        end_body = None
    # Both begin and end probes are needed
    else:
        begin_body = template.format(type=int(RecordType.USDTBegin), loc=probe['name'])
        end_body = template.format(type=int(RecordType.USDTEnd), loc=probe['pair'])
    return begin_body, end_body


def _build_probe_body(probe, verbose_trace):
    """ Generic function for assembling probe body based on the probe type.

    :param dict probe: the probe specification
    :param bool verbose_trace: output trace verbosity on / off

    :return tuple (str, str): entry probe body, exit probe body
    """
    # Choose the correct body assembler depending on the probe type
    body_provider = _build_function_body if probe['type'] == ProbeType.Func else _build_usdt_body
    entry_body, exit_body = body_provider(probe, verbose_trace)
    # Add sampling code to the body if needed
    if probe['sample'] != 1:
        entry_body, exit_body = _build_sampled_body(probe, entry_body, exit_body)
    return entry_body, exit_body


def _build_sampled_body(probe, entry_body, exit_body):
    """ Add sampling code to the provided probe body.

    :param dict probe: the probe specification
    :param str entry_body: the entry probe body code
    :param str or None exit_body: the exit probe body code

    :return tuple (str, str or None): the sampled probe entry and exit body
    """
    # Add the sampling code to the entry probe
    probe_entry = """    sample_array[{index}] ++
    if (sample_array[{index}] == {threshold}) {{
    {body}
        sample_array[{index}] = 0
    }}""".format(index=probe['sample_index'], threshold=probe['sample'], body=entry_body)

    # Add the sampling code to the exit body if needed
    if exit_body is not None:
        probe_exit = """    if (sample_array[{index}] == 0) {{
    {body}
    }}""".format(index=probe['sample_index'], body=exit_body)
    else:
        probe_exit = None
    return probe_entry, probe_exit
