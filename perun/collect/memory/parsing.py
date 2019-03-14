"""This module provides methods for parsing raw memory data"""

import collections
import re

from decimal import Decimal
import perun.profile.convert as convert
import perun.collect.memory.syscalls as syscalls

__author__ = "Radim Podola"

PATTERN_WORD = re.compile(r"(\w+|[?])")
PATTERN_TIME = re.compile(r"\d+([,.]\d*)?|[,.]\d+")
PATTERN_HEXADECIMAL = re.compile(r"0x[0-9a-fA-F]+")
PATTERN_INT = re.compile(r"\d+")
UID_RESOURCE_MAP = collections.defaultdict(int)


def parse_stack(stack):
    """ Parse stack information of one allocation

    :param list stack: list of raw stack data
    :returns list: list of formatted structures representing stack trace of one allocation
    """
    data = []
    for call in stack:
        call_data = {}

        # parsing name of function,
        # it's the first word in the call record
        func = PATTERN_WORD.search(call).group()
        # demangling name of function
        func = syscalls.demangle(func)
        call_data.update({'function': func})

        # parsing instruction pointer,
        # it's the first hexadecimal number in the call record
        ip = PATTERN_HEXADECIMAL.search(call).group()

        # getting information of instruction pointer,
        # the source file and line number in the source file
        ip_info = syscalls.address_to_line(ip)
        if ip_info[0] in ["?", "??"]:
            ip_info[0] = "unreachable"
        if ip_info[1] in ["?", "??"]:
            ip_info[1] = 0
        else:
            ip_info[1] = PATTERN_INT.search(ip_info[1]).group()

        call_data.update({'source': ip_info[0]})
        call_data.update({'line': int(ip_info[1])})

        data.append(call_data)

    return data


def parse_allocation_location(trace):
    """ Parse the location of user's allocation from stack trace

    :param list trace: list representing stack call trace
    :returns dict: first user's call to allocation
    """
    if not trace:
        return {}

    for call in trace:
        source = call['source']
        if source != "unreachable":
            return call

    return {}


def parse_resources(allocation, workload):
    """ Parse resources of one allocation

    :param list allocation: list of raw allocation data
    :param str workload: workload of the resource
    :returns structure: formatted structure representing resources of one allocation
    """
    data = {'workload': workload}

    # parsing amount of allocated memory,
    # it's the first number on the second line
    amount = PATTERN_INT.search(allocation[1]).group()
    data.update({'amount': int(amount)})

    # parsing allocate function,
    # it's the first word on the second line
    allocator = PATTERN_WORD.search(allocation[1]).group()
    data.update({'subtype': allocator})

    # parsing address of allocated memory,
    # it's the second number on the second line
    address = PATTERN_INT.findall(allocation[1])[1]
    data.update({'address': int(address)})

    # parsing stack in the moment of allocation
    # to getting trace of it
    trace = parse_stack(allocation[2:])
    data.update({'trace': trace})

    # parsed data is memory type
    data.update({'type': 'memory'})

    # parsing call trace to get first user call
    # to allocation function
    data.update({'uid': parse_allocation_location(trace)})

    # update the resource number
    flattened_uid = convert.flatten(data['uid'])
    UID_RESOURCE_MAP[flattened_uid] += 1
    data.update({'allocation_order': UID_RESOURCE_MAP[flattened_uid]})

    return data


def parse_log(filename, cmd, snapshots_interval, workload):
    """ Parse raw data in the log file

    :param string filename: name of the log file
    :param string cmd: profiled binary
    :param Decimal snapshots_interval: interval of snapshots [s]
    :returns structure: formatted structure representing section "snapshots" and "global" in memory profile
    """
    interval = snapshots_interval
    with open(filename) as logfile:
        log = logfile.read()
    # allocations are splitted by empty line
    log = log.split('\n\n')

    # Check that there is exit, and the Memory Log is thus not malformed
    glob = log.pop().strip()
    if glob.find('EXIT') == -1:
        raise ValueError

    allocations = []
    for item in log:
        allocations.append(item.splitlines())

    # Collect names and addresses for demangling and addr2line collective call
    names, ips = set(), set()
    for allocation in allocations:
        for resource in allocation[2:]:
            name, ip, offset = resource.split(' ')
            names.add(name)
            ips.add((ip, offset))

    # Build caches for demangle and addr2line for further calls
    syscalls.build_demangle_cache(names)
    syscalls.build_address_to_line_cache(ips, cmd)

    snapshots = []
    data = {}
    data.update({'time': '{0:f}'.format(interval)})
    data.update({'resources': []})
    for allocation in allocations:
        if not allocation:
            continue

        # parsing timestamp,
        # it's the only one number on the 1st line
        time_string = allocation[0]
        # in some cases there is '.' instead of ',' in timestamp
        index = time_string.find(',')
        if index > 0:
            time_string = time_string.replace(',', '.')

        time = Decimal(PATTERN_TIME.search(time_string).group())

        while time > interval:
            snapshots.append(data)
            interval += snapshots_interval
            data = {}
            data.update({'resources': []})
            data.update({'time': '{0:f}'.format(interval)})

        # using parse_resources()
        # parsing resources,
        data['resources'].append(parse_resources(allocation, workload))

    if data:
        snapshots.append(data)

    return {'snapshots': snapshots, 'global': {'resources': []}}


if __name__ == "__main__":
    pass
