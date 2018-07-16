"""SystemTap script generator module.

Creates SystemTap script according to the specification:
 - dynamic probe locations
 - static probe locations
 - global sampling
 - custom sampling

"""


import os
from enum import IntEnum


class RecordType(IntEnum):
    FuncBegin = 0
    FuncEnd = 1
    StaticSingle = 2
    StaticBegin = 3
    StaticEnd = 4


def assemble_system_tap_script(func, static, dynamic, binary, **kwargs):

    script = ''

    # Transform sampling specification to the appropriate format
    indexer = _index_process_sampling(func, static, dynamic)
    func = next(indexer)
    static = next(indexer)
    dynamic = next(indexer)

    # Get sampled probes and prepare the sampling array
    sampled_probes = next(indexer)
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
    return 'probe process("{path}").end {{\n\tprintf("end")\n}}'.format(path=process)


# TODO: generalize script content generation to multiple processes
# def _script_content_for(process, func_probes, static_probes, dynamic_probes, sampling, global_sampling):
#     pass


def _sampling_array_for(process_id, size):
    # Create sampling array variable for given process
    return 'global samp_{proc_idx}[{size}]\n'.format(proc_idx=str(process_id), size=str(size))


def _sampling_array_init_for(process, process_id, samples):
    # initialize the array values according to the sampling specification during process startup
    array_init = 'probe process("{path}").begin {{\n'.format(path=process)
    for probe in samples:
        array_init += ('\tsamp_{proc_idx}[{index}] = {init}\n'
                       .format(proc_idx=str(process_id), index=str(probe['index']), init=str(probe['sample'] - 1)))
    array_init += '}\n\n'

    return array_init


# TODO: derive numbers from the Enum in systemtap.py
def _function_probe(func, process, process_id):
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
    """Creates sampling dictionary that has appropriate form for script generation.
    Handles the global sampling and specific sampling overlaps and priorities.

    :param list of dict sampling: list of sampling specifications as dictionaries 'rule': 'sample'
    :param list func: the list of functions that will be probed
    :param list static: the list of static locations that will be probed
    :param list dynamic: the list of dynamic locations that will be probed
    :param int global_sampling: the sampling value set globally for every rule

    :returns: dict -- the sampling dictionary in form of {rule: (sampling value, index)},
                      where index is unique value representing the rule name

    """

    index = 0
    sampled = []
    for probe_list in [func, static, dynamic]:
        for probe in probe_list:
            if probe['sample'] > 0:
                probe['index'] = index
                sampled.append(probe)
                index += 1
        yield probe_list
    yield sampled
