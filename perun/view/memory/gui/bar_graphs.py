"""This module contains the BAR graphs creating functions"""
import bokeh.charts as bch

__author__ = 'Radim Podola'


def bar_graph_uid_count(data_frame):
    """ Creates the Bar graph.

        This graph represents number of the memory operations
        at all the allocation locations stacked by snapshot.

    Arguments:
        data_frame(DataFrame): the Pandas DataFrame object

    Returns:
        Plot: Bokeh's plot object
    """
    tools = "pan, wheel_zoom, reset, save"
    x_axis_label = "Location"
    y_axis_label = "Number of the memory operations"
    title_text = "Number of the memory operations at all the allocation " \
                 "locations stacked by snapshot"

    for i in data_frame['uid']:
        if i.find(':') != -1:
            return None

    bar_graph = bch.Bar(data_frame, label='uid', values='amount', legend=None,
                        tooltips=[('snapshot', '@snapshots')], tools=tools,
                        stack='snapshots', agg='count', bar_width=0.4)

    bar_graph.title.text = title_text
    bar_graph.xaxis.axis_label = x_axis_label
    bar_graph.yaxis.axis_label = y_axis_label

    return bar_graph


def bar_graph_uid_sum(data_frame, unit):
    """ Creates the Bar graph.

        This graph represents summary of the allocated memory
        at all the allocation locations stacked by snapshot.

    Arguments:
        data_frame(DataFrame): the Pandas DataFrame object
        unit(str): memory amount unit

    Returns:
        Plot: Bokeh's plot object
    """
    tools = "pan, wheel_zoom, reset, save"
    x_axis_label = "Location"
    y_axis_label = "Summary of the allocated memory [{}]".format(unit)
    title_text = "Summary of the allocated memory at all the allocation " \
                 "locations stacked by snapshot"

    for i in data_frame['uid']:
        if i.find(':') != -1:
            return None

    bar_graph = bch.Bar(data_frame, label='uid', values='amount', legend=None,
                        tooltips=[('snapshot', '@snapshots')], tools=tools,
                        stack='snapshots', agg='sum', bar_width=0.4)

    bar_graph.title.text = title_text
    bar_graph.xaxis.axis_label = x_axis_label
    bar_graph.yaxis.axis_label = y_axis_label

    return bar_graph


def bar_graph_snaps_sum_subtype_stacked(data_frame, unit):
    """ Creates the Bar graph.

        This graph represents summary of the allocated memory
        over all the snapshots stacked by allocator.

    Arguments:
        data_frame(DataFrame): the Pandas DataFrame object
        unit(str): memory amount unit

    Returns:
        Plot: Bokeh's plot object
    """
    tools = "pan, wheel_zoom, reset, save"
    x_axis_label = "Snapshots"
    y_axis_label = "Summary of the allocated memory [{}]".format(unit)
    title_text = "Summary of the allocated memory over all the snapshots " \
                 "stacked by allocator"

    bar_graph = bch.Bar(data_frame, label='snapshots', values='amount',
                        agg='sum', stack='subtype', bar_width=0.4, tools=tools,
                        legend=None, tooltips=[('allocator', '@subtype')])

    bar_graph.legend.background_fill_alpha = 0.2

    bar_graph.title.text = title_text
    bar_graph.xaxis.axis_label = x_axis_label
    bar_graph.yaxis.axis_label = y_axis_label

    return bar_graph


def bar_graph_snaps_sum_uid_stacked(data_frame, unit):
    """ Creates the Bar graph.

        This graph represents summary of the allocated memory
        over all the snapshots stacked by location.

    Arguments:
        data_frame(DataFrame): the Pandas DataFrame object
        unit(str): memory amount unit

    Returns:
        Plot: Bokeh's plot object
    """
    tools = "pan, wheel_zoom, reset, save"
    x_axis_label = "Snapshots"
    y_axis_label = "Summary of the allocated memory [{}]".format(unit)
    title_text = "Summary of the allocated memory over all the snapshots " \
                 "stacked by location"

    bar_graph = bch.Bar(data_frame, label='snapshots', values='amount',
                        agg='sum', stack='uid', bar_width=0.4, legend=None,
                        tooltips=[('location', '@uid')], tools=tools)

    bar_graph.legend.background_fill_alpha = 0.2

    bar_graph.title.text = title_text
    bar_graph.xaxis.axis_label = x_axis_label
    bar_graph.yaxis.axis_label = y_axis_label

    return bar_graph


def bar_graph_snaps_count_subtype_grouped(data_frame):
    """ Creates the Bar graph.

        This graph represents number of the memory operations
        over all the snapshots grouped by allocator.

    Arguments:
        data_frame(DataFrame): the Pandas DataFrame object

    Returns:
        Plot: Bokeh's plot object
    """
    tools = "pan, wheel_zoom, reset, save"
    x_axis_label = "Snapshots"
    y_axis_label = "Number of the memory operations"
    title_text = "Number of the memory operations over all the " \
                 "snapshots grouped by allocator"

    bar_graph = bch.Bar(data_frame, label='snapshots', values='amount',
                        agg='count', group='subtype', bar_width=0.4,
                        legend=None, tooltips=[('allocator', '@subtype')],
                        tools=tools)

    bar_graph.legend.background_fill_alpha = 0.2

    bar_graph.title.text = title_text
    bar_graph.xaxis.axis_label = x_axis_label
    bar_graph.yaxis.axis_label = y_axis_label

    return bar_graph


def bar_graph_snaps_count_uid_grouped(data_frame):
    """ Creates the Bar graph.

        This graph represents number of the memory operations
        over all the snapshots grouped by location.

    Arguments:
        data_frame(DataFrame): the Pandas DataFrame object

    Returns:
        Plot: Bokeh's plot object
    """
    tools = "pan, wheel_zoom, reset, save"
    x_axis_label = "Snapshots"
    y_axis_label = "Number of the memory operations"
    title_text = "Number of the memory operations over all the snapshots " \
                 "grouped by location"

    bar_graph = bch.Bar(data_frame, label='snapshots', values='amount',
                        agg='count', group='uid', bar_width=0.4, legend=None,
                        tooltips=[('location', '@uid')], tools=tools)

    bar_graph.legend.background_fill_alpha = 0.2

    bar_graph.title.text = title_text
    bar_graph.xaxis.axis_label = x_axis_label
    bar_graph.yaxis.axis_label = y_axis_label

    return bar_graph


if __name__ == "__main__":
    pass
