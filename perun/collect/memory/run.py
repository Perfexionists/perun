"""This module contains methods needed by Perun logic"""

import os

import click

import perun.core.logic.runner as runner
import perun.collect.memory.filter as filters
import perun.collect.memory.parsing as parser
import perun.collect.memory.syscalls as syscalls
import perun.utils.log as log

from perun.utils.helpers import CollectStatus

__author__ = 'Radim Podola'
_lib_name = "malloc.so"
_tmp_log_filename = "MemoryLog"
DEFAULT_SAMPLING = 0.001


def before(cmd, **_):
    """ Phase for initialization the collect module
    Arguments:
        cmd(string): binary file to profile

    Returns:
        tuple: (return code, status message, updated kwargs)
    """
    pwd = os.path.dirname(os.path.abspath(__file__))
    if not os.path.isfile("{}/{}".format(pwd, _lib_name)):
        print("Missing compiled dynamic library 'lib{}'. Compiling from sources: ".format(
            os.path.splitext(_lib_name)[0]
        ), end='')
        result = syscalls.init()
        if result:
            log.failed()
            error_msg = 'Build of the library failed with error code: '
            error_msg += str(result)
            return CollectStatus.ERROR, error_msg, {}
        else:
            log.done()

    print("Checking if binary contains debugging information: ", end='')
    if not syscalls.check_debug_symbols(cmd):
        log.failed()
        error_msg = "Binary does not contain debug info section.\n"
        error_msg += "Please recompile your project with debug options (gcc -g | g++ -g)"
        return CollectStatus.ERROR, error_msg, {}
    log.done()
    print("Finished preprocessing step!\n")

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
    print("Collecting data: ", end='')
    result, collector_errors = syscalls.run(cmd, args, workload)
    if result:
        log.failed()
        error_msg = 'Execution of binary failed with error code: '
        error_msg += str(result) + "\n"
        error_msg += collector_errors
        return CollectStatus.ERROR, error_msg, {}
    log.done()
    print("Finished collection of the raw data!\n")
    return CollectStatus.OK, '', {}


def after(cmd, sampling=DEFAULT_SAMPLING, **kwargs):
    """ Phase after the collection for minor postprocessing
        that needs to be done after collect
    Arguments:
        cmd(string): binary file to profile
        sampling(int): sampling of the collection of the data
        kwargs(dict): profile's header

    Returns:
        tuple: (return code, message, updated kwargs)

    Case studies:
        --sampling=0.1 --no-func=f2 --no-source=s --all
        -> run memory collector with 0.1s sampling,
        excluding allocations in "f2" function and in "s" source file,
        including allocators and unreachable records in call trace

        --no-func=f1 --no-source=s --all
        -> run memory collector with 0.001s sampling,
        excluding allocations in "f1" function and in "s" source file,
        including allocators and unreachable records in call trace

        --no-func=f1 --sampling=1.0
        -> run memory collector with 1.0s sampling,
        excluding allocations in "f1" function,
        excluding allocators and unreachable records in call trace
    """
    include_all = kwargs.get('all', False)
    exclude_funcs = kwargs.get('no_func', None)
    exclude_sources = kwargs.get('no_source', None)

    print("Generating profile: ", end='')
    try:
        profile = parser.parse_log(_tmp_log_filename, cmd, sampling)
    except IndexError as i_err:
        log.failed()
        return CollectStatus.ERROR, 'Info missing in log file: {}'.format(str(i_err)), {}
    except ValueError as v_err:
        log.failed()
        return CollectStatus.ERROR, 'Wrong format of log file: {}'.format(str(v_err)), {}
    log.done()

    if not include_all:
        print("Filtering traces: ", end='')
        filters.remove_allocators(profile)
        filters.trace_filter(profile, function=['?'], source=['unreachable'])
        log.done()

    if exclude_funcs or exclude_sources:
        print("Excluding functions and sources: ", end='')
        filters.allocation_filter(profile, function=[exclude_funcs], source=[exclude_sources])
        log.done()

    print("Clearing records without assigned UID from profile: ", end='')
    filters.remove_uidless_records_from(profile)
    log.done()
    print("")

    return CollectStatus.OK, '', {'profile': profile}


@click.command()
@click.option('--sampling', '-s', default=DEFAULT_SAMPLING,
              help="Profile data sampling interval.")
@click.option('--no-source',
              help="Will exclude the source file from profiling.")
@click.option('--no-func',
              help="Will exclude the function from profiling.")
@click.option('--all', '-a', is_flag=True, default=False,
              help="Will include all allocators and unreachable records in call trace.")
@click.pass_context
def memory(ctx, **kwargs):
    """Runs memory collect, collecting allocation through the program execution"""
    runner.run_collector_from_cli_context(ctx, 'memory', kwargs)
