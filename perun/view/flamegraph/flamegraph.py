"""This module provides wrapper for the Flame graph visualization"""
from __future__ import annotations

import subprocess

# Standard Imports
from typing import TYPE_CHECKING
import os
import tempfile

# Third-Party Imports

# Perun Imports
from perun.profile import convert
from perun.utils.external import commands

if TYPE_CHECKING:
    from perun.profile.factory import Profile

_SCRIPT_FILENAME = "flamegraph.pl"


def draw_flame_graph(profile: Profile, height: int, width: int = 1200) -> str:
    """Draw Flame graph from profile.

        To create Flame graphs we use perl script created by Brendan Gregg.
        https://github.com/brendangregg/FlameGraph/blob/master/flamegraph.pl

    :param dict profile: the memory profile
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
    with tempfile.NamedTemporaryFile() as tmp:
        tmp.write("".join(flame).encode("utf-8"))
        cmd = " ".join(
            [
                os.path.join(pwd, _SCRIPT_FILENAME),
                tmp.name,
                "--title",
                f'"{title}"',
                "--countname",
                f"{units}",
                "--reverse",
                "--width",
                str(width),
                "--height",
                str(height),
            ]
        )
        out, _ = commands.run_safely_external_command(cmd)
    return out.decode("utf-8")
