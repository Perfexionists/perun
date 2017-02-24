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
        list: list of two objects, 1st is name of the source file, 2nd is line number
    """
    syscall = ['addr2line']
    syscall.append(ip)
    syscall.append('-e')
    syscall.append(filename)
    output = subprocess.check_output(syscall)

    return output.decode("utf-8").strip().split(':')


def parse_log(logfile):
    """
    Arguments:
        logfile(string): name of the log file

    Returns:
        structure: parsed metadata
    """
    with open(logfile) as f:
        file = f.read()
        f.close()
    file = file.split('\n\n')

    allocations = []
    for item in file:
        allocations.append(item.splitlines())

    snapshots = []
    for allocation in allocations:
        data = {}
        if not allocation:
            continue

        time = re.findall("\d+\.\d+", allocation[0])[0]
        data.update({'time' : format('%fs' %float(time))})

        allocator = re.findall("^\w+", allocation[1])[0]
        data.update({'allocator': allocator})

        if allocator == 'free':
            amount = 0
        else:
            amount = re.findall("\d+", allocation[1])[0]
        data.update({'amount': format('%iB' %int(amount))})

        location = 'loc'
        data.update({'location': location})

        snapshots.append(data)

    return snapshots


def calculate_global(data):
    return {}

def update_profile(logfile, filename):
    """
    Arguments:
        logfile(string): name of log file
        filename(string): name of file to update profiling information

    Returns:
        bool: True if log was successfully updated, False if not
    """
    try:
        with open(filename) as f:
            profile = json.load(f)
            f.close()
    except IOError:
        return False

    profile['snapshots'] = parse_log(logfile)
    profile['global'] = calculate_global(profile['snapshots'])

    try:
        with open(filename, mode='w') as f:
            json.dump(profile, f, indent=2)
            f.close()
    except IOError:
        return False

    return True


update_profile('MemoryLog', 'memory.perf')


"""
print(demangle('_ZNKSt7__cxx1112basic_stringIwSt11char_traitsIwESaIwEE6substrEmm'))
print(get_extern_funcs('test'))

localization =  address_to_line('400605', 'test')
print('soubor: ' + localization[0])
print('řádek: ', localization[1])
"""

