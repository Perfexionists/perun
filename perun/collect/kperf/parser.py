"""
Contains helper functions for parsing information from perf
"""

from __future__ import annotations

# Standard Imports
from typing import Any

# Third-Party Imports

# Perun Imports
from perun.utils import log


def parse_events(perf_events: list[str]) -> list[dict[str, Any]]:
    """Parses perf events into a list of resources

    Each resource is identified by its topmost called function (uid),
    and contains traces and unit (the bottom function). For each
    function we count the number of samples.

    :param perf_events: string with perf events
    :return: list of resources
    """
    resources = []
    for event in log.progress(perf_events, description="Parsing Events"):
        if event.strip():
            *record, samples = event.split(" ")
            parts = " ".join(record).split(";")
            command, trace, uid = parts[0], parts[0:-1], parts[-1]
            resources.append(
                {
                    "amount": int(samples),
                    "uid": uid,
                    "command": command,
                    "trace": [{"func": f} for f in trace],
                }
            )
    return resources
