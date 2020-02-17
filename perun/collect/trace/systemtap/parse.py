""" Parsing module for transforming the raw performance records from trace collector into
a perun profile.
"""

import collections

import perun.utils.metrics as metrics

from perun.collect.trace.watchdog import WATCH_DOG
from perun.collect.trace.values import RecordType, TraceRecord


def trace_to_profile(data_file, config, probes, **_):
    """Transforms the collection output into the performance resources. The
    collected time data are paired and provided as resources dictionaries.

    :param str data_file: name of the collection output file
    :param Configuration config: the configuration object
    :param Probes probes: the Probes object

    :return iterable: the generator object that produces dictionaries representing the resources
    """
    WATCH_DOG.info('Transforming the raw performance data into a perun profile format')
    trace_stack, sequence_map = {}, {}

    with open(data_file, 'r') as trace:
        cnt = 0
        line = ''
        try:
            # Initialize just in case the trace doesn't have 'begin' statement
            trace_stack, sequence_map = _init_stack_and_map(probes.func, probes.usdt)
            record = None
            for cnt, line in enumerate(trace):
                # File starts or ends
                if line.startswith('begin '):
                    # Initialize stack and map
                    trace_stack, sequence_map = _init_stack_and_map(probes.func, probes.usdt)
                    continue
                elif line.startswith('end '):
                    # Make sure that the main is always paired, even if not accurately
                    main_resource = _finalize_main(trace_stack['func'], record)
                    if main_resource:
                        main_resource['workload'] = config.executable.workload
                        yield main_resource
                    # TODO: Metrics
                    _count_funcs(sequence_map, probes.func)
                    return
                # Parse the line into the _TraceRecord tuple
                record = _parse_record(line)
                # Process the record
                resource = _process_record(
                    record, trace_stack, sequence_map, probes.usdt_reversed, probes.global_sampling
                )
                if resource:
                    resource['workload'] = config.executable.workload
                    yield resource
            WATCH_DOG.info('Data to profile transformation finished')
            # TODO: Metrics
            _count_funcs(sequence_map, probes.func)
        except Exception:
            WATCH_DOG.info('Error while parsing the raw trace record')
            # Log the status in case of unhandled exception
            WATCH_DOG.log_trace_stack(line, cnt, trace_stack)
            raise


def _count_funcs(sequence_map, probe_funcs):
    collected_funcs = set(
        name for name, val in sequence_map['func'].items() if val['seq'] >= 1
    )
    collected_funcs &= set(probe_funcs.keys())
    metrics.add_metric('collected_func', len(collected_funcs))


def _init_stack_and_map(func, usdt):
    """Initializes the data structures of function and USDT stacks for the trace parsing

    :param dict func: the function probes
    :param dict usdt: the USDT probes

    :return tuple: initialized trace stack and sequence map
    """

    def default_sequence_records(records):
        """ Initializes the default dictionaries for the sequence map

        :param iterable records: the iterable records

        :return dict: the resulting dictionary
        """
        return {record['name']: {'seq': 0, 'sample': record['sample']} for record in records}

    # func: thread -> stack (stack list, faults list)
    # usdt: thread -> name -> stack
    trace_stack = {
        'func': collections.defaultdict(lambda: ([], [])),
        'usdt': collections.defaultdict(lambda: collections.defaultdict(list))
    }
    # name -> sequence values
    sequence_map = {
        'func': default_sequence_records(func.values()),
        'usdt': default_sequence_records(usdt.values())
    }
    return trace_stack, sequence_map


def _finalize_main(stack, last_record):
    # print('finalizing main, last record: {}'.format(last_record))
    for thread_stack in stack.values():
        for call in thread_stack[0]:
            # There is still an unprocessed main record
            if call.name == 'main':
                # print('main start found!')
                if last_record is not None:
                    metrics.add_metric('abrupt_termination', True)
                    return {'amount': int(last_record.timestamp) - int(call.timestamp),
                            'uid': call.name,
                            'type': 'mixed',
                            'subtype': 'time delta',
                            'thread': call.thread,
                            'call-order': call.sequence}
    metrics.add_metric('abrupt_termination', False)
    return {}


# TODO: this should be used only after symbol cross-compare is functional
# def _demangle(trace):
#     """ Demangles the c++ function names in the collection output file if possible,
#     otherwise does nothing.
#
#     :param handle trace: the opened collection output file
#     :return iterable: (demangled) file contents
#     """
#     # Demangle the output if demangler is present
#     demangler = shutil.which('c++filt')
#     if demangler:
#         return utils.get_stdout_from_external_command([demangler], stdin=trace)
#     else:
#         return trace


def _process_record(record, trace_stack, sequence_map, usdt_reversed, global_sampling):
    """Process one output file line = record by calling corresponding functions for
    the given record type.

    :param namedtuple record: the _TraceRecord namedtuple with parsed line values
    :param dict trace_stack: the trace stack dictionary containing trace stacks for
                             function / USDT / etc. probes
    :param dict sequence_map: the map of sequence numbers for function / USDT / etc. probe names
    :param dict usdt_reversed: the collection of USDT probes used for pairing the USDT records

    :return dict: the record transformed into the performance resource or empty dict if no resource
                  could be produced
    """
    # The record was corrupted and thus not parsed properly
    if record.type == RecordType.Corrupt:
        return {}

    # The record is function begin or end point
    if record.type == RecordType.FuncBegin or record.type == RecordType.FuncEnd:
        resource = _process_func_record(
            record, trace_stack['func'][record.thread], sequence_map['func'], global_sampling
        )
        return resource
    # The record is usdt probe point
    resource = _process_usdt_record(
        record, trace_stack['usdt'][record.thread], sequence_map['usdt'],
        usdt_reversed, global_sampling
    )
    return resource


