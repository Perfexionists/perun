"""Wrapper for running perf and profiling mostly kernel data"""
from __future__ import annotations

# Standard Imports
import os
import subprocess
from pathlib import Path
from typing import Any

# Third-Party Imports
import click

# Perun Imports
from perun.collect.kperf import parser
from perun.logic import runner
from perun.utils import log
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
    script_dir = Path(Path(__file__).resolve().parent, "scripts")
    parse_script = os.path.join(script_dir, "stackcollapse-perf.pl")
    if commands.is_executable(f'echo "" | {parse_script}'):
        log.minor_success(f"{log.cmd_style(parse_script)}", "executable")
    else:
        all_found = False
        log.minor_fail(f"{log.cmd_style(parse_script)}", "not-executable")

    if not all_found:
        log.minor_fail("Checking dependencies")
        return CollectStatus.ERROR, "Some depedencies cannot be run", {}
    else:
        log.minor_success("Checking dependencies")

    return CollectStatus.OK, "", {}


def collect(executable: Executable, **kwargs: Any) -> tuple[CollectStatus, str, dict[str, Any]]:
    """Runs the workload with perf and transforms it to stack traces"""
    log.major_info("Collecting performance data")
    script_dir = Path(Path(__file__).resolve().parent, "scripts")
    parse_script = os.path.join(script_dir, "stackcollapse-perf.pl")

    if kwargs.get("with_sudo", False):
        perf_record_command = f"perf record -q -g -o collected.data {executable}"
        perf_script_command = f"perf script -i collected.data | {parse_script}"
    else:
        perf_record_command = f"sudo perf record -q -g -o collected.data {executable}"
        perf_script_command = f"sudo perf script -i collected.data | {parse_script}"

    try:
        commands.run_safely_external_command(perf_record_command)
        out, err = commands.run_safely_external_command(perf_script_command)
        log.minor_success(f"Raw data from {log.cmd_style(executable)}", "collected")
    except subprocess.CalledProcessError:
        log.minor_fail(f"Raw data from {log.cmd_style(executable)}", "not collected")
        return CollectStatus.ERROR, "Command failed", {}
    kwargs["raw_data"] = out.decode("utf-8")
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
            "time": "TODO",
            "resources": resources,
        }
    }
    return CollectStatus.OK, "", kwargs


@click.command()
@click.pass_context
def kperf(ctx: click.Context, **kwargs: Any) -> None:
    """Generates kernel sampled traces for specific commands based on perf."""
    runner.run_collector_from_cli_context(ctx, "kperf", kwargs)
