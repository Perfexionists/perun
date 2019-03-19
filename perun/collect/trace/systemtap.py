"""Module wrapping SystemTap related operations such as:
    - starting the SystemTap with generated script
    - killing the SystemTap process
    - collected data transformation to profile format
    - etc.

This module serves as a SystemTap controller.
"""

import time
import shutil
import shlex
import os
import collections
from subprocess import TimeoutExpired
from enum import IntEnum

import perun.utils as utils
import perun.utils.exceptions as exceptions
import perun.utils.log as log
from perun.collect.trace.systemtap_script import RecordType


# The default sleep value
_DEFAULT_SLEEP = 0.5
# Avoid endless loops with hard timeout value, that breaks the loop in specific cases
_HARD_TIMEOUT = 30


# Collection statuses
class Status(IntEnum):
    """Status codes for before / collect / after phases. """
    OK = 0
    STAP = 1
    STAP_DEP = 2
    EXCEPT = 3


# The trace record template
_TraceRecord = collections.namedtuple('record',
                                      ['type', 'offset', 'name', 'timestamp', 'thread', 'sequence'])


def systemtap_collect(script_path, log_path, output_path, cmd, args, **kwargs):
    """Collects performance data using the system tap wrapper, assembled script and
    external command. This function serves as a interface to the system tap collector.

    :param str script_path: path to the assembled system tap script file
    :param str log_path: path to the collection log file
    :param str output_path: path to the collection output file
    :param str cmd: the external command that contains / invokes the profiled executable
    :param list args: the arguments supplied to the external command
    :param kwargs: additional collector configuration
    :return tuple: containing the collection status, path to the output file of the collector
    """
    # Perform the cleanup
    if kwargs['cleanup']:
        _stap_cleanup()

    # Create the output and log file for collection
    with open(log_path, 'w') as logfile:
        # Start the SystemTap process
        log.cprint(' Starting the SystemTap process... ', 'white')
        stap_pgid = set()
        try:
            stap_runner, code = start_systemtap_in_background(script_path, output_path, logfile,
                                                              **kwargs)
            if code != Status.OK:
                return code, None
            stap_pgid.add(os.getpgid(stap_runner.pid))
            log.done()

            # Run the command that is supposed to be profiled
            log.cprint(' SystemTap up and running, execute the profiling target... ', 'white')
            run_profiled_command(cmd, args, **kwargs)
            log.done()

            # Terminate SystemTap process after the file was fully written
            log.cprint(' Data collection complete, terminating the SystemTap process... ', 'white')
            _wait_for_output_file(output_path, kwargs['binary'])
            kill_systemtap_in_background(stap_pgid)
            log.done()
            return Status.OK, output_path
        # Timeout was reached, inform the user but continue normally
        except exceptions.HardTimeoutException as e:
            kill_systemtap_in_background(stap_pgid)
            log.cprintln('', 'white')
            log.warn(e.msg)
            log.warn('The profile creation might fail or be inaccurate.')
            return Status.OK, output_path
        # Critical error during profiling or collection interrupted
        # make sure we terminate the collector and remove module
        except (Exception, KeyboardInterrupt):
            if not stap_pgid:
                stap_pgid = None
            # Clean only our mess
            _stap_cleanup(stap_pgid, output_path)
            raise


def start_systemtap_in_background(stap_script, output, logfile, **_):
    """Sets up the system tap process in the background with root privileges

    :param str stap_script: path to the assembled system tap script file
    :param str output: path to the collector output file
    :param file logfile: file handle of the opened status log for collection
    :return tuple: consisting of the subprocess object, Status value
    """
    # Resolve the systemtap path
    stap = shutil.which('stap')
    if not stap:
        return Status.STAP_DEP

    # Basically no-op, but fetches root password so os.setpgrp does not halt due to missing password
    utils.run_safely_external_command('sudo sleep 0')
    # The setpgrp is needed for killing the root process which spawns child processes
    process = utils.start_nonblocking_process(
        'sudo stap -v {0} -o {1}'.format(shlex.quote(stap_script), shlex.quote(output)),
        universal_newlines=True, stderr=logfile, preexec_fn=os.setpgrp
    )
    # Wait until systemtap process is ready or error occurs
    return process, _wait_for_systemtap_startup(logfile.name, process)


def run_profiled_command(cmd, args, workload, timeout, **_):
    """Runs the profiled external command with arguments.

    :param str cmd: the external command
    :param str args: the command arguments
    :param str workload: the workload input
    :param int timeout: if the process does not end before the specified timeout,
                        the process is terminated
    """
    # Run the profiled command and block it with wait if timeout is specified
    full_command = utils.build_command_str(shlex.quote(cmd), args, workload)
    process = utils.start_nonblocking_process(full_command)
    try:
        process.wait(timeout=timeout)
    except TimeoutExpired:
        process.terminate()
        return