def _process_func_record(record, trace_stack, sequence_map, global_sampling):
    """Processes the function output record and tries to pair it with stack record if possible

    :param namedtuple record: the _TraceRecord namedtuple with parsed line values
    :param list trace_stack: the trace stack for function records
    :param dict sequence_map: stores the sequence counter for every function

    :returns dict: the resource dictionary or empty dict
    """
    stack = trace_stack[0]
    faults = trace_stack[1]

    # Get the top element in stack or create 'stack bottom' element if there is none
    try:
        top = stack[-1]
    except IndexError:
        top = TraceRecord(RecordType.FuncBegin, -1, '!stack_bottom', -1, 0, 0)

    # Function entry
    if record.type == RecordType.FuncBegin:
        if record.offset != top.offset + 1 and stack:
            faults.append(len(stack) - 1)
        _add_to_stack(stack, sequence_map, record, global_sampling)
        return {}

    # Function return, handle various offset / timestamp corruptions
    matching_record = None
    # Depending on the verbose mode, we might also be able to check if the names match
    if record.offset != top.offset or (record.name and record.name != top.name):

        # Search the faults for possible match
        for fault in reversed(faults):
            # Offset, timestamp and name (if any) must match
            if (fault < len(stack) and stack[fault].offset == record.offset
                    and stack[fault].timestamp < record.timestamp
                    and (not record.name or stack[fault].name == record.name)):
                # Match found
                matching_record = fault
                break
        # No matching fault found, search the whole stack for match
        if matching_record is None:
            for idx, elem in enumerate(reversed(stack)):
                # if (elem.offset == record.offset and elem.timestamp < record.timestamp
                if (elem.timestamp < record.timestamp
                        and (not record.name or elem.name == record.name)):
                    matching_record = len(stack) - idx - 1
                    break

        # Still no match found, simply ignore the return statement
        if matching_record is None:
            return {}

        # A match was found, update the stack and faults
        stack[:] = stack[:matching_record + 1]
        faults[:] = [f for f in faults if f < len(stack) - 1]
    # The matching record is on top of the stack, create resource
    matching_record = stack.pop()
    # for item in stack:
    #     if matching_record.name == item.name:
    #         print('recursion: {}'.format(matching_record.name))
    return {'amount': int(record.timestamp) - int(matching_record.timestamp),
            'uid': matching_record.name,
            'type': 'mixed',
            'subtype': 'time delta',
            'thread': record.thread,
            'call-order': matching_record.sequence}


def _process_usdt_record(record, trace_stack, sequence_map, usdt_reversed, global_sampling):
    """Processes the USDT output record and tries to pair it with stack record if possible

    :param namedtuple record: the _TraceRecord namedtuple with parsed line values
    :param dict trace_stack: the dictionary containing trace stack (list) for each USDT probe
    :param dict sequence_map: stores the sequence counter for every USDT probe
    :param dict usdt_reversed: the USDT reversed probes mapping

    :returns dict: the resource dictionary or empty dict
    """
    matching_record = None

    try:
        if record.type == RecordType.USDTSingle:
            # The probe is paired with itself, find the last record in the stack if there is any
            if trace_stack[record.name]:
                matching_record = trace_stack[record.name].pop()
            # Add the record into the trace stack to correctly measure time between each two hits
            _add_to_stack(trace_stack[record.name], sequence_map, record, global_sampling)
        elif record.type == RecordType.USDTBegin:
            # USDT starting probe, just insert into the stack
            _add_to_stack(trace_stack[record.name], sequence_map, record, global_sampling)
        elif record.type == RecordType.USDTEnd:
            # USDT end probe, find the starting probe
            pair = usdt_reversed[record.name]
            matching_record = trace_stack[pair].pop()
    except (KeyError, IndexError):
        return {}

    if matching_record:
        return {'amount': int(record.timestamp) - int(matching_record.timestamp),
                'uid': matching_record.name + '#' + record.name,
                'type': 'mixed',
                'subtype': 'time delta',
                'call-order': matching_record.sequence}
    return {}


def _add_to_stack(trace_stack, sequence_map, record, global_sampling):
    """Updates the trace stack and sequence mapping structures.

    :param list trace_stack: the trace stack list
    :param dict sequence_map: the sequence mapping dictionary
    :param namedtuple record: the _TraceRecord namedtuple representing the parsed record
    """
    trace_stack.append(record._replace(
        sequence=sequence_map.setdefault(
            record.name, {'seq': 0, 'sample': global_sampling})['seq']))
    sequence_map[record.name]['seq'] += sequence_map[record.name]['sample']


def _parse_record(line):
    """ Parses line from collector output into record tuple consisting of:
        record type, call stack offset, rule name, timestamp, thread and sequence.

    :param str line: one line from the collection output

    :returns namedtuple: the _TraceRecord tuple
    """

    try:
        # Split the line into = 'type' 'timestamp' 'process(pid)' : 'offset' 'rule'
        left, _, right = line.partition(':')
        rtype, timestamp, thread = left.split()
        # Parse the type = '0 - 9 decimal'
        rtype = RecordType(int(rtype))
        # Parse the pid - find the rightmost '(' and read the number between braces
        thread = int(thread[thread.rfind('(') + 1:-1])

        # Parse the offset and rule name = 'offset-spaces rule\n'
        right = right.rstrip('\n')
        name = right.lstrip(' ')
        offset = len(right) - len(name)
        return TraceRecord(rtype, offset, name, int(timestamp), thread, 0)
    except Exception:
        # In case there is any issue with parsing, return corrupted trace record
        WATCH_DOG.debug("Corrupted data record: '{}'".format(line))
        return TraceRecord(RecordType.Corrupt, -1, '', -1, 0, 0)
