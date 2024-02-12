"""This module contains methods needed by Perun logic"""
from __future__ import annotations

# Standard Imports
import os
from typing import Any

# Third-Party Imports
import click

# Perun Imports
from perun.collect.memory import filter as filters, parsing as parser, syscalls
from perun.logic import runner
from perun.utils import log
from perun.utils.structs import CollectStatus, Executable


_lib_name: str = "malloc.so"
_tmp_log_filename: str = "MemoryLog"
DEFAULT_SAMPLING: float = 0.001


def before(executable: Executable, **_: Any) -> tuple[CollectStatus, str, dict[str, Any]]:
    """Phase for initialization the collect module

    :param Executable executable: executable profiled command
    :returns tuple: (return code, status message, updated kwargs)
    """
    log.major_info("Building Instrumented Binary")
    pwd = os.path.dirname(os.path.abspath(__file__))
    if not os.path.isfile(os.path.join(pwd, _lib_name)):
        log.minor_fail(
            f"Dynamic library {log.path_style('lib' + os.path.splitext(_lib_name)[0])}", "not found"
        )
        result = syscalls.init()
        if result:
            log.minor_fail("Compiling from sources")
            error_msg = "Build of the library failed with error code: "
            error_msg += str(result)
            return CollectStatus.ERROR, error_msg, {}
        else:
            log.minor_success("Compiling from sources")
    else:
        log.minor_success(
            f"Dynamic library {log.path_style('lib' + os.path.splitext(_lib_name)[0])}", "found"
        )

    if not syscalls.check_debug_symbols(executable.cmd):
        log.minor_fail("Checking if binary contains debugging info", "not found")
        error_msg = "Binary does not contain debug info section. "
        error_msg += (
            f"Please recompile your project with debug options {log.cmd_style('(gcc -g | g++ -g)')}"
        )
        return CollectStatus.ERROR, error_msg, {}
    log.minor_success("Checking if binary contains debugging info", "found")

    return CollectStatus.OK, "", {}


def collect(executable: Executable, **_: Any) -> tuple[CollectStatus, str, dict[str, Any]]:
    """Phase for collection of the profile data

    :param Executable executable: executable profiled command
    :returns tuple: (return code, status message, updated kwargs)
    """
    log.major_info("Collecting Performance data")
    result, collector_errors = syscalls.run(executable)
    if result:
        log.minor_fail("Collection of the raw data")
        error_msg = "Execution of binary failed with error code: "
        error_msg += str(result) + "\n"
        error_msg += collector_errors
        return CollectStatus.ERROR, error_msg, {}
    log.minor_success("Collection of the raw data")
    return CollectStatus.OK, "", {}


def after(
    executable: Executable, sampling: float = DEFAULT_SAMPLING, **kwargs: Any
) -> tuple[CollectStatus, str, dict[str, Any]]:
    """Phase after the collection for minor postprocessing
        that needs to be done after collect

    :param Executable executable: executable profiled command
    :param int sampling: sampling of the collection of the data
    :param dict kwargs: profile's header
    :returns tuple: (return code, message, updated kwargs)

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
    log.major_info("Creating Profile")
    include_all = kwargs.get("all", False)
    exclude_funcs = kwargs.get("no_func", [])
    exclude_sources = kwargs.get("no_source", [])

    try:
        profile = parser.parse_log(_tmp_log_filename, executable, sampling)
    except (IndexError, ValueError) as parse_err:
        log.minor_fail("Parsing of log")
        return (
            CollectStatus.ERROR,
            f"Could not parse the log file due to: {parse_err}",
            {},
        )
    log.minor_success("Parsing of log")
    filters.set_global_region(profile)

    if not include_all:
        filters.remove_allocators(profile)
        filters.trace_filter(profile, function=["?"], source=["unreachable"])
        log.minor_success("Filtering traces")

    if exclude_funcs or exclude_sources:
        filters.allocation_filter(profile, function=exclude_funcs, source=exclude_sources)
        log.minor_success("Excluding functions")

    filters.remove_uidless_records_from(profile)
    log.minor_success("Removing unassigned records")

    return CollectStatus.OK, "", {"profile": profile}


@click.command()
@click.option(
    "--sampling",
    "-s",
    default=DEFAULT_SAMPLING,
    type=click.FLOAT,
    help=(
        "Sets the sampling interval for profiling the allocations."
        " I.e. memory snapshots will be collected each <sampling>"
        " seconds."
    ),
)
@click.option(
    "--no-source",
    multiple=True,
    help="Will exclude allocations done from <no_source> file during the profiling.",
)
@click.option(
    "--no-func",
    multiple=True,
    help="Will exclude allocations done by <no func> function during the profiling.",
)
@click.option(
    "--all",
    "-a",
    is_flag=True,
    default=False,
    help=(
        "Will record the full trace for each allocation, i.e. it"
        " will include all allocators and even unreachable records."
    ),
)
@click.pass_context
def memory(ctx: click.Context, **kwargs: Any) -> None:
    """Generates `memory` performance profile, capturing memory allocations of
    different types along with target address and full call trace.

    \b
      * **Limitations**: C/C++ binaries
      * **Metric**: `memory`
      * **Dependencies**: ``libunwind.so`` and custom ``libmalloc.so``
      * **Default units**: `B` for `memory`

    The following snippet shows the example of resources collected by `memory`
    profiler. It captures allocations done by functions with more detailed
    description, such as the type of allocation, trace, etc.

    .. code-block:: json

        \b
        {
            "type": "memory",
            "subtype": "malloc",
            "address": 19284560,
            "amount": 4,
            "trace": [
                {
                    "source": "../memory_collect_test.c",
                    "function": "main",
                    "line": 22
                },
            ],
            "uid": {
                "source": "../memory_collect_test.c",
                "function": "main",
                "line": 22
            }
        },

    Refer to :ref:`collectors-memory` for more thorough description and
    examples of `memory` collector.
    """
    runner.run_collector_from_cli_context(ctx, "memory", kwargs)
