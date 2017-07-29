"""This module provides simple wrappers over some linux command line tools"""

import os
import re
import subprocess

__author__ = "Radim Podola"

demangle_cache = {}
address_to_line_cache = {}


def demangle(name):
    """
    Arguments:
        name(string): name to demangle

    Returns:
        string: demangled name
    """
    # Fixme: This could be called just once...
    if name not in demangle_cache.keys():
        sys_call = ['c++filt', name]
        output = subprocess.check_output(sys_call)
        demangle_cache[name] = output.decode("utf-8").strip()

    return demangle_cache[name]


def get_extern_funcs(filename):
    """
    Arguments:
        filename(string): name of file to inspect for functions

    Returns:
        list: list of functions from dynamic section
    """
    sys_call = ['nm', '-D', '-C', filename]
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
    # Fixme: This could be called just once...
    key = ":".join([ip, filename])
    if key not in address_to_line_cache.keys():
        sys_call = ['addr2line', ip, '-e', filename]
        output = subprocess.check_output(sys_call)

        address_to_line_cache[key] = output.decode("utf-8").strip().split(':')

    return address_to_line_cache[key][:]


def run(cmd, params, workload):
    """
    Arguments:
        cmd(string): binary file to profile
        params(string): executing arguments
        workload(string): file that has to be provided to binary

    Returns:
        int: return code of executed binary
    """
    pwd = os.path.dirname(os.path.abspath(__file__))
    sys_call = ('LD_PRELOAD="' + pwd + '/malloc.so" ' + cmd +
                ' ' + params + ' ' + workload)

    with open('ErrorCollectLog', 'w') as error_log:
        ret = subprocess.call(sys_call, shell=True, stderr=error_log)

    with open('ErrorCollectLog', 'r') as error_log:
        log = error_log.readlines()

    return ret, "".join(log)


def init():
    """ Initialize the injected library

    Returns:
        bool: success of the operation
    """
    pwd = os.path.dirname(os.path.abspath(__file__))
    try:
        ret = subprocess.call(["make"], cwd=pwd)
    except subprocess.CalledProcessError:
        return 1

    return ret


def check_debug_symbols(cmd):
    """ Check if binary was compiled with debug symbols

    Arguments:
        cmd(string): binary file to profile

    Returns:
        bool: True if binary was compiled with debug symbols
    """
    try:
        output = subprocess.check_output(["objdump", "-h", cmd])
        raw_output = output.decode("utf-8")
        if re.search("debug", raw_output) is None:
            return False
    except subprocess.CalledProcessError:
        return False

    return True


if __name__ == "__main__":
    pass
