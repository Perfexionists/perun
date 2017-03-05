"""This module provides methods for parsing raw memory data"""

import subprocess
import re
from decimal import Decimal
from perun.collect.memory.syscalls import demangle, address_to_line

__author__ = "Radim Podola"


def demangle(name):
    """
    Arguments:
        name(string): name to demangle

    Returns:
        string: demangled name
    """
    sys_call = ['c++filt']
    sys_call.append(name)
    output = subprocess.check_output(sys_call)

    return output.decode("utf-8").strip()


def get_extern_funcs(filename):
    """
        Arguments:
            filename(string): name of file to inspect for functions

        Returns:
            list: list of functions from dynamic section
    """
    sys_call = ['nm', '-D', '-C']
    sys_call.append(filename)
    output = subprocess.check_output(sys_call)
    output = output.decode("utf-8").splitlines()
    functions = []
    for line in output:
        line = line.strip()
        if line[0] == 'U':
            functions.append(line[2:])

    return functions


def address_to_line(ip, filename):
    """
    Arguments:
        ip(string): instruction pointer value
        filename(string): name of file to inspect for debug information

    Returns:
        list: list of two objects, 1st is the name of the source file,
              2nd is the line number
    """
    sys_call = ['addr2line']
    sys_call.append(ip)
    sys_call.append('-e')
    sys_call.append(filename)
    output = subprocess.check_output(sys_call)

    return output.decode("utf-8").strip().split(':')


def parse_stack(stack, cmd):
    """ Parse stack information of one allocation
    Arguments:
        stack(list): list of raw stack data
        cmd(string): profiled binary

    Returns:
        list: list of formatted structures representing
              stack trace of one allocation
    """
    data = []
    for call in stack:
        call_data = {}

        # parsing name of function,
        # it's the first word in the call record
        func = re.findall(r"\w+", call)[0]
        # demangling name of function
        func = demangle(func)
        call_data.update({'function': func})

        # parsing instruction pointer,
        # it's the first hexadecimal number in the call record
        ip = re.findall(r"0x[0-9a-fA-F]+", call)[0]

        # getting information of instruction pointer,
        # the source file and line number in the source file
        ip_info = address_to_line(ip, cmd)
        if ip_info[0] in ["?", "??"]:
            ip_info[0] = "unreachable"
        if ip_info[1] in ["?", "??"]:
            ip_info[1] = 0
        else:
            ip_info[1] = int(re.findall(r"\d+", ip_info[1])[0])

        call_data.update({'source': ip_info[0]})
        call_data.update({'line': ip_info[1]})

        data.append(call_data)

    return data


def parse_allocation_location(trace):
    """ Parse the location of user's allocation from stack trace
    Arguments:
        trace(list): list representing stack call trace

    Returns:
        dict: first user's call to allocation
    """
    if not trace:
        return {}

    for call in trace:
        source = call['source']
        if source != "unreachable":
            return call

    return {}


def parse_resources(allocation, cmd):
    """ Parse resources of one allocation
    Arguments:
        allocation(list): list of raw allocation data
        cmd(string): profiled binary

    Returns:
        structure: formatted structure representing
                   resources of one allocation
    """
    data = {}

    # parsing amount of allocated memory,
    # it's the first number on the second line
    amount = re.findall(r"\d+", allocation[1])[0]
    data.update({'amount': int(amount)})

    # parsing allocate function,
    # it's the first word on the second line
    allocator = re.findall(r"^\w+", allocation[1])[0]
    data.update({'subtype': allocator})

    # parsing address of allocated memory,
    # it's the second number on the second line
    address = re.findall(r"\d+", allocation[1])[1]
    data.update({'address': int(address)})

    # parsing stack in the moment of allocation
    # to getting trace of it
    trace = parse_stack(allocation[2:], cmd)
    data.update({'trace': trace})

# TODO
    data.update({'type': 'memory'})

    # parsing call trace to get first user call
    # to allocation function
    data.update({'uid': parse_allocation_location(trace)})

    return data


def parse_log(logfile, cmd, snapshots_interval=Decimal('0.001')):
    """ Parse raw data in the log file
    Arguments:
        logfile(string): name of the log file
        cmd(string): profiled binary
        snapshots_interval(Decimal): interval of snapshots [s]

    Returns:
        structure: formatted structure representing
                   section "snapshots" and "global" in memory profile
    """
    interval = snapshots_interval
    with open(logfile) as f:
        log = f.read()

    log = log.split('\n\n')

    glob = log.pop().strip()
    if glob.find('EXIT') > -1:
        glob = [{'time': re.findall(r"\d+\.\d+", glob)[0]}]
    else:
        raise ValueError

    allocations = []
    for item in log:
        allocations.append(item.splitlines())

    snapshots = []
    data = {}
    data.update({'time': '{0:f}'.format(interval)})
    data.update({'resources': []})
    for allocation in allocations:
        if not allocation:
            continue

        # parsing timestamp,
        # it's the only one number on the line
        time = Decimal(re.findall(r"\d+\.\d+", allocation[0])[0])

        while time > interval:
            snapshots.append(data)
            interval += snapshots_interval
            data = {}
            data.update({'resources': []})
            data.update({'time': '{0:f}'.format(interval)})

        # using parse_resources()
        # parsing resources,
        data['resources'].append(parse_resources(allocation, cmd))

    if data:
        snapshots.append(data)

    glob[0].update({'resources': [snapshots[-1]['resources'][-1]]})

    return {'snapshots': snapshots, 'global': glob}


if __name__ == "__main__":
    pass
