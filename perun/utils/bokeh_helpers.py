"""Collection of helper functions for working with bokeh graphs"""

import perun.utils.log as log

import demandimport
with demandimport.enabled():
    import bokeh.layouts as layouts
    import bokeh.palettes as palettes
    import bokeh.plotting as plotting

__author__ = 'Tomas Fiedor'

GRAPH_LR_PADDING = 0
GRAPH_B_PADDING = 100
GRAPH_T_PADDING = 50


class ColourSort(object):
    """Enumeration of sort modes"""
    No = 0
    Reverse = 1
    ByOccurence = 2


def sort_colours(colours, sort_color_style, keys):
    """Sorts the colours corresponding to the keys according to the given style

    Note: For different visualizations and outputs we want the colours in different format,
    but still as a list. Some need them in reverse order, osme as they are in the palette and
    some (like e.g. Bars) needs to be tied to the keys, as they are occuring in the graph.

    :param list colours: list of chosen colour palette
    :param ColourSort sort_color_style: style of the sorting of the colours
    :param list keys: list of keys, sorted by their appearance
    :returns list: sorted colours according to the chosen sorting mode
    """
    if sort_color_style == ColourSort.ByOccurence:
        keys_to_colour = list(zip(keys, colours))
        keys_to_colour.sort()
        return list(map(lambda x: x[1], keys_to_colour))
    elif sort_color_style == ColourSort.Reverse:
        return colours[::-1]
    else:
        return colours


def get_unique_colours_for_(data_source, key, sort_color_style=ColourSort.ByOccurence):
    """Returns list of colours (sorted according to the legend); up to 256 colours.

    :param pandas.DataFrame data_source: data frame for which we want to get unique colours
    :param str key: key for which we are generating unique colours
    :param ColourSort sort_color_style: style of sorting and assigning the values
    """
    unique_keys = data_source[key].unique()
    unique_keys_num = len(unique_keys)

    if unique_keys_num > 256:
        log.error("plotting to Bokeh backend currently supports only 256 colours")

    # This is temporary workaround for non-sorted legends
    colour_palette = palettes.viridis(unique_keys_num)
    return sort_colours(colour_palette, sort_color_style, unique_keys)


def configure_axis(axis, axis_title):
    """ Sets the graph's axis visual style

    :param any axis: Bokeh plot's axis object
    :param str axis_title: title of the axis
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

    :param bokeh.Grid grid: either x or y grid
    """
    grid.minor_grid_line_color = 'grey'
    grid.minor_grid_line_alpha = 0.2
    grid.grid_line_color = 'grey'
    grid.grid_line_alpha = 0.4


def configure_title(graph_title, title):
    """ Sets the graph's title visual style

    :param bokeh.Title graph_title: bokeh title of the graph
    :param str title: title of the graph
    """
    graph_title.text_font = 'helvetica'
    graph_title.text_font_style = 'bold'
    graph_title.text_font_size = '21pt'
    graph_title.align = 'center'
    graph_title.text = title


def configure_graph_canvas(graph, graph_width):
    """Sets the canvas of the graph, its width and padding

    :param bokeh.Figure graph: figure for which we will be setting canvas
    :param int graph_width: width of bokeh graph
    """
    graph.width = graph_width
    graph.min_border_left = GRAPH_LR_PADDING
    graph.min_border_right = GRAPH_LR_PADDING
    graph.min_border_top = GRAPH_T_PADDING
    graph.min_border_bottom = GRAPH_B_PADDING
    graph.outline_line_width = 2
    graph.outline_line_color = 'black'

    for renderer in graph.renderers:
        if hasattr(renderer, 'glyph'):
            renderer.glyph.line_width = 2
            renderer.glyph.line_color = 'black'


def configure_legend(graph):
    """
    :param bokeh.Figure graph: bokeh graph for which we will configure the legend
    """
    graph.legend.border_line_color = 'black'
    graph.legend.border_line_width = 2
    graph.legend.border_line_alpha = 1.0
    graph.legend.label_text_font_style = 'bold'
    graph.legend.location = 'top_right'
    graph.legend.click_policy = 'hide'


def configure_graph(graph, profile, func, graph_title, x_axis_label, y_axis_label, graph_width):
    """Configures the created graph with basic stuff---axes, canvas, title

    :param bokeh.Figure graph: bokeh graph, that we want to configure with basic stuff
    :param dict profile: dictionary with measured data
    :param str func: function that will be used for aggregation of the data
    :param str x_axis_label: label on the x axis
    :param str y_axis_label: label on the y axis
    :param str graph_title: name of the graph
    :param int graph_width: width of the created bokeh graph
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
    :param list graphs: list of bokeh figure that will be outputed in stretchable graph
    :param str filename: name of the file, where the column graph will be saved
    :param bool view_in_browser: true if the outputed graph should be viewed straight in the browser
    """
    output = layouts.column(graphs, sizing_mode="stretch_both")
    plotting.output_file(filename)

    if view_in_browser:
        plotting.show(output)
    else:
        plotting.save(output, filename)


def process_profile_to_graphs(factory_module, profile, filename, view_in_browser, **kwargs):
    """Wrapper function for constructing the graphs from profile, saving it and viewing.

    Wrapper function that takes the factory module, constructs the graph for the given profile,
    and then saves it in filename and optionally view in the registered browser.

    :param module factory_module: module which will create the the graph
    :param dict profile: profile that will be processed
    :param str filename: output filename for the bokeh graph
    :param bool view_in_browser: true if the created graph should be view in registered browser
        after it is constructed.
    :param dict kwargs: rest of the keyword arguments
    :raises AttributeError: when the factory_module has not some of the functions
    """
    if hasattr(factory_module, 'validate_keywords'):
        factory_module.validate_keywords(profile, **kwargs)

    graph = factory_module.create_from_params(profile, **kwargs)
    save_graphs_in_column([graph], filename, view_in_browser)
