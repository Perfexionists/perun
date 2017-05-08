"""This module contains methods needed by Perun logic"""
import json
import subprocess
import pandas as pd
import bokeh as bk
import itertools
import bokeh.charts as bch
import bokeh.models as bm
import bokeh.plotting as bpl
import perun.view.memory.cli.profile_converters as converter

import bokeh.layouts as layouts

__author__ = 'Radim Podola'

_amount_unit = ''
_bar_graph_width = 800

def show(profile):
    """ Main function which handle visualization choices

    Arguments:
        profile(dict): the memory profile
    """
    global _amount_unit
    _amount_unit = profile['header']['units']['memory']

    #print_flame_graph(profile)
    return

    bar_table = converter.create_allocations_table(profile)

    df = pd.DataFrame.from_dict(bar_table)
    print_flow_bar_graphs(df)

    #flow_table = converter.create_flow_table(profile)
    #df = pd.DataFrame.from_dict(flow_table)
    #print_flow_usage(df)

    heat = converter.create_heat_map(profile)
    print_heat_map(heat)


def print_flame_graph(profile):
    flame = converter.create_flame_graph_format(profile)

    header = profile['header']
    profile_type = header['type']
    title = "{} consumption of {} {} {}".format(profile_type,
                                                header['cmd'],
                                                header['params'],
                                                header['workload'])
    units = header['units'][profile_type]

    with open('perf.svg', 'w') as out:
        p = subprocess.Popen(['./flamegraph.pl',
                              '--title', title,
                              '--countname', units,
                              '--reverse',
                              '--height=20'],
                             stdin=subprocess.PIPE,
                             stdout=out)
        p.communicate(bytes(''.join(flame), encoding='UTF-8'))


def print_heat_map(heat):
    tools = "pan, wheel_zoom, reset, save, hover"
    data = {'x': [1] * 3 + [2] * 3 + [3] * 3,
            'uses': [4, 5, 8, 1, 2, 4, 6, 5, 4],
            'add': [151, 171, 191, 152, 172, 192, 153, 173, 193],
            'address': [150, 170, 190] * 3}

    hover = bm.HoverTool(
        tooltips=[
            ("date", "@add"),
        ]
    )

    hm = bch.HeatMap(data, x=bch.bins('x', bins=3), y=bch.bins('address', bins=3), values='uses',
                     title='Fruits', stat=None, tools=[hover],
                     palette=bk.palettes.YlOrRd9)

    p = bpl.figure(plot_width=400, plot_height=400)
    p.quad(top=[2, 3, 4], bottom=[1, 2, 3], left=[1, 2, 3],
           right=[2, 3, 4], color="#B3DE69")

    bpl.output_file('heatmap.html')
    bch.show(p)


def print_flow_usage(df):
    tools = "pan, wheel_zoom, reset, save"
    y_axis_label = "Summary of the allocated memory [{}]".format(_amount_unit)
    x_axis_label = "Snapshots"
    title_text = "Summary of the allocated memory at all the allocation " \
                 "locations over all the snapshots"

    snap_group = df.groupby('snapshots')
    # +1 because of ending process memory should be 0 -- nicer visualization
    snap_count = len(snap_group) + 1
    # get colors pallet
    pallet = bk.palettes.viridis(snap_count)
    # create a color iterator
    colors = itertools.cycle(pallet)

    # preparing data structure
    data = {}
    for uid in df['uid']:
        data[uid] = [0]*snap_count

    for i, group in snap_group:
        for index, series in group.iterrows():
            data[series['uid']][i - 1] += series['amount']

    # JS callback code
    callback_code = """
    l_object.visible = toggle.active
    p_object.visible = toggle.active
    """

    toggles = []
    x = [i+1 for i in range(snap_count)]

    fig = bpl.figure(width=1200, height=500, tools=tools)

    for key, color in zip(data.keys(), colors):
        source = bpl.ColumnDataSource({'x': x,'values': data[key],
                                       'name': [key]*snap_count})
        pat = fig.patch('x', 'values', source=source, color=color,
                        fill_alpha=0.3)
        line = fig.line('x', 'values', source=source, color=color,
                        line_width=3)

        callback = bm.CustomJS.from_coffeescript(code=callback_code, args={})
        toggle = bm.Toggle(label=key, button_type="primary", callback=callback)
        callback.args = {'toggle': toggle, 'p_object': pat, 'l_object': line}
        toggles.append(toggle)

    hover = bm.HoverTool(plot=fig, tooltips=dict(location="@name",
                                                 amount='@values',
                                                 snapshot='@x'))
    fig.tools.append(hover)

    set_title_visual(fig.title, title_text)
    set_axis_visual(fig.xaxis, x_axis_label)
    set_axis_visual(fig.yaxis, y_axis_label)

    bpl.output_file('usage.html')
    bch.show(layouts.row(fig, layouts.widgetbox(toggles)))


def set_title_visual(title, label):
    title.text = label
    title.text_font = 'helvetica'
    title.text_font_style = 'bold'
    title.text_font_size = '12pt'
    title.align = 'center'


def set_axis_visual(axis, label):
    axis.axis_label = label
    axis.axis_label_text_font_style = 'italic'
    axis.axis_label_text_font_size = '12pt'


