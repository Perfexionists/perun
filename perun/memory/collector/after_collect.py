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


def parse_log(filename):
    """
    Arguments:
        filename(string): name of the log file
    """
    with open(filename) as f:
        file = f.read()

    file = file.split('\n\n')
    allocs = []
    for i in file:
        allocs.append(i.splitlines())

    data = {'type' : 'memory', 'metadata' : []}

    for alloc in allocs:
        item = {}
        if not alloc:
            continue

        time = re.findall("\d+\.\d+", alloc[0])[0]
        item.update({'timestamp' : float(time)})

        allocator = re.findall("^\w+", alloc[1])[0]
        item.update({'allocator': allocator})

        data['metadata'].append(item)


    print(json.dumps(data, indent=4))


parse_log('MemoryLog')

"""
print(demangle('_ZNKSt7__cxx1112basic_stringIwSt11char_traitsIwESaIwEE6substrEmm'))
print(get_extern_funcs('test'))

localization =  address_to_line('400605', 'test')
print('soubor: ' + localization[0])
print('řádek: ', localization[1])
"""

