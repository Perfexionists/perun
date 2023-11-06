"""This module provides wrapper for the Flame graph visualization"""
from __future__ import annotations

import os
import subprocess

import perun.profile.convert as converter
import perun.profile.factory as profiles
import perun.utils.helpers as helpers


_SCRIPT_FILENAME = "./flamegraph.pl"


def draw_flame_graph(profile: profiles.Profile, output_file: str, height: int) -> None:
    """Draw Flame graph from profile.

        To create Flame graphs it's uses perl script created by Brendan Gregg.
        https://github.com/brendangregg/FlameGraph/blob/master/flamegraph.pl

    :param dict profile: the memory profile
    :param str output_file: filename of the output file, expected is SVG format
    :param int height: graphs height
    """
    # converting profile format to format suitable to Flame graph visualization
    flame = converter.to_flame_graph_format(profile)

    header = profile["header"]
    profile_type = header["type"]
    title = "{} consumption of {} {} {}".format(
        profile_type,
        header["cmd"],
        helpers.get_key_with_aliases(header, ("args", "params")),
        header["workload"],
    )
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
