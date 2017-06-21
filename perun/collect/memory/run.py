"""This module contains methods needed by Perun logic"""

import os
from decimal import Decimal

import click

import perun.core.logic.runner as runner
import perun.collect.memory.filter as filters
import perun.collect.memory.parsing as parser
from perun.collect.memory.syscalls import run, init
from perun.utils.helpers import CollectStatus

__author__ = 'Radim Podola'
_lib_name = "malloc.so"
_tmp_log_filename = "MemoryLog"


def before(**_):
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


def collect(cmd, args, workload, **_):
    """ Phase for collection of the profile data
    Arguments:
        cmd(string): binary file to profile
        args(string): executing arguments
        workload(string): file that has to be provided to binary

    Returns:
        tuple: (return code, status message, updated kwargs)
    """
    result = run(cmd, args, workload)
    if result:
        error_msg = 'Execution of binary failed with error code: '
        error_msg += str(result)
        return CollectStatus.ERROR, error_msg, {}

    return CollectStatus.OK, '', {}


def after(cmd, **kwargs):
    """ Phase after the collection for minor postprocessing
        that needs to be done after collect
    Arguments:
        cmd(string): binary file to profile
        kwargs(dict): profile's header

    Returns:
        tuple: (return code, message, updated kwargs)

    Fixme: There should be warning raised, when the debugging information is not present. (*)

    (*) When one compiles some application without -g, the profiled binaries WILL generate empty
    profiles, which is not really acceptable. Fix this ASAP!

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
        profile = parser.parse_log(_tmp_log_filename, cmd, sampling)
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


@click.command()
@click.pass_context
def memory(ctx):
    """Runs memory collect, collecting allocation through the program execution"""
    runner.run_collector_from_cli_context(ctx, 'memory', {})
