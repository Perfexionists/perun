"""This module provides simple wrappers over some linux command line tools"""
import subprocess


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
