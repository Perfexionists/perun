"""This module provides methods for parsing raw memory data"""

import collections
import re

from typing import Dict
from decimal import Decimal

from typing import TypedDict
from typing_extensions import Unpack

import perun.profile.convert as convert
import perun.collect.memory.syscalls as syscalls
import perun.utils.helpers as helpers

from perun.utils.structs import Executable


class Resource(TypedDict):
    amount: int
    address: int
    trace: list[dict]
    type: str
    subtype: str
    uid: dict
    allocation_order: int


__author__ = "Radim Podola"

PATTERN_WORD = re.compile(r"(\w+|[?])")
PATTERN_TIME = re.compile(r"\d+([,.]\d*)?|[,.]\d+")
PATTERN_HEXADECIMAL = re.compile(r"0x[0-9a-fA-F]+")
PATTERN_INT = re.compile(r"\d+")
UID_RESOURCE_MAP: Dict[str, int] = collections.defaultdict(int)


def parse_stack(stack: list[str]) -> list[dict]:
    """ Parse stack information of one allocation

    :param list stack: list of raw stack data
    :returns list: list of formatted structures representing stack trace of one allocation
    """
    data = []
    for call in stack:
        call_data = {}

        # parsing name of function,
        # it's the first word in the call record
        func = helpers.safe_match(PATTERN_WORD, call, "<?>")
        # demangling name of function
        func = syscalls.demangle(func)
        call_data['function'] = func

        # parsing instruction pointer,
        # it's the first hexadecimal number in the call record
        instruction_pointer = helpers.safe_match(PATTERN_HEXADECIMAL, call, "<?>")

        # getting information of instruction pointer,
        # the source file and line number in the source file
        ip_info = syscalls.address_to_line(instruction_pointer)
        if ip_info[0] in ["?", "??"]:
            ip_info[0] = "unreachable"
        if ip_info[1] in ["?", "??"]:
            ip_info[1] = 0
        else:
            ip_info[1] = helpers.safe_match(PATTERN_INT, ip_info[1], "<?>")

        call_data['source'] = ip_info[0]
        call_data['line'] = int(ip_info[1])

        data.append(call_data)

    return data


def parse_allocation_location(trace: list) -> dict:
    """ Parse the location of user's allocation from stack trace

    :param list trace: list representing stack call trace
    :returns dict: first user's call to allocation
    """
    for call in trace or []:
        source = call['source']
        if source != "unreachable":
            return call
    return {}


def parse_resources(allocation: list[str]) -> Resource:
    """ Parse resources of one allocation

    :param list allocation: list of raw allocation data
    :returns structure: formatted structure representing resources of one allocation
    """
    data:  Resource = {}  # type: ignore

    # parsing amount of allocated memory,
    # it's the first number on the second line
    amount = helpers.safe_match(PATTERN_INT, allocation[1], -1)
    data['amount'] = int(amount)

    # parsing allocate function,
    # it's the first word on the second line
    allocator = helpers.safe_match(PATTERN_WORD, allocation[1], "<?>")
    data['subtype'] = allocator

    # parsing address of allocated memory,
    # it's the second number on the second line
    address = PATTERN_INT.findall(allocation[1])[1]
    data['address'] = int(address)

    # parsing stack in the moment of allocation
    # to getting trace of it
    trace = parse_stack(allocation[2:])
    data['trace'] = trace

    # parsed data is memory type
    data['type'] = 'memory'

    # parsing call trace to get first user call
    # to allocation function
    data['uid'] = parse_allocation_location(trace)

    # update the resource number
    flattened_uid = convert.flatten(data['uid'])
    UID_RESOURCE_MAP[flattened_uid] += 1
    data['allocation_order'] = UID_RESOURCE_MAP[flattened_uid]

    return data


def parse_log(filename: str, executable: Executable, snapshots_interval: float) -> dict:
    """ Parse raw data in the log file

    :param string filename: name of the log file
    :param Executable executable: profiled binary
    :param float snapshots_interval: interval of snapshots [s]
    :returns structure: formatted structure representing section "snapshots" and "global"
        in memory profile
    """
    interval = snapshots_interval
    with open(filename) as logfile:
        log_lines = logfile.read()
    # allocations are split by empty line
    log = log_lines.split('\n\n')

    # Check that there is exit, and the Memory Log is thus not malformed
    if log.pop().strip().find('EXIT') == -1:
        raise ValueError

    allocations = []
    for item in log:
        allocations.append(item.splitlines())

    # Collect names and addresses for demangling and addr2line collective call
    names, ips = set(), set()
    for allocation in allocations:
        for resource in allocation[2:]:
            name, instruction_pointer, offset = resource.split(' ')
            names.add(name)
            ips.add((instruction_pointer, offset))

    # Build caches for demangle and addr2line for further calls
    syscalls.build_demangle_cache(names)
    syscalls.build_address_to_line_cache(ips, executable.cmd)

    snapshots = []
    data = {'time': f'{interval:f}', 'resources': []}
    for allocation in allocations:
        # parsing timestamp,
        # it's the only one number on the 1st line
        time_string = allocation[0]
        # in some cases there is '.' instead of ',' in timestamp
        if time_string.find(',') > 0:
            time_string = time_string.replace(',', '.')

        time = Decimal(helpers.safe_match(PATTERN_TIME, time_string, -1))

        while time > interval:
            snapshots.append(data)
            interval += snapshots_interval
            data = {
                'resources': [], 'time': f'{interval:f}'
            }

        # using parse_resources()
        # parsing resources,
        data['resources'].append(parse_resources(allocation))  # type: ignore

    if data:
        snapshots.append(data)

    return {'snapshots': snapshots, 'global': {'resources': []}}
