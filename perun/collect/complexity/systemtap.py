"""Module wrapping SystemTap related operations such as:
    - SystemTap script assembling
    - starting the SystemTap with generated script
    - killing the SystemTap process
    - collected data transformation to profile format
    - etc.

This module serves basically as SystemTap controller.
"""

import time
import shutil
import shlex
import os
import collections
from subprocess import TimeoutExpired, CalledProcessError
from enum import IntEnum

import perun.utils as utils
import perun.utils.exceptions as exceptions
from perun.collect.complexity.systemtap_script import RecordType


# Collection statuses
class Status(IntEnum):
    OK = 0
    STAP = 1
    STAP_DEP = 2
    EXCEPT = 3


# The trace record template
_TraceRecord = collections.namedtuple('record', ['type', 'offset', 'name', 'timestamp', 'sequence'])


def systemtap_collect(script, cmd, args, **kwargs):
    # Create the output and log file for collection
    output = os.path.join(kwargs['cmd_dir'], 'collect_record_{0}.txt'.format(kwargs['timestamp']))
    log = os.path.join(kwargs['cmd_dir'], 'collect_log_{0}.txt'.format(kwargs['timestamp']))

    with open(log, 'w') as logfile:
        # Start the SystemTap process
        print('Starting the SystemTap process... ', end='')
        stap_runner, code = start_systemtap_in_background(script, output, logfile, **kwargs)
        if code != Status.OK:
            return code, None
        print('Done')

        # Run the command that is supposed to be profiled
        print('SystemTap up and running, execute the profiling target... ', end='')
        try:
            run_profiled_command(cmd, args)
        except CalledProcessError:
            # Critical error during profiled command, make sure we terminate the collector
            kill_systemtap_in_background(stap_runner)
            raise
        print('Done')

        # Terminate SystemTap process after the file was fully written
        print('Data collection complete, terminating the SystemTap process... ', end='')
        _wait_for_fully_written(output)
        kill_systemtap_in_background(stap_runner)
        print('Done')
        return Status.OK, output


def start_systemtap_in_background(stap_script, output, log, **_):
    # Resolve the systemtap path
    stap = shutil.which('stap')
    if not stap:
        return Status.STAP_DEP

    # Basically no-op, but requesting root password so os.setpgrp does not halt due to missing password
    utils.run_safely_external_command('sudo sleep 0')
    # The setpgrp is needed for killing the root process which spawns child processes
    process = utils.start_nonblocking_process(
        'sudo stap -v {0} -o {1}'.format(shlex.quote(stap_script), shlex.quote(output)),
        universal_newlines=True, stderr=log, preexec_fn=os.setpgrp
    )
    # Wait until systemtap process is ready or error occurs
    return process, _wait_for_systemtap_startup(log.name, process)


def kill_systemtap_in_background(stap_process):
    utils.run_safely_external_command('sudo kill {0}'.format(os.getpgid(stap_process.pid)))


def run_profiled_command(cmd, args):
    if args != '':
        full_command = '{0} {1}'.format(shlex.quote(cmd), args)
    else:
        full_command = shlex.quote(cmd)
    utils.run_safely_external_command(full_command, False)


def _wait_for_systemtap_startup(logfile, stap_process):
    with open(logfile, 'r') as scanlog:
        while True:
            try:
                # Take a break before the next status check
                stap_process.wait(timeout=0.5)
                # The process actually terminated which means that error occurred
                return Status.STAP
            except TimeoutExpired:
                # Check process status and reload the log file
                scanlog.seek(0)
                # Read the last line of logfile and return if the systemtap is ready
                last = ''
                for line in scanlog:
                    last = line
                if last == 'Pass 5: starting run.\n':
                    return Status.OK


def _wait_for_fully_written(output):
    with open(output, 'rb') as content:
        # Wait until the file is not empty
        while os.path.getsize(output) == 0:
            time.sleep(0.5)

        while True:
            # Find the last line of the file
            content.seek(-2, os.SEEK_END)
            while content.read(1) != b'\n':
                content.seek(-2, os.SEEK_CUR)
            marker = content.readline().decode()
            # The file is ready if it's last line is end marker
            if marker == 'end':
                return
            time.sleep(0.5)


