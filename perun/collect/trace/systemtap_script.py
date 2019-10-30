"""SystemTap script generator module. Assembles the SystemTap script according to the specified
rules such as function or static locations and sampling.
"""

from perun.collect.trace.watchdog import WD
from perun.collect.trace.values import RecordType


def assemble_system_tap_script(script_file, func, static, binary, verbose_trace, **_):
    """Assembles system tap script according to the configuration parameters.

    :param str script_file: path to the script file, that should be generated
    :param dict func: the collection of functions to probe, each function is represented
                      with dictionary
    :param dict static: the collection of static probe locations represented as a dictionaries
    :param str binary: the executable file that contains specified probe points
    :param bool verbose_trace: produces more verbose raw output if set to True
    """
    WD.info("Attempting to assembly the SystemTap script '{}'".format(script_file))

    script = ''

    # Get sampled probes and prepare the sampling array
    sampled_probes = _index_process_sampling(func, static)
    if sampled_probes:
        script += _define_sampling_array_for(0, len(sampled_probes))
    script += _add_begin_marker(binary, 0, sampled_probes)

    # Sort the functions and static probes by name to ensure deterministic scripts
    for func_probe in sorted(func.values(), key=lambda value: value['name']):
        script += _build_function_probe(func_probe, binary, 0, verbose_trace)

    for rule in sorted(static.values(), key=lambda value: value['name']):
        # Do not create duplicate rules for pairs (starting probe also creates the ending probe)
        if rule.get('pair', [RecordType.StaticBegin])[0] != RecordType.StaticEnd:
            script += _build_static_probe(rule, binary, 0)

    # Add the ending marker to determine the output is fully written
    script += _add_end_marker(binary)

    # Create the file and save the script
    with open(script_file, 'w') as stp_handle:
        stp_handle.write(script)
    WD.info("SystemTap script successfully assembled")
    WD.log_probes(len(func), len(static), script_file)


def _add_end_marker(process):
    """Adds marker to the collection output indicating the end of collection. This is needed to
    determine that the output file is fully written and can be further analyzed and processed.

    :param str process: the name of the process / executable that is profiled

    :return str: the rule for marker generation
    """
    return 'probe process("{path}").end {{\n\tprintf("end {path}\\n")\n}}'.format(path=process)


# TODO: generalize script content generation to multiple processes
# def _script_content_for(process, func_probes, static_probes, dynamic_probes,
#                         sampling, global_sampling):
#     pass


def _add_begin_marker(process, process_id, samples):
    """Adds marker to the beginning of the collection output.

    :param str process: the name of the profiled process
    :param int process_id: the ID number of the process
    :param list samples: the list of sampled probes and their indices
    """
    begin_probe = 'probe process("{path}").begin {{\n'.format(path=process)
    if samples:
        begin_probe += _init_sampling_array_for(process_id, samples)
    begin_probe += '\tprintf("begin {path}\\n")\n}}\n\n'.format(path=process)
    return begin_probe


def _define_sampling_array_for(process_id, size):
    """Defines global variable for sampling array of certain process

    :param int process_id: the process / executable identification
    :param int size: the number of elements in the sampling array

    :return str: the script component for array definition
    """
    # Create sampling array variable for given process
    return 'global samp_{proc_idx}[{size}]\n'.format(proc_idx=str(process_id), size=str(size))


def _init_sampling_array_for(process_id, samples):
    """Handles the sampling array initialization during process startup.

    :param int process_id: the process / executable identification
    :param list samples: list of probes for process with sampling initialization values

    :return str: the script component for array initialization
    """
    # initialize the array values according to the sampling specification during process startup
    array_init = ''
    for idx, sample in samples:
        array_init += ('\tsamp_{proc_idx}[{index}] = {init}\n'
                       .format(proc_idx=str(process_id), index=str(idx),
                               init=str(sample - 1)))
    return array_init


# TODO: improve the temporary func parameter
# (we would like to cross-compare mangled / demangled / user specified names)
def _build_function_probe(func, process, process_id, verbose_trace):
    """Assembles function entry and exit probes including sampling.

    :param dict func: the function probe specification
    :param str process: the name of the process / executable that contains the function
    :param int process_id: the process / executable identification
    :param bool verbose_trace: produces more verbose raw output if set to True

    :return str: the script component with function probes
    """
    # Probe start and end point declaration
    begin_probe = ('probe process("{proc}").function("{func}").call? {{\n'
                   .format(proc=process, func=func['name']))
    end_probe = ('probe process("{proc}").function("{func}").return? {{\n'
                 .format(proc=process, func=func['name']))
    # Probes definition
    begin_body = ('printf("{type} %s{func}\\n", thread_indent(1))'
                  .format(type=int(RecordType.FuncBegin), func=func['name']))

    end_body = ('printf("{type} %s{func}\\n", thread_indent(-1))'
                .format(type=int(RecordType.FuncEnd), func=func['name'] if verbose_trace else ''))

    # Add sampling counter manipulation to the probe definition if needed
    begin_probe += _build_probe_sampling_begin(process_id, func, begin_body)
    end_probe += _build_probe_sampling_end(process_id, func, end_body)

    return begin_probe + end_probe


