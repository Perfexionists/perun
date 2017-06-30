"""Collection of helper functions for working with bokeh graphs"""

import bokeh.layouts as layouts
import bokeh.palettes as palettes
import bokeh.plotting as plotting

import perun.utils.log as log

__author__ = 'Tomas Fiedor'

GRAPH_LR_PADDING = 0
GRAPH_B_PADDING = 100
GRAPH_T_PADDING = 50


def get_unique_colours_for_(data_source, key):
    """Returns list of colours (sorted according to the legend); up to 256 colours.

    Arguments:
        data_source(pandas.DataFrame): data frame for which we want to get unique colours
        key(str): key for which we are generating unique colours
    """
    unique_keys = data_source[key].unique()
    unique_keys_num = len(unique_keys)

    if unique_keys_num > 256:
        log.error("plotting to Bokeh backend currently supports only 256 colours")

    # This is temporary workaround for non-sorted legends
    keys_to_colour = list(zip(unique_keys, palettes.viridis(unique_keys_num)))
    keys_to_colour.sort()

    return list(map(lambda x: x[1], keys_to_colour))


def configure_axis(axis, axis_title):
    """ Sets the graph's axis visual style

    Arguments:
        axis(any): Bokeh plot's axis object
        axis_title(str): title of the axis
    """
    axis.axis_label_text_font = 'helvetica'
    axis.axis_label_text_font_style = 'bold'
    axis.axis_label_text_font_size = '14pt'
    axis.axis_label = axis_title
    axis.major_label_text_font_style = 'bold'
    axis.major_tick_line_width = 2
    axis.minor_tick_line_width = 2
    axis.major_tick_in = 8
    axis.major_tick_out = 8
    axis.minor_tick_in = 4
    axis.minor_tick_out = 4


def configure_grid(grid):
    """Sets the given grid

    Arguments:
        grid(bokeh.Grid): either x or y grid
    """
    grid.minor_grid_line_color = 'grey'
    grid.minor_grid_line_alpha = 0.2
    grid.grid_line_color = 'grey'
    grid.grid_line_alpha = 0.4


def configure_title(graph_title, title):
    """ Sets the graph's title visual style

    Arguments:
        graph_title(bokeh.Title): bokeh title of the graph
        title(str): title of the graph
    """
    graph_title.text_font = 'helvetica'
    graph_title.text_font_style = 'bold'
    graph_title.text_font_size = '21pt'
    graph_title.align = 'center'
    graph_title.text = title


def configure_graph_canvas(graph, graph_width):
    """Sets the canvas of the graph, its width and padding

    Arguments:
        graph(bokeh.Figure): figure for which we will be setting canvas
        graph_width(int): width of bokeh graph
    """
    graph.width = graph_width
    graph.min_border_left = GRAPH_LR_PADDING
    graph.min_border_right = GRAPH_LR_PADDING
    graph.min_border_top = GRAPH_T_PADDING
    graph.min_border_bottom = GRAPH_B_PADDING
    graph.outline_line_width = 2
    graph.outline_line_color = 'black'

    for r in graph.renderers:
        if hasattr(r, 'glyph'):
            r.glyph.line_width = 2
            r.glyph.line_color = 'black'


def configure_legend(graph):
    """
    Arguments:
        graph(bokeh.Figure): bokeh graph for which we will configure the legend
    """
    graph.legend.border_line_color = 'black'
    graph.legend.border_line_width = 2
    graph.legend.border_line_alpha = 1.0
    graph.legend.label_text_font_style = 'bold'
    graph.legend.location = 'top_right'


def configure_graph(graph, profile, func, graph_title, x_axis_label, y_axis_label, graph_width):
    """Configures the created graph with basic stuff---axes, canvas, title

    Arguments:
        graph(bokeh.Figure): bokeh graph, that we want to configure with basic stuff
        profile(dict): dictionary with measured data
        func(str): function that will be used for aggregation of the data
        x_axis_label(str): label on the x axis
        y_axis_label(str): label on the y axis
        graph_title(str): name of the graph
        graph_width(int): width of the created bokeh graph
    """
    # Stylize the graph
    configure_graph_canvas(graph, graph_width)
    configure_axis(graph.xaxis, x_axis_label)
    configure_axis(graph.yaxis, y_axis_label)
    configure_title(graph.title, graph_title)
    configure_legend(graph)
    configure_grid(graph.ygrid)
    configure_grid(graph.grid)

    # If of key is ammount, add unit
    if func not in ('count', 'nunique') and not y_axis_label.endswith("]"):
        profile_type = profile['header']['type']
        type_unit = profile['header']['units'][profile_type]
        graph.yaxis.axis_label = y_axis_label + " [{}]".format(type_unit)


def save_graphs_in_column(graphs, filename, view_in_browser=False):
    """
    Arguments:
        graphs(list): list of bokeh figure that will be outputed in stretchable graph
        filename(str): name of the file, where the column graph will be saved
        view_in_browser(bool): true if the outputed graph should be viewed straight in the browser
    """
    output = layouts.column(graphs, sizing_mode="stretch_both")
    plotting.output_file(filename)

    if view_in_browser:
        plotting.show(output)
    else:
        plotting.save(output, filename)