def trace_to_profile(**kwargs):
    trace_stack = {'func': [], 'static': collections.defaultdict(list), 'dynamic': collections.defaultdict(list)}
    sequence_map = {'func': collections.defaultdict(int), 'static': collections.defaultdict(int),
                    'dynamic': collections.defaultdict(int)}

    with open(kwargs['output'], 'r') as trace:

        # Create demangled counterparts of the function names
        trace = _demangle(trace)

        for line in trace.splitlines(keepends=True):
            # File ended
            if line == 'end':
                return

            # Parse the line into the _TraceRecord tuple
            record = _parse_record(line)
            # Process the record
            resource = _process_record(record, trace_stack, sequence_map, kwargs['static'])
            if resource:
                yield resource


def _demangle(trace):
        demangler = shutil.which('c++filt')
        if demangler:
            return utils.get_stdout_from_external_command([demangler], shell=False, stdin=trace)
        else:
            return trace


def _process_record(record, trace_stack, sequence_map, static):
    if record.type == RecordType.FuncBegin or record.type == RecordType.FuncEnd:
        resource, trace_stack['func'] = _process_func_record(record, trace_stack['func'], sequence_map['func'])
        return resource
    else:
        resource, trace_stack['static'] = _process_static_record(record, trace_stack['static'], sequence_map['static'],
                                                                 static)
        return resource


def _process_func_record(record, trace_stack, sequence_map):
    """ Processes the next profile record and tries to pair it with stack record if possible

    :param namedtuple record: the _ProfileRecord tuple containing the record data
    :param list trace_stack: the call stack with file records
    :param list resources: the list of resource dictionaries
    :param dict sequence_map: stores the sequence counter for every function
    :returns: int -- status code, nonzero values for errors
    """
    if record.type == RecordType.FuncBegin:
        # Function entry, add to stack and note the sequence number
        trace_stack.append(record._replace(sequence=sequence_map[record.name]))
        sequence_map[record.name] += 1
        return {}, trace_stack
    elif trace_stack and record.offset == trace_stack[-1].offset - 1:
        # Function exit, match with the function enter to create resources record
        matching_record = trace_stack.pop()
        return {'amount': int(record.timestamp) - int(matching_record.timestamp),
                'uid': matching_record.name,
                'type': 'mixed',
                'subtype': 'time delta',
                'structure-unit-size': matching_record.sequence}, trace_stack
    raise exceptions.TraceStackException(record, trace_stack)


def _process_static_record(record, trace_stack, sequence_map, probes):
    matching_record = None
    if record.type == RecordType.StaticSingle:
        # The probe is paired with itself, find the last record in the stack
        if trace_stack[record.name]:
            matching_record = trace_stack[record.name].pop()
    elif record.type == RecordType.StaticEnd:
        # Static end probe, find the starting probe record
        name = None
        for probe in probes:
            if probe['pair'] == record.name:
                name = probe['name']
        # Name not found or its stack is empty
        if not name or not trace_stack[name]:
            raise exceptions.TraceStackException(record, trace_stack)
        matching_record = trace_stack[name].pop()

    if matching_record:
        # Matching record was found, create resource
        return {'amount': int(record.timestamp) - int(matching_record.timestamp),
                'uid': record.name + '#' + matching_record.name,
                'type': 'mixed',
                'subtype': 'time delta',
                'structure-unit-size': record.sequence}, trace_stack
    else:
        # No matching record found, insert into the stack
        trace_stack[record.name].append(record._replace(sequence=sequence_map[record.name]))
        sequence_map[record.name] += 1
        return {}, trace_stack


def _parse_record(line):
    """ Parses line into record tuple consisting of record type, call stack offset, rule name, timestamp and sequence.

    :param str line: one line from the trace output
    :returns: namedtuple -- the _TraceRecord tuple
    """

    # Split the line into = 'type' 'timestamp process' : 'offset' 'rule'
    parts = line.partition(':')
    # Parse the type = '0 - 9 decimal'
    rtype = RecordType(int(parts[0][0]))
    # Parse the timestamp = 'int process'

    time = parts[0][1:].lstrip(' ').split()[0]
    # Parse the offset and rule name = 'offset-spaces rule\n'
    right_section = parts[2].rstrip('\n')
    name = right_section.lstrip(' ')
    offset = len(right_section) - len(name)
    return _TraceRecord(rtype, offset, name, time, 0)