def _wait_for_systemtap_startup(logfile, stap_process):
    """The system tap startup takes some time and it is necessary to wait until the process
    is ready before the data collection itself. This function periodically scans the status
    log for updates until the process is ready.

    :param str logfile: name of the status log to check
    :param subprocess object stap_process: object representing the system tap process
    :return Status value: the Status code
    """
    with open(logfile, 'r') as scanlog:
        while True:
            try:
                # Take a break before the next status check
                stap_process.wait(timeout=_DEFAULT_SLEEP)
                # The process actually terminated which means that error occurred
                return Status.STAP
            except TimeoutExpired:
                # Check process status and reload the log file
                scanlog.seek(0)
                # Read the last line of logfile and return if the systemtap is ready
                last = (0, '')
                for line_num, line in enumerate(scanlog):
                    last = (line_num, line)
                # The line we are looking for is at least 5th, use language-neutral test
                if last[0] >= 4 and ' 5: ' in last[1]:
                    return Status.OK


def _wait_for_output_file(output, process):
    """Due to the system tap process being in the background, the output file is generally
    not fully written after the external command is finished and system tap process killed.
    Thus we scan the output file for ending marker that indicates finished writing.

    :param str output: name of the collection output file
    """
    # Wait until the file exists and something is written
    timeout = 0
    while not os.path.exists(output) or os.path.getsize(output) == 0:
        timeout = _sleep_with_timeout(timeout)

    # Find the last line of the file
    while True:
        # Explicitly reopen the file for every iteration to refresh the contents
        with open(output, 'rb') as content:
            # Move to the end of the file
            try:
                content.seek(-3, os.SEEK_END)  # Cover the case of '\n\n' at the end
            except OSError:
                timeout = _sleep_with_timeout(timeout)
                continue
            # Do backward steps until we find the next to last newline
            found = True
            while content.read(1) != b'\n':
                if content.tell() < 2:
                    # The file ends too soon, try again later
                    found = False
                    break
                content.seek(-2, os.SEEK_CUR)
            if found:
                # The file is ready if its last line is end marker
                if content.readline().decode().startswith('end {proc}'.format(proc=process)):
                    return
            timeout = _sleep_with_timeout(timeout)


def _sleep_with_timeout(counter):
    """Performs sleep and keeps track of total time slept to indicate hard timeout condition
    fulfilled. Raises HardTimeoutException if the timeout threshold was reached.

    :param int counter: the counter variable for hard timeout detection
    :return int: the updated counter value
    """
    if counter >= _HARD_TIMEOUT:
        raise exceptions.HardTimeoutException('Timeout reached during waiting for the collection'
                                              ' output file to fully load.')
    time.sleep(_DEFAULT_SLEEP)
    counter += _DEFAULT_SLEEP
    return counter


def _stap_cleanup(stap_pgid=None, target=''):
    """Performs cleanup of the possibly running systemtap processes and loaded kernel modules

    :param set stap_pgid: list of the systemtap processes to terminate
    :param str target: if set to some collect_record_<timestamp>.txt, then only the process
                       associated with this collection will be searched for
    """
    if stap_pgid is None:
        stap_pgid = _running_stap_processes(target)
    kill_systemtap_in_background(stap_pgid)
    # Remove also the loaded kernel modules that were not removed by the systemtap
    time.sleep(_DEFAULT_SLEEP)  # Stap processes are in background, the unloading can take some time
    _remove_stap_modules(_loaded_stap_kernel_modules())


def _running_stap_processes(target=''):
    """Extracts gpid of all systemtap processes that are currently running on the system
    or only the systemtap process that is associated with the specified profiling

    :param str target: if set to some collect_record_<timestamp>.txt, then only the process
                       associated with this collection will be searched for
    :return set: the set of gpid of running stap processes
    """
    # Check that dependencies are not missing
    if (not utils.check_dependency('ps') or not utils.check_dependency('grep')
            or not utils.check_dependency('awk')):
        log.warn(' Unable to perform cleanup of systemtap processes, please terminate them manually'
                 ' or install the missing dependencies')

    # Create command for extraction of stap processes that are currently running on the system
    extractor = 'ps aux | grep stap'
    if target:
        # We look only for the process that was possibly used in this collection
        extractor += ' | grep {record}'.format(record=target)
    # Filter only the root stap process, not the spawned children
    extractor += ' | awk \'$11" "$12 == "sudo stap" {print $2}\''

    # Get the pid list and kill the processes
    out, _ = utils.run_safely_external_command(extractor, False)
    gpid = set()
    for line in out.decode('utf-8').splitlines():
        try:
            gpid.add(os.getpgid(int(line)))
        except ProcessLookupError:
            # The process might have been already somehow terminated
            continue
    return gpid


