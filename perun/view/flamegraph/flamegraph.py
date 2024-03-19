"""This module provides wrapper for the Flame graph visualization"""
from __future__ import annotations

# Standard Imports
from typing import TYPE_CHECKING
import os
import tempfile

# Third-Party Imports

# Perun Imports
from perun.profile import convert
from perun.utils.common import script_kit
from perun.utils.external import commands

if TYPE_CHECKING:
    from perun.profile.factory import Profile


def draw_flame_graph(profile: Profile, height: int, width: int = 1200, title: str = "") -> str:
    """Draw Flame graph from profile.

        To create Flame graphs we use perl script created by Brendan Gregg.
        https://github.com/brendangregg/FlameGraph/blob/master/flamegraph.pl

    :param profile: the memory profile
    :param width: width of the graph
    :param height: graphs height
    :param title: if set to empty, then title will be generated
    """
    # converting profile format to format suitable to Flame graph visualization
    flame = convert.to_flame_graph_format(profile)

    header = profile["header"]
    profile_type = header["type"]
    cmd, workload = (header["cmd"], header["workload"])
    title = title if title != "" else f"{profile_type} consumption of {cmd} {workload}"
    units = header["units"][profile_type]

    pwd = os.path.dirname(os.path.abspath(__file__))
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write("".join(flame).encode("utf-8"))
        tmp.close()
        cmd = " ".join(
            [
                script_kit.get_script("flamegraph.pl"),
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
        os.remove(tmp.name)
    return out.decode("utf-8")
