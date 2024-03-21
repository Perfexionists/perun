"""Wrapper for running perf and profiling mostly kernel data"""
from __future__ import annotations

# Standard Imports
from typing import Any
import subprocess
import time

# Third-Party Imports
import click
import progressbar

# Perun Imports
from perun.collect.kperf import parser
from perun.logic import runner
from perun.utils import log
from perun.utils.common import script_kit
from perun.utils.structs import Executable, CollectStatus
from perun.utils.external import commands


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


def run_perf(executable: Executable, run_with_sudo: bool = False) -> str:
    """Runs perf and obtains the output

    :param executable: run executable profiled by perf
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
        commands.run_safely_external_command(perf_record_command)
        out, _ = commands.run_safely_external_command(perf_script_command)
        log.minor_success(f"Raw data from {log.cmd_style(str(executable))}", "collected")
    except subprocess.CalledProcessError:
        log.minor_fail(f"Raw data from {log.cmd_style(str(executable))}", "not collected")
        return ""
    return out.decode("utf-8")


def collect(executable: Executable, **kwargs: Any) -> tuple[CollectStatus, str, dict[str, Any]]:
    """Runs the workload with perf and transforms it to stack traces"""
    log.major_info("Collecting performance data")
    warmups = kwargs["warmup"]
    repeats = kwargs["repeat"]

    log.minor_info(f"Running {log.highlight(warmups)} warmup iterations")
    for _ in progressbar.progressbar(range(0, warmups)):
        run_perf(executable, kwargs.get("with_sudo", False))

    log.minor_info(f"Running {log.highlight(repeats)} iterations")
    before_time = time.time()
    kwargs["raw_data"] = []
    for _ in progressbar.progressbar(range(0, repeats)):
        output = run_perf(executable, kwargs.get("with_sudo", False))
        kwargs["raw_data"].extend(output.splitlines())
    kwargs["time"] = time.time() - before_time

    return CollectStatus.OK, "", kwargs


def after(**kwargs: Any) -> tuple[CollectStatus, str, dict[str, Any]]:
    """Parses the raw data into performance profile"""
    log.major_info("Creating performance profile")
    resources = parser.parse_events(kwargs["raw_data"])

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
    default=3,
    type=click.INT,
    help="Runs [INT] warm up iterations of profiled command.",
)
@click.option(
    "--repeat",
    "-r",
    default=5,
    type=click.INT,
    help="Runs [INT] samplings of the profiled command.",
)
def kperf(ctx: click.Context, **kwargs: Any) -> None:
    """Generates kernel sampled traces for specific commands based on perf."""
    runner.run_collector_from_cli_context(ctx, "kperf", kwargs)
