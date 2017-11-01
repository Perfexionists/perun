"""Flame graph visualization of the profiles."""

import click
import perun.view.flamegraph.flamegraph as flame
from perun.utils.helpers import pass_profile

__author__ = 'Radim Podola'


@click.command()
@click.option('--filename', '-f', default="flame.svg",
              help="Outputs the graph to file specified by filename.")
@click.option('--graph-height', '-h', default=20, type=int,
              help="Changes the width of the generated Graph.")
@pass_profile
def flamegraph(profile, filename, graph_height, **_):
    """
    Flame graph shows the relative and inclusive presence of the resources according to the stack
    depth. This visualization uses the awesome script made by © Brendan Gregg!

    ::

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

    Flame graph allows one to quickly identify hotspots, that are the source of the resource
    consumption complexity. On X axis, a relative consumption of the data is depicted, while on
    Y axis a stack depth is displayed. The wider the bars are on the X axis are, the more the
    function consumed resources relative to others.

    Acknowledgements: Big thanks to Brendan Gregg for creating the original perl script for creating
    flame graphs out of simple format. If you like this visualization technique, please check out
    this guy's site (http://brendangregg.com) for more information about performance, profiling and
    useful talks and visualization techniques!
    """
    flame.draw_flame_graph(profile, filename, graph_height)