# TODO: There seems to be useless to test for only_self, as the same module can be used from cache
# and loaded again, check again for possible distinction
def _loaded_stap_kernel_modules():
    """Extracts the names of all systemtap kernel modules that are currently loaded

    :return set: the list of names of loaded systemtap kernel modules
    """
    # Check that dependencies are not missing
    if (not utils.check_dependency('lsmod') or not utils.check_dependency('grep')
            or not utils.check_dependency('awk') or not utils.check_dependency('rmmod')):
        log.warn(' Unable to perform cleanup of systemtap kernel modules, please terminate them '
                 ' manually or install the missing dependencies')
        return []
    # Build the extraction command
    extractor = 'lsmod | grep stap_ | awk \'{print $1}\''

    # Run the command and save the found modules
    out, _ = utils.run_safely_external_command(extractor, False)
    modules = set()
    for line in out.decode('utf-8'):
        modules.add(line)
    return modules


def kill_systemtap_in_background(stap_processes):
    """Terminates the system tap processes that are running in the background and all child
    processes that were spawned.

    :param set stap_processes: the list of PGID of the stap processes to kill
    """
    for pgid in stap_processes:
        utils.run_safely_external_command('sudo kill {0}'.format(pgid), False)


def _remove_stap_modules(modules):
    """Removes (unloads) the specified systemtap modules from the kernel

    :param set modules: the list of modules to unload
    """
    for module in modules:
        rm_cmd = 'sudo rmmod {mod}'.format(mod=module)
        utils.run_safely_external_command(rm_cmd, False)


def trace_to_profile(output_path, func, static, **kwargs):
    """Transforms the collection output into the performance profile, where the
    collected time data are paired and stored as a resources.

    :param str output_path: name of the collection output file
    :param dict func: the function probe specifications
    :param dict static: the static probe specifications as a dictionaries
    :param kwargs: additional parameters
    :return object: the generator object that produces dictionaries representing the resources
    """
    trace_stack, sequence_map = {}, {}

    with open(output_path, 'r') as trace:
        # Create demangled counterparts of the function names
        # trace = _demangle(trace)
        cnt = 0
        try:
            # Initialize just in case the trace doesn't have 'begin' statement
            trace_stack, sequence_map = _init_stack_and_map(func, static)
            for cnt, line in enumerate(trace):
                # File starts or ends
                if line.startswith('begin '):
                    # Initialize stack and map
                    trace_stack, sequence_map = _init_stack_and_map(func, static)
                    continue
                elif line.startswith('end '):
                    return
                # Parse the line into the _TraceRecord tuple
                record = _parse_record(line)
                # Process the record
                resource = _process_record(record, trace_stack, sequence_map, static,
                                           kwargs['global_sampling'])
                if resource:
                    resource['workload'] = kwargs.get('workload', ' '.join(kwargs['workload']))
                    yield resource
        except Exception:
            # Log the status in case of unhandled exception
            log.cprintln(' Error while parsing the raw trace record.', 'white')
            # Log the line that failed
            log.cprintln('  Line: {}'.format(str(cnt)), 'white')
            log.cprintln('  Func stack:', 'white')
            # Log the function probe stack
            if 'func' in trace_stack:
                for thread, stack in trace_stack['func'].items():
                    log.cprintln('   Thread {}:'.format(str(thread)), 'white')
                    log.cprintln('    ' + '\n    '.join(map(str, stack[0])), 'white')
            # Log the static probe stack
            log.cprintln('  Static stack:', 'white')
            if 'static' in trace_stack:
                for thread, probes in trace_stack['static'].items():
                    log.cprintln('   Thread {}:'.format(str(thread)), 'white')
                    for name, stack in probes.items():
                        log.cprintln('    Probe {}:'.format(name), 'white')
                        log.cprintln('     ' + '\n     '.join(map(str, stack)), 'white')
            raise


