import sys
import subprocess
import json
import re

__author__ = "Radim Podola"


def demangle(name):
    """
    Arguments:
        name(string): name to demangle

    Returns:
        string: demangled name
    """
    syscall = ['c++filt']
    syscall.append(name)
    output = subprocess.check_output(syscall)

    return output.decode("utf-8").strip()


def get_extern_funcs(filename):
    """
        Arguments:
            filename(string): name of file to inspect for functions

        Returns:
            list: list of functions from dynamic section
    """
    syscall = ['nm', '-D', '-C']
    syscall.append(filename)
    output = subprocess.check_output(syscall)
    output = output.decode("utf-8").splitlines()
    fs = []
    for line in output:
        line = line.strip()
        if(line[0] == 'U'):
            fs.append(line[2:])

    return fs


def address_to_line(ip, filename):
    """
    Arguments:
        ip(string): instruction pointer value
        filename(string): name of file to inspect for debug information

    Returns:
        list: list of two objects, 1st is the name of the source file,
              2nd is the line number
    """
    syscall = ['addr2line']
    syscall.append(ip)
    syscall.append('-e')
    syscall.append(filename)
    output = subprocess.check_output(syscall)

    return output.decode("utf-8").strip().split(':')


def parse_stack(stack):
    """ Parse stack information of one allocation
    Arguments:
        stack(list): list of raw stack data

    Returns:
        list: list of formatted structures representing
              stack trace of one allocation
    """
    data = []
    for call in stack:
        call_data = {}

        # parsing name of function,
        # it's the first word in the call record
        func = re.findall("\w+", call)[0]
        # demangling name of function
        func = demangle(func)
        call_data.update({'function': func})

        # parsing instruction pointer,
        # it's the first hexadecimal number in the call record
        ip = re.findall("0x[0-9a-fA-F]+", call)[0]

        # getting information of instruction pointer,
        # the source file and line number in the source file
        ip_info = address_to_line(ip, binary_file)
        if ip_info[0] in ["?", "??"]:
            ip_info[0] = "unreachable"
        if ip_info[1] in ["?", "??"]:
            ip_info[1] = 0
        else:
            ip_info[1] = int(re.findall("\d+", ip_info[1])[0])

        call_data.update({'source': ip_info[0]})
        call_data.update({'line': ip_info[1]})

        data.append(call_data)

    return data


def parse_resources(allocation):
    """ Parse resources of one allocation
    Arguments:
        allocation(list): list of raw allocation data

    Returns:
        structure: formatted structure representing
                   resources of one allocation

    """
    data = {}

    # parsing amount of allocated memory,
    # it's the first number on the second line
    amount = re.findall("\d+", allocation[1])[0]
    data.update({'amount': int(amount)})

    # parsing allocate function,
    # it's the first word on the second line
    allocator = re.findall("^\w+", allocation[1])[0]
    data.update({'allocator': allocator})

    # parsing address of allocated memory,
    # it's the second number on the second line
    address = re.findall("\d+", allocation[1])[1]
    data.update({'address': int(address)})

    # parsing stack in the moment of allocation
    # to getting trace of it
    trace = parse_stack(allocation[2:])
    data.update({'trace': trace})

    return data


def parse_log(logfile, snapshots_interval=1.0):
    """ Parse raw data in the log file
    Arguments:
        logfile(string): name of the log file
        snapshots_interval(float): interval of snapshots [s]

    Returns:
        structure: formatted structure representing
                   section "snapshots" in memory profile
    """
    interval = snapshots_interval
    with open(logfile) as f:
        file = f.read()

    file = file.split('\n\n')

    allocations = []
    for item in file:
        allocations.append(item.splitlines())

    snapshots = []
    data = {}
    data.update({'time': interval})
    data.update({'resources': []})
    for allocation in allocations:
        if not allocation:
            continue

        # parsing timestamp,
        # it's the only one number on the line
        time = float(re.findall("\d+\.\d+", allocation[0])[0])

        if time > interval:
            snapshots.append(data)
            interval += snapshots_interval
            data = {}
            data.update({'resources': []})
            data.update({'time': interval})

        # using parse_resources()
        # parsing resources,
        data['resources'].append(parse_resources(allocation))

    if data:
        snapshots.append(data)

    return snapshots


def calculate_global(data):
    return {}


def update_profile(logfile, filename, snapshots_interval=1.0):
    """
    Arguments:
        logfile(string): name of log file
        filename(string): name of file to update profiling information
        snapshots_interval(float): interval of snapshots [s]

    Returns:
        bool: True if log was successfully updated, False if not
    """
    try:
        with open(filename) as f:
            profile = json.load(f)
    except IOError:
        return False

    profile['snapshots'] = parse_log(logfile, snapshots_interval)
    profile['global'] = calculate_global(profile['snapshots'])

    try:
        with open(filename, mode='w') as f:
            json.dump(profile, f, indent=2)
        print(json.dumps(profile, indent=2))
    except IOError:
        return False

    return True


binary_file = 'test'
update_profile('MemoryLog', 'memory.perf', 0.001)

"""
TODO:
Upravit log z C aby se to líp parsovalo
    -trasu jen čísla
    -u free položka 0B
"""


"""
print(demangle('_ZNKSt7__cxx1112basic_stringIwSt11char_traitsIwESaIwEE6substrEmm'))
print(get_extern_funcs('test'))

localization =  address_to_line('400605', 'test')
print('soubor: ' + localization[0])
print('řádek: ', localization[1])
"""
