"""This module contains the BAR graphs creating functions"""

import perun.profile.factory as profiles

import perun.profile.converters as converters
import perun.utils.bokeh_helpers as bokeh_helpers
import perun.utils.log as log

import demandimport
with demandimport.enabled():
    import bkcharts as charts

__author__ = 'Radim Podola'
__coauthored__ = 'Tomas Fiedor'


def validate_keywords(profile, func, of_key, **_):
    """Function for validating the keywords before calling the graph generation.

    Checks if the of key can be aggregated by the function.

    Arguments:
        profile(dict): profile that will be used against in the validation
        func(function): function used for aggregation of the data
        of_key(str): key that will be aggregated in the graph

    Returns:
        bool: true if the values are OK

    Raises:
        InvalidParameterException: if the of_key does not support the given function
    """
    return profiles.is_key_aggregatable_by(profile, func, of_key, "of_key")


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

    # Call basic configuration of the graph
    bokeh_helpers.configure_graph(
        bar_graph, profile, func, graph_title, x_axis_label, y_axis_label, graph_width
    )

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
