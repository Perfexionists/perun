"""Bar's graphs interpretation of the profiles."""

import click
import pandas
import bokeh.plotting as plotting
import bokeh.layouts as layouts
import perun.utils.profile_converters as converter
import perun.view.bargraph.bar_graphs as bar_creator
import perun.view.flowgraph.run as helpers
from perun.utils.helpers import pass_profile

__author__ = 'Radim Podola'


def _create_bar_graphs(profile, filename, width):
    """ Creates and draw a grid of the Bar's graphs.

    Arguments:
        profile(dict): the memory profile
        filename(str): filename of the output file, expected is HTML format
        width(int): width of the bar graph
    """
    header = profile['header']
    profile_type = header['type']
    amount_unit = header['units'][profile_type]

    # converting memory profile to allocations table
    bar_table = converter.create_allocations_table(profile)
    # converting allocations table to pandas DataFrame
    data_frame = pandas.DataFrame.from_dict(bar_table)
    # obtaining grid of Bar's graphs
    grid = _get_bar_graphs_grid(data_frame, amount_unit, width)

    plotting.output_file(filename)
    plotting.show(grid)


def _get_bar_graphs_grid(data_frame, unit, graph_width):
    """ Creates a grid of the Bar's graphs.

    Arguments:
        data_frame(DataFrame): the Pandas DataFrame
        unit(str): memory amount unit
        graph_width(int): width of the bar graph

    Returns:
        any: Bokeh's grid layout object
    """
    graphs = []

    r1c1 = bar_creator.bar_graph_snaps_sum_subtype_stacked(data_frame, unit)
    graphs.append(r1c1)
    r1c2 = bar_creator.bar_graph_snaps_sum_uid_stacked(data_frame, unit)
    graphs.append(r1c2)
    r2c1 = bar_creator.bar_graph_snaps_count_subtype_grouped(data_frame)
    graphs.append(r2c1)
    r2c2 = bar_creator.bar_graph_snaps_count_uid_grouped(data_frame)
    graphs.append(r2c2)
    r3c1 = bar_creator.bar_graph_uid_count(data_frame)
    graphs.append(r3c1)
    r3c2 = bar_creator.bar_graph_uid_sum(data_frame, unit)
    graphs.append(r3c2)

    for graph in graphs:
        if graph is None:
            continue
        helpers._set_title_visual(graph.title)
        _set_axis_visual(graph.xaxis)
        _set_axis_visual(graph.yaxis)
        _set_graphs_width(graph, graph_width)

    # creating layout grid
    row1 = _create_grid_row([r1c1, r1c2])
    row2 = _create_grid_row([r2c1, r2c2])
    row3 = _create_grid_row([r3c1, r3c2])

    grid = layouts.column(row1, row2, row3)

    return grid


def _create_grid_row(bars):
    """ Create grid's row from list of graphs

    Arguments:
        bars(list): list of Bokeh plot's objects
    """
    row_items = [b for b in bars if b is not None]
    row = layouts.row() if row_items == [] else layouts.row(row_items)

    return row


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
@click.option('--filename', '-f', default="bars.html",
              help="Outputs the graph to the file specified by filename.")
@click.option('--graph-width', '-w', default=800,
              help="Changes the width of the generated Graph.")
@pass_profile
def bargraph(profile, filename, graph_width, **kwargs):
    """Bar's graphs interpretation of the profile."""
    _create_bar_graphs(profile, filename, graph_width)
