"""Wrapper for running perf and profiling mostly kernel data"""

from __future__ import annotations

# Standard Imports
from typing import Any
import os
import subprocess
import time

# Third-Party Imports
import click

# Perun Imports
from perun.logic import runner
from perun.profiles.folded import parser
from perun.utils import log
from perun.utils.common import script_kit
from perun.utils.structs.common_structs import CollectStatus, Executable
from perun.utils.external import commands
from perun.utils.exceptions import SuppressedExceptions


def before(**_: Any) -> tuple[CollectStatus, str, dict[str, Any]]:
    """Checks that all dependencies are runnable"""
    log.major_info("Checking for Dependencies")
    # Check that perf can be run
    all_found = True
    if commands.is_executable("perf --help"):
        log.minor_success(f"{log.cmd_style('perf')}", "executable")
    else:
        all_found = False
        log.minor_fail(f"{log.cmd_style('perf')}", "not-executable")

    # Check that helper script can be run
    parse_script = script_kit.get_script("stackcollapse-perf.pl")
    if commands.is_executable(f'echo "" | {parse_script}'):
        log.minor_success(f"{log.cmd_style(parse_script)}", "executable")
    else:
        all_found = False
        log.minor_fail(f"{log.cmd_style(parse_script)}", "not-executable")

    if not all_found:
        log.minor_fail("Checking dependencies")
        return CollectStatus.ERROR, "Some dependencies cannot be run", {}
    else:
        log.minor_success("Checking dependencies")

    return CollectStatus.OK, "", {}


def run_perf(executable: Executable, tag: str, run_with_sudo: bool = False) -> str:
    """Runs perf and obtains the output

    :param executable: run executable profiled by perf
    :param tag: tag that is appended to the log
    :param run_with_sudo: if the command should be run with sudo
    :return: parsed output of perf
    """
    parse_script = script_kit.get_script("stackcollapse-perf.pl")

    if run_with_sudo:
        perf_record_command = f"sudo perf record -q -g -o collected.data {executable}"
        perf_script_command = f"sudo perf script -i collected.data | {parse_script}"
    else:
        perf_record_command = f"perf record -q -g -o collected.data {executable}"
        perf_script_command = f"perf script -i collected.data | {parse_script}"

    try:
        commands.run_safely_external_command(
            perf_record_command, log_verbosity=log.VERBOSE_RELEASE, log_tag=tag
        )
        out, _ = commands.run_safely_external_command(
            perf_script_command, log_verbosity=log.VERBOSE_RELEASE, log_tag=tag
        )
        log.minor_success(f"Raw data from {log.cmd_style(str(executable))}", "collected")
        with SuppressedExceptions(Exception):
            os.remove("collected.data")
    except subprocess.CalledProcessError:
        log.minor_fail(f"Raw data from {log.cmd_style(str(executable))}", "not collected")
        with SuppressedExceptions(Exception):
            os.remove("collected.data")
        return ""
    return out.decode("utf-8")


def collect(executable: Executable, **kwargs: Any) -> tuple[CollectStatus, str, dict[str, Any]]:
    """Runs the workload with perf and transforms it to stack traces"""
    log.major_info("Collecting performance data")
    warmups = kwargs["warmup"]
    repeats = kwargs["repeat"]

    log.minor_info(f"Running {log.highlight(warmups)} warmup iterations")
    for _ in log.progress(range(0, warmups), description="Warmup"):
        run_perf(executable, "warmup", kwargs.get("with_sudo", False))

    log.minor_info(f"Running {log.highlight(repeats)} iterations")
    before_time = time.time()
    kwargs["raw_data"] = []
    for _ in log.progress(range(0, repeats), description="Main Run"):
        output = run_perf(executable, "main_run", kwargs.get("with_sudo", False))
        kwargs["raw_data"].extend(output.splitlines())
    kwargs["time"] = time.time() - before_time

    return CollectStatus.OK, "", kwargs


def after(**kwargs: Any) -> tuple[CollectStatus, str, dict[str, Any]]:
    """Parses the raw data into performance profile"""
    log.major_info("Creating performance profile")
    resources: list[dict[str, str | int]] = []
    parser.parse_resources_from_stream(kwargs["raw_data"], resources)

    if resources:
        log.minor_success("perf events", "parsed")
    else:
        log.warn("possibly empty raw data: no resources were parsed")
        return CollectStatus.OK, "", {}

    kwargs["profile"] = {
        "global": {
            "time": kwargs["time"],
            "resources": resources,
        }
    }
    return CollectStatus.OK, "", kwargs


@click.command()
@click.pass_context
@click.option(
    "--with-sudo", "-s", is_flag=True, help="Runs the profiled command in sudo mode.", default=False
)
@click.option(
    "--warmup",
    "-w",
    default=0,
    type=click.INT,
    help="Runs [INT] warm up iterations of profiled command.",
)
@click.option(
    "--repeat",
    "-r",
    default=1,
    type=click.INT,
    help="Runs [INT] samplings of the profiled command.",
)
def kperf(ctx: click.Context, **kwargs: Any) -> None:
    """Generates kernel sampled traces for specific commands based on perf."""
    runner.run_collector_from_cli_context(ctx, "kperf", kwargs)
