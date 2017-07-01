"""Flow graphs visualization of the profiles."""

import bokeh.core.enums as enums
import bokeh.layouts as layouts
import bokeh.plotting as plotting
import click
import pandas as pandas

import perun.utils.bokeh_helpers as bokeh_helpers
import perun.utils.cli_helpers as cli_helpers
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

    bokeh_helpers.configure_title(graph.title, "Graph title")
    _set_axis_visual(graph.xaxis)
    _set_axis_visual(graph.yaxis)
    _set_graphs_width(graph, graph_width)

    widget = layouts.widgetbox(toggles)

    grid = layouts.row(graph, widget)

    return grid


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


def process_title(ctx, _, value):
    """Processes the default value for the flow graph title.

    If the value supplied from CLI is non-None, it is returned as it is. Otherwise, we try to
    create some optimal name for the graph ourselves. We do this according to already processed
    parameters as follows:

      Func of 'of-key' through 'through-key' for each 'by-key' (stacked)

    Arguments:
        ctx(click.Context): called context of the process
        value(object): value that is being processed ad add to parameter

    Returns:
        object: either value (if it is non-None) or default title of the graph
    """
    if not value:
        # Construct default title of the graph
        return "{} of '{}' through '{}' for each {} {}".format(
            ctx.params['func'].capitalize(), ctx.params['of_key'], ctx.params['through_key'],
            ctx.params['by_key'], ctx.params['stacked']*"(stacked)"
        )
    else:
        return value


@click.command()
@click.argument('func', required=False, default='sum', metavar="<aggregation_function>",
                type=click.Choice(map(str, enums.Aggregation)))
@click.option('--of', '-o', 'of_key', nargs=1, required=True, metavar="<of_resource_key>",
              is_eager=True, callback=cli_helpers.process_resource_key_param,
              help="Source of the data for the graphs, i.e. what will be displayed on Y axis.")
@click.option('--through', '-t', 'through_key', nargs=1, required=False, metavar="<through_key>",
              is_eager=True, callback=cli_helpers.process_resource_key_param, default='snapshots',
              help="Independent variable on the X axis, values will be grouped by this key.")
@click.option('--by', '-b', 'by_key', nargs=1, required=True, metavar="<by_resource_key>",
              is_eager=True, callback=cli_helpers.process_resource_key_param,
              help="For each of the value of the <by_resource_key> a graph will be output")
@click.option('--stacked', '-s', is_flag=True, default=False,
              help="Will stack the values according to the <by_resource_key> showing the overall.")
# Other options and arguments
@click.option('--use-terminal', '-t', is_flag=True, default=False,
              help="Shows flow graph in the terminal (using ncurses).")
@click.option('--filename', '-f', default="flow.html", metavar="<html>",
              help="Outputs the graph to file specified by filename.")
@click.option('--x-axis-label', '-xl', metavar="<text>", default=None,
              callback=cli_helpers.process_bokeh_axis_title,
              help="Label on the X axis of the bar graph.")
@click.option('--y-axis-label', '-yl', metavar="<text>", default=None,
              callback=cli_helpers.process_bokeh_axis_title,
              help="Label on the Y axis of the bar graph.")
@click.option('--graph-title', '-gt', metavar="<text>", default=None, callback=process_title,
              help="Title of the graph.")
@click.option('--view-in-browser', '-v', default=False, is_flag=True,
              help="Will show the graph in browser.")
@pass_profile
# Fixme: Consider breaking this to two
def flowgraph(profile, use_terminal, filename, view_in_browser, **_):
    """Flow graphs visualization of the profile."""
    if use_terminal:
        _call_terminal_flow(profile)
    else:
        _call_flow(profile, filename, 800, view_in_browser)
