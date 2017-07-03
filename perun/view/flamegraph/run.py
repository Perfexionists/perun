"""Flame graph visualization of the profiles."""

import click
import perun.view.flamegraph.flamegraph as flame
from perun.utils.helpers import pass_profile

__author__ = 'Radim Podola'


@click.command()
@click.option('--filename', '-f', default="flame.svg",
              help="Outputs the graph to file specified by filename.")
@click.option('--graph-height', '-h', default=20,
              help="Changes the width of the generated Graph.")
@pass_profile
def flamegraph(profile, filename, graph_height, **_):
    """Flame graph visualization of the profile."""
    flame.draw_flame_graph(profile, filename, graph_height)
