"""This module provides wrapper for the Flame graph visualization"""
from __future__ import annotations

# Standard Imports
from typing import TYPE_CHECKING
import os
import subprocess

# Third-Party Imports

# Perun Imports
from perun.profile import convert
from perun.utils.common import common_kit

if TYPE_CHECKING:
    from perun.profile.factory import Profile

_SCRIPT_FILENAME = "./flamegraph.pl"


def draw_flame_graph(profile: Profile, output_file: str, height: int) -> None:
    """Draw Flame graph from profile.

        To create Flame graphs we use perl script created by Brendan Gregg.
        https://github.com/brendangregg/FlameGraph/blob/master/flamegraph.pl

    :param dict profile: the memory profile
    :param str output_file: filename of the output file, expected is SVG format
    :param int height: graphs height
    """
    # converting profile format to format suitable to Flame graph visualization
    flame = convert.to_flame_graph_format(profile)

    header = profile["header"]
    profile_type = header["type"]
    cmd, workload = (header["cmd"], header["workload"])
    title = f"{profile_type} consumption of {cmd} {workload}"
    units = header["units"][profile_type]

    pwd = os.path.dirname(os.path.abspath(__file__))
    with open(output_file, "w") as out:
        process = subprocess.Popen(
            [
                _SCRIPT_FILENAME,
                "--title",
                title,
                "--countname",
                units,
                "--reverse",
                "--height",
                str(height),
            ],
            stdin=subprocess.PIPE,
            stdout=out,
            cwd=pwd,
        )
        process.communicate(bytes("".join(flame), encoding="UTF-8"))
