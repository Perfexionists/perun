"""This module contains methods needed by Perun logic"""
import json

import pandas as pd
import bokeh.plotting as bpl
import bokeh.layouts as bla
import perun.view.memory.cli.profile_converters as converter
import perun.view.memory.gui.bar_graphs as bars
import perun.view.memory.gui.flamegraph as flame
import perun.view.memory.gui.flow_usage_graph as flow
import perun.view.memory.gui.heat_map_graph as heat

__author__ = 'Radim Podola'


def show(profile, choice):
    """ Main function which handle visualization choices

    Arguments:
        profile(dict): the memory profile
    """
    if choice == 0:
        draw_flow_bar_graphs(profile, "bars.html")
    elif choice == 1:
        draw_flow_usage(profile, "usage.html")
    elif choice == 2:
        flame.draw_flame_graph(profile, "flame.svg")
    elif choice == 3:
        draw_heat_map(profile, "heat.html")


    return


def draw_heat_map(profile, filename):
    heat_table = converter.create_heat_map(profile)
    graph = heat.heat_map_graph(heat_table)

    bpl.output_file(filename)
    bpl.show(graph)


def get_flow_usage_grid(df, amount_unit, graph_width):
    graph, toggles = flow.flow_usage_graph(df, amount_unit)

    _set_title_visual(graph.title)
    _set_axis_visual(graph.xaxis)
    _set_axis_visual(graph.yaxis)
    _set_graphs_width(graph, graph_width)

    widget = bla.widgetbox(toggles)

    grid = bla.row(graph, widget)

    return grid


def draw_flow_usage(profile, filename):
    """ Creates and draw a grid of the Flow usage graph.

    Arguments:
        profile(dict): the memory profile
        filename(str): filename of the output file, expected is html format
    """
    graph_width = 1200

    header = profile['header']
    profile_type = header['type']
    amount_unit = header['units'][profile_type]

    # converting memory profile to flow usage table
    flow_table = converter.create_flow_table(profile)
    # converting flow usage table to pandas DataFrame
    df = pd.DataFrame.from_dict(flow_table)
    # obtaining grid of flow usage graph
    grid = get_flow_usage_grid(df, amount_unit, graph_width)

    bpl.output_file(filename)
    bpl.show(grid)


def draw_flow_bar_graphs(profile, filename):
    """ Creates and draw a grid of the Bar's graphs.

    Arguments:
        profile(dict): the memory profile
        filename(str): filename of the output file, expected is html format
    """
    bar_graph_width = 800

    header = profile['header']
    profile_type = header['type']
    amount_unit = header['units'][profile_type]

    # converting memory profile to allocations table
    bar_table = converter.create_allocations_table(profile)
    # converting allocations table to pandas DataFrame
    df = pd.DataFrame.from_dict(bar_table)
    # obtaining grid of Bar's graphs
    grid = get_flow_bar_graphs_grid(df, amount_unit, bar_graph_width)

    bpl.output_file(filename)
    bpl.show(grid)


def get_flow_bar_graphs_grid(df, amount_unit, bar_width):
    graphs = []

    r1c1 = bars.flow_bar_graph_snaps_sum_subtype_stacked(df, amount_unit)
    graphs.append(r1c1)
    r1c2 = bars.flow_bar_graph_snaps_sum_uid_stacked(df, amount_unit)
    graphs.append(r1c2)
    r2c1 = bars.flow_bar_graph_snaps_count_subtype_grouped(df)
    graphs.append(r2c1)
    r2c2 = bars.flow_bar_graph_snaps_count_uid_grouped(df)
    graphs.append(r2c2)
    r3c1 = bars.flow_bar_graph_uid_count(df)
    graphs.append(r3c1)
    r3c2 = bars.flow_bar_graph_uid_sum(df, amount_unit)
    graphs.append(r3c2)

    for graph in graphs:
        _set_title_visual(graph.title)
        _set_axis_visual(graph.xaxis)
        _set_axis_visual(graph.yaxis)
        _set_graphs_width(graph, bar_width)

    # creating layout grid
    row1 = bla.row(r1c1, r1c2)
    row2 = bla.row(r2c1, r2c2)
    row3 = bla.row(r3c1, r3c2)
    grid = bla.column(row1, row2, row3)

    return grid


def _set_title_visual(title):
    title.text_font = 'helvetica'
    title.text_font_style = 'bold'
    title.text_font_size = '12pt'
    title.align = 'center'


def _set_axis_visual(axis):
    axis.axis_label_text_font_style = 'italic'
    axis.axis_label_text_font_size = '12pt'


def _set_graphs_width(graph, width):
    graph.plot_width = width


if __name__ == "__main__":
    with open('memory.perf') as prof_json:
        profile = json.load(prof_json)
    show(profile, 1)