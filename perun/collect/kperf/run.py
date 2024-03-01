"""Wrapper for running perf and profiling mostly kernel data"""
from __future__ import annotations

# Standard Imports
from typing import Any

# Third-Party Imports
import click

# Perun Imports
from perun.logic import runner
from perun.utils import log
from perun.utils.structs import Executable, CollectStatus


def before(**kwargs: Any) -> tuple[CollectStatus, str, dict[str, Any]]:
    log.major_info("Checking for Dependencies")
    return CollectStatus.OK, "", {}


def collect(executable: Executable, **_: Any) -> tuple[CollectStatus, str, dict[str, Any]]:
    log.major_info("Collecting performance data")
    return CollectStatus.OK, "", {}


def after(**kwargs: Any) -> tuple[CollectStatus, str, dict[str, Any]]:
    log.major_info("Creating performance profile")
    return CollectStatus.OK, "", {}


@click.command()
@click.pass_context
def kperf(ctx: click.Context, **kwargs: Any) -> None:
    """Generates kernel sampled traces for specific commands based on perf."""
    runner.run_collector_from_cli_context(ctx, "kperf", kwargs)
