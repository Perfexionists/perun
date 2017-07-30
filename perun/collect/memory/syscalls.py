"""This module provides simple wrappers over some linux command line tools"""

import os
import re
import subprocess
import perun.utils.log as log

PATTERN_WORD = re.compile(r"(\w+)|[?]")
PATTERN_HEXADECIMAL = re.compile(r"0x[0-9a-fA-F]+")

__author__ = "Radim Podola"

demangle_cache = {}
address_to_line_cache = {}


def build_demangle_cache(names):
    """Builds global cache for demangle() function calls.

    Instead of continuous calls to subprocess, this takes all of the collected names
    and calls the demangle just once, while constructing the cache.

    Arguments:
        names(set): set of names that will be demangled in future
    """
    global demangle_cache

    list_of_names = list(names)
    if not all(map(PATTERN_WORD.match, list_of_names)):
        log.error("incorrect values in demangled names")
    else:
        sys_call = ['c++filt'] + list_of_names
        output = subprocess.check_output(sys_call).decode("utf-8").strip()
        demangle_cache = dict(zip(list_of_names, output.split("\n")))


def demangle(name):
    """
    Arguments:
        name(string): name to demangle

    Returns:
        string: demangled name
    """
    return demangle_cache[name]


def build_address_to_line_cache(addresses, binary_name):
    """Builds global cache for address_to_line() function calls.

    Instead of continuous calls to subprocess, this takes all of the collected
    names and calls the addr2line just once.

    Arguments:
        addresses(set): set of addresses that will be translated to line info
        binary_name(str): name of the binary which will be parsed for info
    """
    global address_to_line_cache

    list_of_addresses = list(addresses)
    if not all(map(PATTERN_HEXADECIMAL.match, list_of_addresses)):
        log.error("incorrect values in address translations")
    else:
        sys_call = ['addr2line', '-e', binary_name] + list_of_addresses
        output = subprocess.check_output(sys_call).decode("utf-8").strip()
        address_to_line_cache = dict(zip(
            list_of_addresses, map(lambda x: x.split(':'), output.split("\n"))
        ))


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


def address_to_line(ip):
    """
    Arguments:
        ip(string): instruction pointer value

    Returns:
        list: list of two objects, 1st is the name of the source file,
              2nd is the line number
    """
    return address_to_line_cache[ip][:]


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
