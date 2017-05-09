"""This module contains the Flow usage graph creating functions"""
import bokeh.palettes as palletes
import bokeh.plotting as bpl
import bokeh.models as bm

__author__ = 'Radim Podola'


def _add_tools(figure):
    """ Adds tools to Bokeh's plot.

    Arguments:
        figure(Plot): the Bokeh's plot
    """
    hover = bm.HoverTool(tooltips=dict(location="@name",
                                       amount='@y',
                                       snapshot='@x'))
    figure.add_tools(bm.PanTool())
    figure.add_tools(bm.WheelZoomTool())
    figure.add_tools(bm.ResetTool())
    figure.add_tools(bm.SaveTool())
    figure.add_tools(hover)


def _add_callback(key, patch, line):
    """ Adds JS callback to Bokeh's plot.

    Arguments:
        figure(Plot): the Bokeh's plot

    Returns:
        Toggle: Bokeh's Toggle model object
    """
    # JS callback code
    callback_code = """
    l_object.visible = toggle.active
    p_object.visible = toggle.active
    """

    callback = bm.CustomJS.from_coffeescript(code=callback_code, args={})
    toggle = bm.Toggle(label=key, button_type="primary", callback=callback)
    callback.args = {'toggle': toggle, 'p_object': patch, 'l_object': line}

    return toggle


def _get_plot(data_frame):
    """ Creates Flow usage Bokeh's plot.

    Arguments:
        data_frame(any): the Pandas DataFrame object

    Returns:
        tuple: 1st is Bokeh's figure,
               2nd is list of Bokeh's toggles
    """
    toggles = []
    data = {}
    snap_group = data_frame.groupby('snapshots')

    # creating figure for plotting
    fig = bpl.figure(width=1200, height=500)

    # +1 because of ending process memory should be 0 -- nicer visualization
    snap_count = len(snap_group) + 1

    # preparing data structure
    for uid in data_frame['uid']:
        data[uid] = [0]*snap_count
    # calculating summary of the amount for each location's snapshot
    for i, group in snap_group:
        for _, series in group.iterrows():
            data[series['uid']][i - 1] += series['amount']

    # get colors pallet
    colors_count = len(data.keys()) if len(data.keys()) <= 256 else 256
    colors = palletes.viridis(colors_count)

    for key, color in zip(data.keys(), colors):
        # creating DataSource for each UID
        source = bpl.ColumnDataSource({'x': range(1, snap_count + 1),
                                       'y': data[key],
                                       'name': [key]*snap_count})
        patch = fig.patch('x', 'y', source=source, color=color, fill_alpha=0.3)
        line = fig.line('x', 'y', source=source, color=color, line_width=3)

        toggles.append(_add_callback(key, patch, line))

    return fig, toggles


def flow_usage_graph(data_frame, unit):
    """ Creates Flow usage graph.

    Arguments:
        data_frame(any): the Pandas DataFrame object
        unit(str): memory amount unit

    Returns:
        tuple: 1st is Bokeh's figure,
               2nd is list of Bokeh's toggles
    """
    y_axis_label = "Summary of the allocated memory [{}]".format(unit)
    x_axis_label = "Snapshots"
    title_text = "Summary of the allocated memory at all the allocation " \
                 "locations over all the snapshots"

    fig, toggles = _get_plot(data_frame)

    _add_tools(fig)
    fig.title.text = title_text
    fig.xaxis.axis_label = x_axis_label
    fig.yaxis.axis_label = y_axis_label

    return fig, toggles


if __name__ == "__main__":
    pass
