"""This module contains the BAR graphs creating functions"""

import demandimport
import perun.profile.convert as convert
import perun.utils.view_helpers as bokeh_helpers
# import holoviews as hv

with demandimport.enabled():
    import bkcharts as charts

__author__ = 'Radim Podola'
__coauthored__ = 'Tomas Fiedor'


def create_from_params(profile, func, of_key, per_key, by_key, cummulation_type,
                       x_axis_label, y_axis_label, graph_title, graph_width=800):
    """Creates Bar graph according to the given parameters.

    Takes the input profile, convert it to pandas.DataFrame. Then the data according to 'of_key'
    parameter are used as values and are output by aggregation function of 'func' depending on
    values of 'per_key'. Values are further stacked by 'by_key' key and cummulated according to the
    type.

    :param dict profile: dictionary with measured data
    :param str func: function that will be used for aggregation of the data
    :param str of_key: key that specifies which fields of the resource entry will be used as data
    :param str per_key: key that specifies fields of the resource that will be on the x axis
    :param str by_key: key that specifies grouping or stacking of the resources
    :param str cummulation_type: type of the cummulation of the data (either stacked or grouped)
    :param str x_axis_label: label on the x axis
    :param str y_axis_label: label on the y axis
    :param str graph_title: name of the graph
    :param int graph_width: width of the created bokeh graph
    :returns charts.Bar: bar graph according to the params
    """
    # Convert profile to pandas data grid
    data_frame = convert.resources_to_pandas_dataframe(profile)
    data_frame.sort_values([per_key, by_key], inplace=True)

    # Create basic graph:
    if cummulation_type == 'stacked':
        bar_graph = create_stacked_bar_graph(data_frame, func, of_key, per_key, by_key)
    else:
        # Is grouped
        bar_graph = create_grouped_bar_graph(data_frame, func, of_key, per_key, by_key)

    # Call basic configuration of the graph
    bokeh_helpers.configure_graph(
        bar_graph, profile, func, graph_title, x_axis_label, y_axis_label, graph_width
    )

    return bar_graph


def create_stacked_bar_graph(data_frame, func, of_key, per_key, by_key):
    """Creates a bar graph with stacked values.

    :param pandas.DataFrame data_frame: data frame with values of resources
    :param str func: aggregation function for the values
    :param str of_key: key specifying the values of the graph
    :param str per_key: key specifying the x labels
    :param str by_key: key specifying the stacking field
    :returns charts.Bar: stacked bar
    """
    bar_graph = charts.Bar(
        data_frame, label=per_key, values=of_key, agg=func, stack=by_key, bar_width=1.0,
        tooltips=[(by_key, '@{}'.format(by_key))],
        tools="pan,wheel_zoom,box_zoom,zoom_in,zoom_out,reset,save",
        color=bokeh_helpers.get_unique_colours_for_(data_frame, by_key)
    )
    return bar_graph


def create_grouped_bar_graph(data_frame, func, of_key, per_key, by_key):
    """Creates a bar graph with grouped values.

    :param pandas.DataFrame data_frame: data frame with values of resources
    :param str func: aggregation function for the values
    :param str of_key: key specifying the values of the graph
    :param str per_key: key specifying the x labels
    :param str by_key: key specifying the stacking field
    :returns charts.Bar: stacked bar
    """
    bar_graph = charts.Bar(
        data_frame, label=per_key, values=of_key, agg=func, group=by_key, bar_width=1.0,
        tooltips=[(by_key, '@{}'.format(by_key))],
        tools="pan,wheel_zoom,box_zoom,zoom_in,zoom_out,reset,save",
        color=bokeh_helpers.get_unique_colours_for_(data_frame, by_key)
    )
    return bar_graph
