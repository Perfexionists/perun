"""This module contains the Flow usage graph creating functions"""

import perun.profile.factory as profiles

import perun.profile.convert as convert
import perun.utils.bokeh_helpers as bokeh_helpers
import perun.utils.log as log

import demandimport
with demandimport.enabled():
    import bkcharts as charts
    import bokeh.models as models
    import pandas

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


def create_from_params(profile, func, of_key, through_key, by_key, stacked, accumulate,
                       x_axis_label, y_axis_label, graph_title, graph_width=800):
    """Creates Flow graph according to the given parameters.

    Takes the input profile, converts it first to pandas.DataFrame. Then the data are grouped
    according to the 'by_key' and then grouped again for each 'through' key. For this atomic
    groups aggregation function is used.

    For each computed data, we output the area and points.

    Arguments:
        profile(dict): dictionary with measured data
        func(str): function that will be used for aggregation of the data
        of_key(str): key that specifies which fields of the resource entry will be used as data
        through_key(str): key that specifies fields of the resource that will be on the x axis
        by_key(str): key that specifies values for which graphs will be outputed
        stacked(bool): true if the values of the graphs should be stacked on each other
          -> this shows the overall values
        accumulate(bool): true if the values from previous x values should be accumulated
        x_axis_label(str): label on the x axis
        y_axis_label(str): label on the y axis
        graph_title(str): name of the graph
        graph_width(int): width of the created bokeh graph

    Returns:
        charts.Area: flow graph according to the params
    """
    # Convert profile to pandas data grid
    data_frame = convert.resources_to_pandas_dataframe(profile)
    data_source = construct_data_source_from(
        data_frame, func, of_key, by_key, through_key, accumulate
    )

    # Obtain colours, which will be sorted in reverse
    key_colours = bokeh_helpers.get_unique_colours_for_(
        data_frame, by_key, sort_color_style=bokeh_helpers.ColourSort.Reverse
    )

    # Construct the area chart
    area_chart = charts.Area(data_source, stack=stacked, color=key_colours)

    # Configure graph and return it
    bokeh_helpers.configure_graph(
        area_chart, profile, func, graph_title, x_axis_label, y_axis_label, graph_width
    )
    configure_area_chart(area_chart, data_frame, data_source, through_key, stacked)

    return area_chart


def configure_area_chart(area_chart, data_frame, data_source, through_key, stacked):
    """Sets additional configuration details to the area chart, specific for flow visualization.

    Configures the legend location, click policy and ranges of the graph.

    Arguments:
        area_chart(charts.Area): area chart which will be further configured
        data_frame(pandas.DataFrame): original data frame
        data_source(pandas.DataFrame): transformed data frame with aggregated data
        through_key(str): key on the x axis
        stacked(bool): true if the values in the graph are stacked
    """
    # Get minimal and maximal values; note we will add some small bonus to the maximal value
    minimal_x_value = data_frame[through_key].min()
    maximal_x_value = data_frame[through_key].max()
    values_data_frame = pandas.DataFrame(data_source)
    minimal_y_value = values_data_frame.min().min()
    value_maxima = values_data_frame.max()
    maximal_y_value = 1.05*(value_maxima.max() if not stacked else value_maxima.sum())

    # Configure flow specific options
    area_chart.legend.location = 'top_left'
    area_chart.legend.click_policy = 'hide'
    area_chart.x_range = models.Range1d(minimal_x_value, maximal_x_value - 1)
    area_chart.y_range = models.Range1d(minimal_y_value, maximal_y_value)


def construct_data_source_from(data_frame, func, of_key, by_key, through_key, accumulate):
    """Transforms the data frame using the aggregating functions, breaking into groups.

    Takes the original data frame, groups it by the 'by_key' and then for each group, groups values
    again by the 'through_key', which are further aggregated by func and optionally accumulated.

    Arguments:
        data_frame(pandas.DataFrame): source data for the aggregated data frame
        func(str): function that will be used for aggregation of the data
        of_key(str): key that specifies which fields of the resource entry will be used as data
        through_key(str): key that specifies fields of the resource that will be on the x axis
        by_key(str): key that specifies values for which graphs will be outputed
        accumulate(bool): true if the values from previous x values should be accumulated

    Returns:
        pandas.DataFrame: transformed data frame
    """
    # Compute extremes for X axis
    #  -> this is needed for offseting of the values for the area chart
    minimal_x_value = data_frame[through_key].min()
    maximal_x_value = data_frame[through_key].max()

    # Construct the data source (first we group the values by 'by_key' (one graph per each key).
    #   And then we compute the aggregations of the data grouped again, but by through key
    #   (i.e. for each value on X axis), the values are either accumulated or not
    data_source = {}
    for group_name, by_key_group_data_frame in data_frame.groupby(by_key):
        data_source[group_name] = [0]*(maximal_x_value + 1)
        source_data_frame = group_and_aggregate(by_key_group_data_frame, through_key, func)
        if accumulate:
            accumulated_value = 0
            for index in range(minimal_x_value, maximal_x_value):
                accumulated_value += source_data_frame[of_key].get(index + minimal_x_value, 0)
                data_source[group_name][index] = accumulated_value
        else:
            for through_key_value, of_key_value in source_data_frame[of_key].items():
                data_source[group_name][through_key_value - minimal_x_value] = of_key_value
    return data_source


def group_and_aggregate(data, group_through_key, func):
    """Groups the data by group_through_key and then aggregates it through function

    Arguments:
        data(pandas.DataFrame): data frame with partially grouped data
        group_through_key(str): key which will be used for further aggregation
        func(str): aggregation function for the grouped data

    Returns:
        dict: source data frame
    """
    # Aggregate the data according to the func grouped by through_key
    through_data_group = data.groupby(group_through_key)
    try:
        aggregation_function = getattr(through_data_group, func)
    except AttributeError:
        log.error("{} function is not supported as aggregation for this visualization".format(
            func
        ))
    return aggregation_function()
