"""This module contains the Flow usage graph creating functions"""

import bkcharts as charts
import bokeh.models as models
import pandas

import perun.utils.log as log
import perun.utils.bokeh_helpers as bokeh_helpers
import perun.core.profile.converters as converters

__author__ = 'Radim Podola'
__coauthored__ = 'Tomas Fiedor'


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
    data_frame = converters.resources_to_pandas_dataframe(profile)

    # Compute extremes for X axis
    #  -> this is needed for offseting of the values for the area chart
    minimal_x_value = data_frame[through_key].min()
    maximal_x_value = data_frame[through_key].max()

    # Obtain colours, which will be sorted in reverse
    key_colours = bokeh_helpers.get_unique_colours_for_(
        data_frame, by_key, sort_color_style=bokeh_helpers.ColourSort.Reverse
    )

    # Construct the data source (first we group the values by 'by_key' (one graph per each key).
    #   And then we compute the aggregations of the data grouped again, but by through key
    #   (i.e. for each value on X axis), the values are either accumulated or not
    data_source = {}
    for gn, by_key_group_frame in data_frame.groupby(by_key):
        data_source[gn] = [0]*(maximal_x_value + 1)
        through_data_group = by_key_group_frame.groupby(through_key)
        try:
            aggregation_function = getattr(through_data_group, func)
        except AttributeError:
            log.error("{} function is not supported as aggregation for this visualization".format(
                func
            ))
        source_data_frame = aggregation_function()
        if accumulate:
            accumulated_value = 0
            for index in range(minimal_x_value, maximal_x_value):
                accumulated_value += source_data_frame[of_key].get(index + minimal_x_value, 0)
                data_source[gn][index] = accumulated_value
        else:
            for t_k, o_k in source_data_frame[of_key].items():
                data_source[gn][t_k - minimal_x_value] = o_k

    # Construct the area chart
    area_chart = charts.Area(data_source, stack=stacked, color=key_colours)

    # Configure graph and return it
    bokeh_helpers.configure_graph(
        area_chart, profile, func, graph_title, x_axis_label, y_axis_label, graph_width
    )

    # Get minimal and maximal value of y; note we will add some small bonus to the maximal value
    values_data_frame = pandas.DataFrame(data_source)
    minimal_y_value = values_data_frame.min().min()
    value_maxima = values_data_frame.max()
    maximal_y_value = 1.05*(value_maxima.max() if not stacked else value_maxima.sum())

    # Configure flow specific options
    area_chart.legend.location = 'top_left'
    area_chart.legend.click_policy = 'hide'
    area_chart.x_range = models.Range1d(minimal_x_value, maximal_x_value - 1)
    area_chart.y_range = models.Range1d(minimal_y_value, maximal_y_value)
    return area_chart
