"""Flow graphs visualization of the profiles."""

import click
from perun.utils.helpers import pass_profile
import perun.utils.profile_converters as heap_representation
import perun.view.flowgraph.flow_graph as fg
import bokeh.layouts as bla
import pandas as pd
import bokeh.plotting as bpl
import perun.utils.profile_converters as converter
import perun.view.flowgraph.flow_usage_graph as flow

__author__ = 'Radim Podola'


def _call_terminal_flow(profile):
    """ Call interactive flow graph in the terminal

    Arguments:
        profile(dict): memory profile with records
    """
    heap_map = heap_representation.create_heap_map(profile)
    fg.flow_graph(heap_map)


def _call_flow(profile, filename, width):
    """ Creates and draw a grid of the Flow usage graph.

    Arguments:
        profile(dict): the memory profile
        filename(str): output filename
        width(int): width of the bar graph
    """
    header = profile['header']
    profile_type = header['type']
    amount_unit = header['units'][profile_type]

    # converting memory profile to flow usage table
    flow_table = converter.create_flow_table(profile)
    # converting flow usage table to pandas DataFrame
    data_frame = pd.DataFrame.from_dict(flow_table)
    # obtaining grid of flow usage graph
    grid = _get_flow_usage_grid(data_frame, amount_unit, width)

    bpl.output_file(filename)
    bpl.show(grid)


def _get_flow_usage_grid(data_frame, unit, graph_width):
    """ Creates a grid of the Flow usage graph.

    Arguments:
        data_frame(DataFrame): the Pandas DataFrame
        unit(str): memory amount unit
        graph_width(int): width of the bar graph

    Returns:
        any: Bokeh's grid layout object
    """
    graph, toggles = flow.flow_usage_graph(data_frame, unit)

    _set_title_visual(graph.title)
    _set_axis_visual(graph.xaxis)
    _set_axis_visual(graph.yaxis)
    _set_graphs_width(graph, graph_width)

    widget = bla.widgetbox(toggles)

    grid = bla.row(graph, widget)

    return grid


def _set_title_visual(title):
    """ Sets the graph's title visual style

    Arguments:
        title(any): Bokeh plot's title object
    """
    title.text_font = 'helvetica'
    title.text_font_style = 'bold'
    title.text_font_size = '12pt'
    title.align = 'center'


def _set_axis_visual(axis):
    """ Sets the graph's axis visual style

    Arguments:
        axis(any): Bokeh plot's axis object
    """
    axis.axis_label_text_font_style = 'italic'
    axis.axis_label_text_font_size = '12pt'


def _set_graphs_width(graph, width):
    """ Sets the graph width

    Arguments:
        graph(Plot): Bokeh's plot object
        width(int): width to set
    """
    graph.plot_width = width


@click.command()
@click.option('--terminal', '-t', is_flag=True, default=False,
              help="Shows flow graph in the terminal.")
@click.option('--filename', '-f', default="flow.html",
              help="Output filename.")
@click.option('--width', '-w', default=1200,
              help="Graph's width.")
@pass_profile
def flowgraph(profile, **kwargs):
    """Flow graphs visualization of the profile."""
    if kwargs.get('terminal', False):
        _call_terminal_flow(profile)
    else:
        file = kwargs.get('filename', "flow.html")
        width = kwargs.get('width', 1200)
        _call_flow(profile, file, width)
