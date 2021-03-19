"""This module provides simple wrappers over some linux command line tools"""

import os
import re
import subprocess
import perun.utils.log as log
from perun.utils.helpers import SuppressedExceptions

PATTERN_WORD = re.compile(r"(\w+)|[?]")
PATTERN_HEXADECIMAL = re.compile(r"0x[0-9a-fA-F]+")

__author__ = "Radim Podola"

demangle_cache = {}
address_to_line_cache = {}


def build_demangle_cache(names):
    """Builds global cache for demangle() function calls.

    Instead of continuous calls to subprocess, this takes all of the collected names
    and calls the demangle just once, while constructing the cache.

    :param set names: set of names that will be demangled in future
    """
    global demangle_cache

    list_of_names = [name for name in names if PATTERN_WORD.match(name)]
    sys_call = ['c++filt'] + list_of_names
    output = subprocess.check_output(sys_call).decode("utf-8").strip()
    demangle_cache = dict(zip(list_of_names, output.split("\n")))


def demangle(name):
    """
    :param string name: name to demangle
    :returns string: demangled name
    """
    return demangle_cache[name]


def build_address_to_line_cache(addresses, binary_name):
    """Builds global cache for address_to_line() function calls.

    Instead of continuous calls to subprocess, this takes all of the collected
    names and calls the addr2line just once.

    :param set addresses: set of addresses that will be translated to line info
    :param str binary_name: name of the binary which will be parsed for info
    """
    global address_to_line_cache

    list_of_addresses = [a[0] for a in addresses if PATTERN_HEXADECIMAL.match(a[0])]

    sys_call = ['addr2line', '-e', binary_name] + list_of_addresses
    output = subprocess.check_output(sys_call).decode("utf-8").strip()
    address_to_line_cache = dict(zip(
        list_of_addresses, map(lambda x: x.split(':'), output.split("\n"))
    ))


def address_to_line(ip):
    """
    :param string ip: instruction pointer value
    :returns list: list of two objects, 1st is the name of the source file, 2nd is the line number
    """
    return address_to_line_cache[ip][:]


def run(executable):
    """
    :param Executable executable: executable command
    :returns int: return code of executed binary
    """
    pwd = os.path.dirname(os.path.abspath(__file__))
    sys_call = ('LD_PRELOAD="' + pwd + '/malloc.so" ' + str(executable))

    with open('ErrorCollectLog', 'w') as error_log:
        ret = subprocess.call(sys_call, shell=True, stderr=error_log)

    with open('ErrorCollectLog', 'r') as error_log:
        error_log = error_log.readlines()

    return ret, "".join(error_log)


def init():
    """ Initialize the injected library

    :returns bool: success of the operation
    """
    pwd = os.path.dirname(os.path.abspath(__file__))
    ret = 1
    with SuppressedExceptions(subprocess.CalledProcessError):
        ret = subprocess.call(["make"], cwd=pwd)

    return ret


def check_debug_symbols(cmd):
    """ Check if binary was compiled with debug symbols

    :param string cmd: binary file to profile
    :returns bool: True if binary was compiled with debug symbols
    """
    with SuppressedExceptions(subprocess.CalledProcessError):
        output = subprocess.check_output(["objdump", "-h", cmd])
        raw_output = output.decode("utf-8")
        if re.search("debug", raw_output):
            return True
    return False
