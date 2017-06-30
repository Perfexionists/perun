"""Flow graphs visualization of the profiles."""

import bokeh.layouts as layouts
import bokeh.plotting as plotting
import click
import pandas as pandas

import perun.core.profile.converters as converters
import perun.view.flowgraph.bokeh_flow_graph as bokeh_graphs
import perun.view.flowgraph.ncurses_flow_graph as curses_graphs
from perun.utils.helpers import pass_profile

__author__ = 'Radim Podola'


def _call_terminal_flow(profile):
    """ Call interactive flow graph in the terminal
    # Fixme: Why the hell is this dependent on heap map :(

    Arguments:
        profile(dict): memory profile with records
    """
    heap_map = converters.create_heap_map(profile)
    curses_graphs.flow_graph(heap_map)


def _call_flow(profile, filename, width, interactive):
    """ Creates and draw a grid of the Flow usage graph.

    Arguments:
        profile(dict): the memory profile
        filename(str): output filename
        width(int): width of the bar graph
        interactive(bool): true if the bokeh session should be interactive
    """
    header = profile['header']
    profile_type = header['type']
    amount_unit = header['units'][profile_type]

    # converting memory profile to flow usage table
    flow_table = converters.create_flow_table(profile)
    # converting flow usage table to pandas DataFrame
    data_frame = pandas.DataFrame.from_dict(flow_table)
    # obtaining grid of flow usage graph
    grid = _get_flow_usage_grid(data_frame, amount_unit, width)

    plotting.output_file(filename)
    if interactive:
        plotting.show(grid)
    else:
        plotting.save(grid, filename)


def _get_flow_usage_grid(data_frame, unit, graph_width):
    """ Creates a grid of the Flow usage graph.

    Arguments:
        data_frame(DataFrame): the Pandas DataFrame
        unit(str): memory amount unit
        graph_width(int): width of the bar graph

    Returns:
        any: Bokeh's grid layout object
    """
    graph, toggles = bokeh_graphs.flow_usage_graph(data_frame, unit)

    _set_title_visual(graph.title)
    _set_axis_visual(graph.xaxis)
    _set_axis_visual(graph.yaxis)
    _set_graphs_width(graph, graph_width)

    widget = layouts.widgetbox(toggles)

    grid = layouts.row(graph, widget)

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
@click.option('--use-terminal', '-t', is_flag=True, default=False,
              help="Shows flow graph in the terminal (using ncurses).")
@click.option('--filename', '-f', default="flow.html",
              help="Outputs the graph to file specified by filename.")
@click.option('--graph-width', '-w', default=1200,
              help="Changes the width of the generated Graph.")
@click.option('--run-in-browser', '-b', is_flag=True, default=False,
              help="Will run the generated flow graph in browser.")
@pass_profile
# Fixme: Consider breaking this to two
def flowgraph(profile, use_terminal, filename, graph_width, run_in_browser, **_):
    """Flow graphs visualization of the profile."""
    if use_terminal:
        _call_terminal_flow(profile)
    else:
        _call_flow(profile, filename, graph_width, run_in_browser)
