"""This module contains methods needed by Perun logic"""
import os
from decimal import Decimal
import perun.collect.memory.filter as filters
import perun.collect.memory.parsing as parser
from perun.collect.memory.syscalls import run, init
from perun.utils.helpers import CollectStatus

__author__ = 'Radim Podola'
_lib_name = "malloc.so"
_tmp_log_filename = "MemoryLog"


def before(**kwargs):
    """ Phase for initialization the collect module

    Returns:
        tuple: (return code, status message, updated kwargs)
    """
    pwd = os.path.dirname(os.path.abspath(__file__))
    if not os.path.isfile("{}/{}".format(pwd, _lib_name)):
        result = init()
        if result:
            error_msg = 'Build of the library failed with error code: '
            error_msg += str(result)
            return CollectStatus.ERROR, error_msg, {}

    return CollectStatus.OK, '', {}


def collect(bin, args, workload, **kwargs):
    """ Phase for collection of the profile data
    Arguments:
        bin(string): binary file to profile
        args(string): executing arguments
        workload(string): file that has to be provided to binary
        kwargs(dict): profile's header

    Returns:
        tuple: (return code, status message, updated kwargs)
    """
    result = run(bin, args, workload)
    if result:
        error_msg = 'Execution of binary failed with error code: '
        error_msg += str(result)
        return CollectStatus.ERROR, error_msg, {}

    return CollectStatus.OK, '', {}


def after(bin, **kwargs):
    """ Phase after the collection for minor postprocessing
        that needs to be done after collect
    Arguments:
        collect_params(string): execution parameters of collector
        bin(string): binary file to profile
        kwargs(dict): profile's header

    Returns:
        tuple: (return code, message, updated kwargs)

    Case studies:
        --sampling=0.1 --no-func=f1 --no-func=f2 --no-source=s --all
        -> run memory collector with 0.1s sampling,
        excluding allocations in "f1", "f2" functions and in "s" source file,
        including allocators and unreachable records in call trace

        --no-func=f1 --no-source=s --all
        -> run memory collector with 0.0001s sampling,
        excluding allocations in "f1" function and in "s" source file,
        including allocators and unreachable records in call trace

        --no-func=f1 --sampling=1.0
        -> run memory collector with 1.1s sampling,
        excluding allocations in "f1" function,
        excluding allocators and unreachable records in call trace
    """
    if 'sampling' in kwargs.keys():
        sampling = Decimal(str(kwargs['sampling']))
    else:
        sampling = Decimal('0.001')

    include_all = 'all' in kwargs.keys()

    exclude_funcs = kwargs.get('no-func', [])
    if exclude_funcs is None:
        exclude_funcs = []

    exclude_sources = kwargs.get('no-source', [])
    if exclude_sources is None:
        exclude_sources = []

    try:
        profile = parser.parse_log(_tmp_log_filename, bin, sampling)
    except IndexError:
        return CollectStatus.ERROR, 'Info missing in log file', {}
    except ValueError:
        return CollectStatus.ERROR, 'Wrong format of log file', {}

    if not include_all:
        filters.remove_allocators(profile)
        filters.trace_filter(profile, function=['?'], source=['unreachable'])

    if exclude_funcs or exclude_sources:
        filters.allocation_filter(profile, function=exclude_funcs,
                                  source=exclude_sources)

    filters.clear_profile(profile)

    return CollectStatus.OK, '', {'profile': profile}


if __name__ == "__main__":
    pass
