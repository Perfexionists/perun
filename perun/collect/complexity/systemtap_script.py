"""SystemTap script generator module.

Creates SystemTap script according to the specification:
 - dynamic probe locations
 - static probe locations
 - global sampling
 - custom sampling

"""


import os
from enum import IntEnum


# Type of record in collector output
class RecordType(IntEnum):
    FuncBegin = 0
    FuncEnd = 1
    StaticSingle = 2
    StaticBegin = 3
    StaticEnd = 4


def assemble_system_tap_script(func, static, dynamic, binary, **kwargs):
    """Assembles system tap script according to the configuration parameters.

    :param list func: the list of functions to probe, each function is represented with dictionary
    :param list static: the list of static probe locations represented as a dictionaries
    :param list dynamic: the list of dynamic probe locations represented as a dictionaries
    :param str binary: the binary / executable file that contains specified probe points (functions, static, ...)
    :param kwargs: additional collector parameters
    :return str: the path to the assembled script file
    """
    script = ''

    # Transform sampling specification to the appropriate format
    indexer = _index_process_sampling(func, static, dynamic)
    func = next(indexer)
    static = next(indexer)
    dynamic = next(indexer)  # The dynamic probes are not supported yet

    # Get sampled probes and prepare the sampling array
    sampled_probes = next(indexer)
    if sampled_probes:
        script += _sampling_array_for(0, len(sampled_probes))
        script += _sampling_array_init_for(binary, 0, sampled_probes)

    for func in func:
        script += _function_probe(func, binary, 0)

    for rule in static:
        script += _static_probe(rule, binary, 0)

    # Add the ending marker to determine the output is fully written
    script += _end_marker(binary)

    # Create the file and save the script
    script_path = os.path.join(kwargs['cmd_dir'], 'collect_script_{0}.stp'.format(kwargs['timestamp']))
    with open(script_path, 'w') as stp_handle:
        stp_handle.write(script)
    return script_path


def _end_marker(process):
    """Adds marker to the collection output indicating the end of collection. This is needed to determine that the
    output file is fully written and can be further analyzed and processed.

    :param str process: the name of the process / executable that is profiled
    :return str: the rule for marker generation
    """
    return 'probe process("{path}").end {{\n\tprintf("end")\n}}'.format(path=process)


# TODO: generalize script content generation to multiple processes
# def _script_content_for(process, func_probes, static_probes, dynamic_probes, sampling, global_sampling):
#     pass


def _sampling_array_for(process_id, size):
    """Defines global variable for sampling array of certain process

    :param int process_id: the process / executable identification
    :param int size: the number of elements in the sampling array
    :return str: the script component for array definition
    """
    # Create sampling array variable for given process
    return 'global samp_{proc_idx}[{size}]\n'.format(proc_idx=str(process_id), size=str(size))


def _sampling_array_init_for(process, process_id, samples):
    """Handles the sampling array initialization during process startup.

    :param str process: the name of the process / executable
    :param int process_id: the process / executable identification
    :param list samples: list of probes as dictionaries for process with sampling initialization values
    :return str: the script component for array initialization
    """
    # initialize the array values according to the sampling specification during process startup
    array_init = 'probe process("{path}").begin {{\n'.format(path=process)
    for probe in samples:
        array_init += ('\tsamp_{proc_idx}[{index}] = {init}\n'
                       .format(proc_idx=str(process_id), index=str(probe['index']), init=str(probe['sample'] - 1)))
    array_init += '}\n\n'

    return array_init


def _function_probe(func, process, process_id):
    """Assembles function entry and exit probes including sampling.

    :param dict func: the function probe specification
    :param str process: the name of the process / executable that contains the function
    :param int process_id: the process / executable identification
    :return str: the script component with function probes
    """
    # Probe start and end point declaration
    begin_probe = 'probe process("{proc}").function("{func}").call {{\n'.format(proc=process, func=func['name'])
    end_probe = 'probe process("{proc}").function("{func}").return {{\n'.format(proc=process, func=func['name'])
    # Probes definition
    begin_body = 'printf("{type} %s %s\\n", thread_indent(1), probefunc())'.format(type=int(RecordType.FuncBegin))
    end_body = 'printf("{type} %s\\n", thread_indent(-1))'.format(type=int(RecordType.FuncEnd))

    # Add sampling counter manipulation to the probe definition if needed
    begin_probe += _probe_sampling_begin(process_id, func, begin_body)
    end_probe += _probe_sampling_end(process_id, func, end_body)

    return begin_probe + end_probe


def _static_probe(rule, process, process_id):
    """Assembles static rule probe. The static probe can have corresponding paired probe, which serves as a exit
    point for measuring, or the paired probe may not be present, which means that the time will be measured
    between each probe hit

    :param dict rule: the static probe specification
    :param str process: the name of the process / executable that contains the static probe point
    :param int process_id: the process / executable identification
    :return str: the script component with the static probe(s)
    """
    # Create static start probe
    begin_probe = 'probe process("{proc}").mark("{loc}") {{\n'.format(proc=process, loc=rule['name'])
    begin_body = 'printf("{type} %s {loc}\\n", thread_indent(0))'.format(loc=rule['name'],
                                                                         type=int(RecordType.StaticSingle))
    end_probe = ''
    # Create also end probe if needed
    if 'pair' in rule:
        # Update the body record type
        begin_body = 'printf("{type} %s {loc}\\n", thread_indent(0))'.format(loc=rule['name'],
                                                                             type=int(RecordType.StaticBegin))
        end_probe = 'probe process("{proc}").mark("{loc}") {{\n'.format(proc=process, loc=rule['pair'])
        end_body = 'printf("{type} %s {loc}\\n", thread_indent(0))'.format(loc=rule['pair'],
                                                                           type=int(RecordType.StaticEnd))
        # Add sampling to the end probe
        end_probe += _probe_sampling_end(process_id, rule, end_body)

    # Add sampling to the start probe
    begin_probe += _probe_sampling_begin(process_id, rule, begin_body)
    return begin_probe + end_probe


# TODO: add support for dynamic rules
# def _dynamic_probe(rule, process, sample):
#     pass


def _probe_sampling_begin(process_id, rule, body):
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
                .format(proc_idx=str(process_id), index=str(rule['index']), threshold=str(rule['sample']), body=body))
    else:
        return '\t{body}\n}}\n\n'.format(body=body)


def _probe_sampling_end(process_id, rule, body):
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
    else:
        return '\t{body}\n}}\n\n'.format(body=body)


# TODO: generalize sampling transformation to multiple processes
# def _transform_sampling(func_probes, static_probes, dynamic_probes, sampling, processes, global_sampling):
#     pass


def _index_process_sampling(func, static, dynamic):
    """Performs indexation of probes that are sampled, which is needed to access the sampling array value for
    the given probe.

    :param list func: the list of function specification as dictionaries
    :param list static: the list of static probe locations that will be probed
    :param list dynamic: the list of dynamic locations that will be probed

    :returns object: the generator object that provides:
                     - updated function, static and dynamic probe lists
                     - the list of probes with sampling

    """
    index = 0
    sampled = []
    # Iterate all probe lists
    for probe_list in [func, static, dynamic]:
        for probe in probe_list:
            # Index probes that actually have sampling
            if probe['sample'] > 0:
                probe['index'] = index
                sampled.append(probe)
                index += 1
        # Provide the current probe list
        yield probe_list
    # Provide all the probes with sampling
    yield sampled
