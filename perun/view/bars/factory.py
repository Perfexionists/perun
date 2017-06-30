"""This module contains the BAR graphs creating functions"""

import bkcharts as charts

import perun.utils.log as log
import perun.utils.bokeh_helpers as bokeh_helpers
import perun.utils.profile_converters as converters
import perun.view.flowgraph.run as helpers

from perun.utils.bokeh_helpers import GRAPH_LR_PADDING, GRAPH_TB_PADDING

__author__ = 'Radim Podola'
__coauthored__ = 'Tomas Fiedor'


def set_axis(axis, axis_title):
    """ Sets the graph's axis visual style

    Arguments:
        axis(any): Bokeh plot's axis object
        axis_title(str): title of the axis
    """
    axis.axis_label_text_font_style = 'italic'
    axis.axis_label_text_font_size = '12pt'
    axis.axis_label = axis_title


def create_from_params(profile, func, of_key, per_key, by_key, cummulation_type,
                       x_axis_label, y_axis_label, graph_title, graph_width=800):
    """Creates Bar graph according to the given parameters.

    Takes the input profile, convert it to pandas.DataFrame. Then the data according to 'of_key'
    parameter are used as values and are output by aggregation function of 'func' depending on
    values of 'per_key'. Values are further stacked by 'by_key' key and cummulated according to the
    type.

    Arguments:
        profile(dict): dictionary with measured data
        func(str): function that will be used for aggregation of the data
        of_key(str): key that specifies which fields of the resource entry will be used as data
        per_key(str): key that specifies fields of the resource that will be on the x axis
        by_key(str): key that specifies grouping or stacking of the resources
        cummulation_type(str): type of the cummulation of the data (either stacked or grouped)
        x_axis_label(str): label on the x axis
        y_axis_label(str): label on the y axis
        graph_title(str): name of the graph
        graph_width(int): width of the created bokeh graph

    Returns:
        charts.Bar: bar graph according to the params
    """
    # Convert profile to pandas data grid
    data_frame = converters.resources_to_pandas_dataframe(profile)

    # Create basic graph:
    if cummulation_type == 'stacked':
        bar_graph = create_stacked_bar_graph(data_frame, func, of_key, per_key, by_key)
    elif cummulation_type == 'grouped':
        bar_graph = create_grouped_bar_graph(data_frame, func, of_key, per_key, by_key)
    else:
        log.error("unknown cummulation type '{}'".format(cummulation_type))

    # Stylize the graph
    bar_graph.width = graph_width
    bar_graph.min_border_left = GRAPH_LR_PADDING
    bar_graph.min_border_right = GRAPH_LR_PADDING
    bar_graph.min_border_top = GRAPH_TB_PADDING
    bar_graph.min_border_bottom = GRAPH_TB_PADDING
    set_axis(bar_graph.xaxis, x_axis_label)
    set_axis(bar_graph.yaxis, y_axis_label)
    bar_graph.title.text = graph_title
    # Fixme: Refactor this!
    helpers._set_title_visual(bar_graph.title)

    # If of key is ammount, add unit
    if func not in ('count', 'nunique') and not y_axis_label.endswith("]"):
        profile_type = profile['header']['type']
        type_unit = profile['header']['units'][profile_type]
        bar_graph.yaxis.axis_label = y_axis_label + " [{}]".format(type_unit)

    return bar_graph


def create_stacked_bar_graph(data_frame, func, of_key, per_key, by_key):
    """Creates a bar graph with stacked values.

    Arguments:
        data_frame(pandas.DataFrame): data frame with values of resources
        func(str): aggregation function for the values
        of_key(str): key specifying the values of the graph
        per_key(str): key specifying the x labels
        by_key(str): key specifying the stacking field

    Returns:
        charts.Bar: stacked bar
    """
    bar_graph = charts.Bar(
        data_frame, label=per_key, values=of_key, agg=func, stack=by_key, bar_width=1.0,
        tooltips=[(by_key, '@{}'.format(by_key))], tools="pan, wheel_zoom, reset, save",
        color=bokeh_helpers.get_unique_colours_for_(data_frame, by_key)
    )
    return bar_graph


def create_grouped_bar_graph(data_frame, func, of_key, per_key, by_key):
    """Creates a bar graph with grouped values.

    Arguments:
        data_frame(pandas.DataFrame): data frame with values of resources
        func(str): aggregation function for the values
        of_key(str): key specifying the values of the graph
        per_key(str): key specifying the x labels
        by_key(str): key specifying the stacking field

    Returns:
        charts.Bar: stacked bar
    """
    bar_graph = charts.Bar(
        data_frame, label=per_key, values=of_key, agg=func, group=by_key, bar_width=1.0,
        tooltips=[(by_key, '@{}'.format(by_key))], tools="pan, wheel_zoom, reset, save",
        color=bokeh_helpers.get_unique_colours_for_(data_frame, by_key)
    )
    return bar_graph