def print_flow_bar_graphs(df):
    bpl.output_file("flow_bars.html")

    r1c1 = flow_bar_graph_snaps_sum_subtype_stacked(df)
    r1c2 = flow_bar_graph_snaps_sum_uid_stacked(df)
    r2c1 = flow_bar_graph_snaps_count_subtype_grouped(df)
    r2c2 = flow_bar_graph_snaps_count_uid_grouped(df)
    r3c1 = flow_bar_graph_uid_count(df)
    r3c2 = flow_bar_graph_uid_sum(df)

    row1 = layouts.row(r1c1, r1c2)
    row2 = layouts.row(r2c1, r2c2)
    row3 = layouts.row(r3c1, r3c2)

    # creating layout grid
    grid = layouts.column(row1, row2, row3)
    bch.show(grid)


def flow_bar_graph_uid_count(data_frame):
    tools = "pan, wheel_zoom, reset, save"
    x_axis_label = "Location"
    y_axis_label = "Number of the memory operations"
    title_text = "Number of the memory operations at all the allocation " \
                 "locations stacked by snapshot"

    bar_graph = bch.Bar(data_frame, label='uid', values='amount', legend=None,
                        tooltips=[('snapshot', '@snapshots')], tools=tools,
                        stack='snapshots', agg='count', bar_width=0.4)

    bar_graph.plot_width = _bar_graph_width

    set_title_visual(bar_graph.title, title_text)
    set_axis_visual(bar_graph.xaxis, x_axis_label)
    set_axis_visual(bar_graph.yaxis, y_axis_label)

    return bar_graph


def flow_bar_graph_uid_sum(data_frame):
    tools = "pan, wheel_zoom, reset, save"
    x_axis_label = "Location"
    y_axis_label = "Summary of the allocated memory [{}]".format(_amount_unit)
    title_text = "Summary of the allocated memory at all the allocation " \
                 "locations stacked by snapshot"

    bar_graph = bch.Bar(data_frame, label='uid', values='amount', legend=None,
                        tooltips=[('snapshot', '@snapshots')], tools=tools,
                        stack='snapshots', agg='sum', bar_width=0.4)

    bar_graph.plot_width = _bar_graph_width

    set_title_visual(bar_graph.title, title_text)
    set_axis_visual(bar_graph.xaxis, x_axis_label)
    set_axis_visual(bar_graph.yaxis, y_axis_label)

    return bar_graph


def flow_bar_graph_snaps_sum_subtype_stacked(data_frame):
    tools = "pan, wheel_zoom, reset, save"
    x_axis_label = "Snapshots"
    y_axis_label = "Summary of the allocated memory [{}]".format(_amount_unit)
    title_text = "Summary of the allocated memory over all the snapshots " \
                 "stacked by allocator"

    bar_graph = bch.Bar(data_frame, label='snapshots', values='amount',
                        agg='sum', stack='subtype', bar_width=0.4, tools=tools,
                        legend=None, tooltips=[('allocator', '@subtype')])

    bar_graph.legend.background_fill_alpha = 0.2
    bar_graph.plot_width = _bar_graph_width

    set_title_visual(bar_graph.title, title_text)
    set_axis_visual(bar_graph.xaxis, x_axis_label)
    set_axis_visual(bar_graph.yaxis, y_axis_label)

    return bar_graph


def flow_bar_graph_snaps_sum_uid_stacked(data_frame):
    tools = "pan, wheel_zoom, reset, save"
    x_axis_label = "Snapshots"
    y_axis_label = "Summary of the allocated memory [{}]".format(_amount_unit)
    title_text = "Summary of the allocated memory over all the snapshots " \
                 "stacked by location"

    bar_graph = bch.Bar(data_frame, label='snapshots', values='amount',
                           agg='sum', stack='uid', bar_width=0.4, legend=None,
                           tooltips=[('location', '@uid')], tools=tools)

    bar_graph.legend.background_fill_alpha = 0.2
    bar_graph.plot_width = _bar_graph_width

    set_title_visual(bar_graph.title, title_text)
    set_axis_visual(bar_graph.xaxis, x_axis_label)
    set_axis_visual(bar_graph.yaxis, y_axis_label)

    return bar_graph


def flow_bar_graph_snaps_count_subtype_grouped(data_frame):
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
    bar_graph.plot_width = _bar_graph_width

    set_title_visual(bar_graph.title, title_text)
    set_axis_visual(bar_graph.xaxis, x_axis_label)
    set_axis_visual(bar_graph.yaxis, y_axis_label)

    return bar_graph


def flow_bar_graph_snaps_count_uid_grouped(data_frame):
    tools = "pan, wheel_zoom, reset, save"
    x_axis_label = "Snapshots"
    y_axis_label = "Number of the memory operations"
    title_text = "Number of the memory operations over all the snapshots " \
                 "grouped by location"

    bar_graph = bch.Bar(data_frame, label='snapshots', values='amount',
                        agg='count', group='uid', bar_width=0.4, legend=None,
                        tooltips=[('location', '@uid')], tools=tools)

    bar_graph.legend.background_fill_alpha = 0.2
    bar_graph.plot_width = _bar_graph_width

    set_title_visual(bar_graph.title, title_text)
    set_axis_visual(bar_graph.xaxis, x_axis_label)
    set_axis_visual(bar_graph.yaxis, y_axis_label)

    return bar_graph


if __name__ == "__main__":
    with open('memory.perf') as prof_json:
        profile = json.load(prof_json)
    show(profile)