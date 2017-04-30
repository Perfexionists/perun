"""This module contains methods needed by Perun logic"""
import json
import pandas as pd
import bokeh.charts as charts
import bokeh.layouts as layouts
import perun.view.memory.cli.profile_converters as converter

__author__ = 'Radim Podola'

_amount_unit = ''

def show(profile):
    """ Main function which handle visualization choices

    Arguments:
        profile(dict): the memory profile
    """
    global _amount_unit
    _amount_unit = profile['header']['units']['memory']

    table = converter.create_allocations_table(profile)

    df = pd.DataFrame.from_dict(table)
    print_flow_bar_graphs(df)


def print_flow_bar_graphs(df):
    charts.output_file("flow_bars.html")

    row1 = layouts.row(flow_bar_graph_snaps_sum_subtype_stacked(df),
                       flow_bar_graph_snaps_sum_uid_stacked(df))
    row2 = layouts.row(flow_bar_graph_snaps_count_subtype_grouped(df),
                       flow_bar_graph_snaps_count_uid_grouped(df))
    row3 = layouts.row(flow_bar_graph_uid_count(df),
                       flow_bar_graph_uid_sum(df))
    grid = layouts.column(row1, row2, row3)
    charts.show(grid)


def flow_bar_graph_uid_count(data_frame):
    TOOLS = "pan, wheel_zoom, reset, save"
    y_axis_label = "Number of the memory operations"

    bar_graph = charts.Bar(data_frame, label='uid', values='amount',
                           agg='count', bar_width=0.4, legend=None, tools=TOOLS)

    bar_graph.title.text = "Uid"
    bar_graph.yaxis.axis_label = y_axis_label

    return bar_graph


def flow_bar_graph_uid_sum(data_frame):
    TOOLS = "pan, wheel_zoom, reset, save"
    y_axis_label = "Summary of the allocated memory [{}]".format(_amount_unit)

    bar_graph = charts.Bar(data_frame, label='uid', values='amount',
                           agg='sum', bar_width=0.4, legend=None, tools=TOOLS)

    bar_graph.title.text = "Uid"
    bar_graph.yaxis.axis_label = y_axis_label

    return bar_graph


def flow_bar_graph_snaps_sum_subtype_stacked(data_frame):
    TOOLS = "pan, wheel_zoom, reset, save"
    y_axis_label = "Summary of the allocated memory [{}]".format(_amount_unit)

    bar_graph = charts.Bar(data_frame, label='snapshots', values='amount',
                           agg='sum', stack='subtype', bar_width=0.4,
                           tools=TOOLS)

    bar_graph.legend.background_fill_alpha = 0.2
    bar_graph.title.text = "subtype..."
    bar_graph.yaxis.axis_label = y_axis_label

    return bar_graph


def flow_bar_graph_snaps_sum_uid_stacked(data_frame):
    TOOLS = "pan, wheel_zoom, reset, save"
    y_axis_label = "Summary of the allocated memory [{}]".format(_amount_unit)

    bar_graph = charts.Bar(data_frame, label='snapshots', values='amount',
                           agg='sum', stack='uid', bar_width=0.4,
                           tools=TOOLS)

    bar_graph.legend.background_fill_alpha = 0.2
    bar_graph.title.text = "uid..."
    bar_graph.yaxis.axis_label = y_axis_label

    return bar_graph


def flow_bar_graph_snaps_count_subtype_grouped(data_frame):
    TOOLS = "pan, wheel_zoom, reset, save"
    y_axis_label = "Number of the memory operations"

    bar_graph = charts.Bar(data_frame, label='snapshots', values='amount',
                           agg='count', group='subtype', bar_width=0.4,
                           tools=TOOLS)

    bar_graph.legend.background_fill_alpha = 0.2
    bar_graph.title.text = "type..."
    bar_graph.yaxis.axis_label = y_axis_label

    return bar_graph


def flow_bar_graph_snaps_count_uid_grouped(data_frame):
    TOOLS = "pan, wheel_zoom, reset, save"
    y_axis_label = "Number of the memory operations"

    bar_graph = charts.Bar(data_frame, label='snapshots', values='amount',
                           agg='count', group='uid', bar_width=0.4,
                           tools=TOOLS)

    bar_graph.legend.background_fill_alpha = 0.2
    bar_graph.title.text = "uid..."
    bar_graph.yaxis.axis_label = y_axis_label

    return bar_graph


if __name__ == "__main__":
    with open('memory.perf') as prof_json:
        profile = json.load(prof_json)
    show(profile)