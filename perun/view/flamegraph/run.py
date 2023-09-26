"""Flame graph visualization of the profiles."""
from __future__ import annotations

import click
from typing import Any

import perun.view.flamegraph.flamegraph as flame
from perun.profile.factory import pass_profile, Profile


@click.command()
@click.option('--filename', '-f', default="flame.svg",
              help="Sets the output file of the resulting flame graph.")
@click.option('--graph-height', '-h', default=20, type=int,
              help="Increases the width of the resulting flame graph.")
@pass_profile
def flamegraph(profile: Profile, filename: str, graph_height: int, **_: Any) -> None:
    """Flame graph interprets the relative and inclusive presence of the
    resources according to the stack depth of the origin of resources.

    \b
      * **Limitations**: `memory` profiles generated by
        :ref:`collectors-memory`.
      * **Interpretation style**: graphical
      * **Visualization backend**: HTML

    Flame graph intends to quickly identify hotspots, that are the source of
    the resource consumption complexity. On X axis, a relative consumption of
    the data is depicted, while on Y axis a stack depth is displayed. The wider
    the bars are on the X axis are, the more the function consumed resources
    relative to others.

    **Acknowledgements**: Big thanks to Brendan Gregg for creating the original
    perl script for creating flame graphs w.r.t simple format. If you like this
    visualization technique, please check out this guy's site
    (http://brendangregg.com) for more information about performance, profiling
    and useful talks and visualization techniques!

    The example output of the flamegraph is more or less as follows::

        \b
                            `
                            -                         .
                            `                         |
                            -              ..         |     .
                            `              ||         |     |
                            -              ||        ||    ||
                            `            |%%|       |--|  |!|
                            -     |## g() ##|     |#g()#|***|
                            ` |&&&& f() &&&&|===== h() =====|
                            +````||````||````||````||````||````

    Refer to :ref:`views-flame-graph` for more thorough description and
    examples of the interpretation technique. Refer to
    :func:`perun.profile.convert.to_flame_graph_format` for more details how
    the profiles are converted to the flame graph format.
    """
    flame.draw_flame_graph(profile, filename, graph_height)