def _build_static_probe(rule, process, process_id):
    """Assembles static rule probe. The static probe can have corresponding paired probe,
    which serves as a exitpoint for measuring, or the paired probe may not be present, which
    means that the time will be measured between each probe hit

    :param dict rule: the static probe specification
    :param str process: the name of the process / executable that contains the static probe point
    :param int process_id: the process / executable identification

    :return str: the script component with the static probe(s)
    """
    # Create static start probe
    begin_probe = ('probe process("{proc}").mark("{loc}") {{\n'
                   .format(proc=process, loc=rule['name']))
    begin_body = ('printf("{type} %s {loc}\\n", thread_indent(0))'
                  .format(loc=rule['name'], type=int(RecordType.StaticSingle)))
    end_probe = ''
    # Create also end probe if needed
    if 'pair' in rule:
        # Update the body record type
        begin_body = ('printf("{type} %s{loc}\\n", thread_indent(0))'
                      .format(loc=rule['name'], type=int(RecordType.StaticBegin)))
        end_probe = ('probe process("{proc}").mark("{loc}") {{\n'
                     .format(proc=process, loc=rule['pair'][1]))
        end_body = ('printf("{type} %s{loc}\\n", thread_indent(0))'
                    .format(loc=rule['pair'][1], type=int(RecordType.StaticEnd)))
        # Add sampling to the end probe
        end_probe += _build_probe_sampling_end(process_id, rule, end_body)

    # Add sampling to the start probe
    begin_probe += _build_probe_sampling_begin(process_id, rule, begin_body)
    return begin_probe + end_probe


# TODO: add support for dynamic rules
# def _dynamic_probe(rule, process, sample):
#     pass


def _build_probe_sampling_begin(process_id, rule, body):
    """Add code to the entry probe definition that handles the sampling.

    :param int process_id: the process / executable identification
    :param dict rule: the probe specification
    :param str body: the current probe definition body that will be wrapped by the sampling code

    :return str: the probe definition body with incorporated sampling
    """
    if 'index' in rule:
        return ('\tsamp_{proc_idx}[{index}] ++\n'
                '\tif(samp_{proc_idx}[{index}] == {threshold}) {{\n'
                '\t\t{body}\n'
                '\t\tsamp_{proc_idx}[{index}] = 0\n'
                '\t}}\n}}\n'
                .format(proc_idx=str(process_id), index=str(rule['index']),
                        threshold=str(rule['sample']), body=body))
    return '\t{body}\n}}\n\n'.format(body=body)


def _build_probe_sampling_end(process_id, rule, body):
    """Add code to the exit probe definition that handles the sampling.

    :param int process_id: the process / executable identification
    :param dict rule: the probe specification
    :param str body: the current probe definition body that will be wrapped by the sampling code

    :return str: the probe definition body with incorporated sampling
    """
    if 'index' in rule:
        return ('\tif(samp_{proc_idx}[{index}] == 0) {{\n'
                '\t\t{body}\n'
                '\t}}\n}}\n\n'
                .format(proc_idx=str(process_id), index=str(rule['index']), body=body))
    return '\t{body}\n}}\n\n'.format(body=body)


# TODO: generalize sampling indexation to multiple processes
# def _index_sampling(func_probes, static_probes, sampling, processes, global_sampling):
#     pass


def _index_process_sampling(func, static):
    """Performs indexation of probes that are sampled, which is needed to access the
    sampling array value for the given probe. The function adds 'index' value to sampled
    probes.

    :param dict func: the collection of function probe specification as dictionaries
    :param dict static: the collection of static probe locations that will be probed

    :returns list: list of pairs representing the index: sampling mapping
    """
    index = 0
    sampled = []
    # Iterate all probe lists
    for probe_collection in [func, static]:
        for prb_conf in sorted(probe_collection.values(), key=lambda value: value['name']):
            # Index probes that actually have sampling and avoid duplicate index for pairs
            if (prb_conf['sample'] > 1 and
                    ('pair' not in prb_conf or prb_conf['pair'][0] != RecordType.StaticEnd)):
                prb_conf['index'] = index
                sampled.append((index, prb_conf['sample']))
                index += 1
    # Provide index: sampling mapping
    return sampled