def _init_stack_and_map(func, static):
    """Initializes the data structures of function and static stacks for the trace parsing

    :param dict func: the function probes
    :param dict static: the static probes
    :return tuple: initialized trace stack and sequence map
    """
    # func: thread -> stack (stack list, faults list)
    # static: thread -> name -> stack
    trace_stack = {
        'func': collections.defaultdict(lambda: ([], [])),
        'static': collections.defaultdict(lambda: collections.defaultdict(list))
    }
    # name -> sequence values
    sequence_map = {
        'func': {
            record['name']: {
                'seq': 0,
                'sample': record['sample']
            } for record in func.values()},
        'static': {
            record['name']: {
                'seq': 0,
                'sample': record['sample']
            } for record in static.values()}
    }
    return trace_stack, sequence_map


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


def _process_record(record, trace_stack, sequence_map, static, global_sampling):
    """Process one output file line = record by calling corresponding functions for
    the given record type.

    :param namedtuple record: the _TraceRecord namedtuple with parsed line values
    :param dict trace_stack: the trace stack dictionary containing trace stacks for
                             function / static / etc. probes
    :param dict sequence_map: the map of sequence numbers for function / static / etc. probe names
    :param dict static: the list of static probes used for pairing the static records
    :return dict: the record transformed into the performance resource or empty dict if no resource
                  could be produced
    """
    # The record was corrupted and thus not parsed properly
    if record.type == RecordType.Corrupt:
        return {}

    # The record is function begin or end point
    if record.type == RecordType.FuncBegin or record.type == RecordType.FuncEnd:
        resource = _process_func_record(record, trace_stack['func'][record.thread],
                                        sequence_map['func'], global_sampling)
        return resource
    # The record is static probe point
    resource = _process_static_record(record, trace_stack['static'][record.thread],
                                      sequence_map['static'], static, global_sampling)
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
        top = _TraceRecord(RecordType.FuncBegin, -1, '!stack_bottom', -1, 0, 0)

    # Function entry
    if record.type == RecordType.FuncBegin:
        if record.offset != top.offset + 1 and stack:
            faults.append(len(stack) - 1)
        _add_to_stack(stack, sequence_map, record, global_sampling)
        return {}

    # Function return, handle various offset / timestamp corruptions
    matching_record = False
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
        if not matching_record:
            for idx, elem in enumerate(reversed(stack)):
                if (elem.offset == record.offset and elem.timestamp < record.timestamp
                        and (not record.name or elem.name == record.name)):
                    matching_record = len(stack) - idx - 1
                    break

        # Still no match found, simply ignore the return statement
        if not matching_record:
            return {}

        # A match was found, update the stack and faults
        stack[:] = stack[:matching_record + 1]
        faults[:] = [f for f in faults if f < len(stack) - 1]
    # The matching record is on top of the stack, create resource
    matching_record = stack.pop()
    return {'amount': int(record.timestamp) - int(matching_record.timestamp),
            'uid': matching_record.name,
            'type': 'mixed',
            'subtype': 'time delta',
            'thread': record.thread,
            'structure-unit-size': matching_record.sequence}


def _process_static_record(record, trace_stack, sequence_map, probes, global_sampling):
    """Processes the static output record and tries to pair it with stack record if possible

    :param namedtuple record: the _TraceRecord namedtuple with parsed line values
    :param dict trace_stack: the dictionary containing trace stack (list) for each static probe
    :param dict sequence_map: stores the sequence counter for every static probe
    :param dict probes: the list of all static probe definitions for pairing
    :returns dict: the resource dictionary or empty dict
    """
    matching_record = None

    try:
        if record.type == RecordType.StaticSingle:
            # The probe is paired with itself, find the last record in the stack if there is any
            if trace_stack[record.name]:
                matching_record = trace_stack[record.name].pop()
            # Add the record into the trace stack to correctly measure time between each two hits
            _add_to_stack(trace_stack[record.name], sequence_map, record, global_sampling)
        elif record.type == RecordType.StaticBegin:
            # Static starting probe, just insert into the stack
            _add_to_stack(trace_stack[record.name], sequence_map, record, global_sampling)
        elif record.type == RecordType.StaticEnd:
            # Static end probe, find the starting probe
            pair = probes[record.name]['pair'][1]
            matching_record = trace_stack[pair].pop()
    except (KeyError, IndexError):
        return {}

    if matching_record:
        return {'amount': int(record.timestamp) - int(matching_record.timestamp),
                'uid': matching_record.name + '#' + record.name,
                'type': 'mixed',
                'subtype': 'time delta',
                'structure-unit-size': matching_record.sequence}
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
        return _TraceRecord(rtype, offset, name, timestamp, thread, 0)
    except Exception:
        # In case there is any issue with parsing, return corrupted trace record
        return _TraceRecord(RecordType.Corrupt, -1, '', -1, 0, 0)
