"""Collection of helper functions for working with bokeh graphs"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Any
from collections.abc import MutableMapping, Iterable

from enum import Enum
import demandimport
with demandimport.enabled():
    import bokeh.layouts as bk_layouts
    import bokeh.palettes as bk_palettes
    import bokeh.plotting as bk_plotting
    import bokeh.themes.theme as bk_theme

import perun.profile.helpers as profiles
from perun.utils import log

if TYPE_CHECKING:
    import pandas as pd


__author__ = 'Tomas Fiedor'

GRAPH_LR_PADDING = 0
GRAPH_B_PADDING = 100
GRAPH_T_PADDING = 50


class ColourSort(Enum):
    """Enumeration of sort modes"""
    REVERSE = 1
    BY_OCCURRENCE = 2


def _sort_colours(
    colours: bk_palettes.Palette, sort_color_style: ColourSort, keys: Iterable[str]
) -> List[str]:
    """Sorts the colours corresponding to the keys according to the given style

    Note: For different visualizations and outputs we want the colours in different format,
    but still as a list. Some need them in reverse order, some as they are in the palette and
    some (like e.g. Bars) needs to be tied to the keys, as they are occurring in the graph.

    :param colours: list of chosen colour palette
    :param sort_color_style: style of the sorting of the colours
    :param keys: list of keys, sorted by their appearance
    :returns: sorted colours according to the chosen sorting mode
    """
    if sort_color_style == ColourSort.REVERSE:
        return list(colours[::-1])
    keys_to_colour = list(zip(keys, colours))
    keys_to_colour.sort()
    return list(map(lambda x: x[1], keys_to_colour))


def get_unique_colours_for_(
    data_source: pd.DataFrame, key: str, sort_color_style: ColourSort = ColourSort.BY_OCCURRENCE
) -> List[str]:
    """Returns list of colours (sorted according to the legend); up to 256 colours.

    :param data_source: data frame for which we want to get unique colours
    :param key: key for which we are generating unique colours
    :param sort_color_style: style of sorting and assigning the values
    :returns: sorted colours according to the chosen sorting mode
    """
    unique_keys = data_source[key].unique()
    unique_keys_num = len(unique_keys)

    if unique_keys_num > 256:
        log.error("plotting to Bokeh backend currently supports only 256 colours")

    # This is temporary workaround for non-sorted legends
    colour_palette: bk_palettes.Palette = bk_palettes.viridis(unique_keys_num)
    return _sort_colours(colour_palette, sort_color_style, unique_keys)


def build_bokeh_theme() -> bk_theme.Theme:
    """Create Bokeh theme object that can be used to override default styling.

    :returns: a Bokeh theme for plots.
    """
    return bk_theme.Theme(
        json={
            "attrs": {
                "figure": {
                    "min_border_left": GRAPH_LR_PADDING,
                    "min_border_right": GRAPH_LR_PADDING,
                    "min_border_top": GRAPH_T_PADDING,
                    "min_border_bottom": GRAPH_B_PADDING,
                    "outline_line_width": 2,
                    "outline_line_color": "black",
                },
                "Grid": {
                    "minor_grid_line_color": "grey",
                    "minor_grid_line_alpha": 0.2,
                    "grid_line_color": "grey",
                    "grid_line_alpha": 0.4,
                },
                "Axis": {
                    "axis_label_text_font": "helvetica",
                    "axis_label_text_font_style": "bold",
                    "axis_label_text_font_size": "14pt",
                    "major_label_text_font_style": "bold",
                    "major_tick_line_width": 2,
                    "minor_tick_line_width": 2,
                    "major_tick_in": 8,
                    "major_tick_out": 8,
                    "minor_tick_in": 4,
                    "minor_tick_out": 4,
                },
                "Title": {
                    "text_font": "helvetica",
                    "text_font_style": "bold",
                    "text_font_size": "21pt",
                    "align": "center",
                },
                "Legend": {
                    "border_line_color": "black",
                    "border_line_width": 2,
                    "border_line_alpha": 1.0,
                    "label_text_font_style": "bold",
                    "location": "top_right",
                    "click_policy": "hide",
                },
            },
        })


# TODO: remove
def _configure_axis(axis, axis_title):
    """ Sets the graph's axis visual style

    :param any axis: Bokeh plot's axis object
    :param str axis_title: title of the axis
    """
    axis.axis_label_text_font = 'helvetica'
    axis.axis_label_text_font_style = 'bold'
    axis.axis_label_text_font_size = '14pt'
    axis.axis_label = axis_title
    axis.major_label_text_font_style = 'bold'
    axis.major_tick_line_width = 2
    axis.minor_tick_line_width = 2
    axis.major_tick_in = 8
    axis.major_tick_out = 8
    axis.minor_tick_in = 4
    axis.minor_tick_out = 4


# TODO: remove
def _configure_grid(grid):
    """Sets the given grid

    :param bokeh.Grid grid: either x or y grid
    """
    grid.minor_grid_line_color = 'grey'
    grid.minor_grid_line_alpha = 0.2
    grid.grid_line_color = 'grey'
    grid.grid_line_alpha = 0.4


# TODO: remove
def _configure_title(graph_title, title):
    """ Sets the graph's title visual style

    :param bokeh.Title graph_title: bokeh title of the graph
    :param str title: title of the graph
    """
    graph_title.text_font = 'helvetica'
    graph_title.text_font_style = 'bold'
    graph_title.text_font_size = '21pt'
    graph_title.align = 'center'
    graph_title.text = title


# TODO: remove
def _configure_graph_canvas(graph, graph_width):
    """Sets the canvas of the graph, its width and padding

    :param bokeh.Figure graph: figure for which we will be setting canvas
    :param int graph_width: width of bokeh graph
    """
    graph.width = graph_width
    graph.min_border_left = GRAPH_LR_PADDING
    graph.min_border_right = GRAPH_LR_PADDING
    graph.min_border_top = GRAPH_T_PADDING
    graph.min_border_bottom = GRAPH_B_PADDING
    graph.outline_line_width = 2
    graph.outline_line_color = 'black'

    for renderer in graph.renderers:
        if hasattr(renderer, 'glyph'):
            renderer.glyph.line_width = 2
            renderer.glyph.line_color = 'black'


# TODO: remove
def _configure_legend(graph):
    """
    :param bokeh.Figure graph: bokeh graph for which we will configure the legend
    """
    graph.legend.border_line_color = 'black'
    graph.legend.border_line_width = 2
    graph.legend.border_line_alpha = 1.0
    graph.legend.label_text_font_style = 'bold'
    graph.legend.location = 'top_right'
    graph.legend.click_policy = 'hide'


# TODO: remove
def configure_graph(graph, profile, func, graph_title, x_axis_label, y_axis_label, graph_width):
    """Configures the created graph with basic stuff---axes, canvas, title

    :param bokeh.Figure graph: bokeh graph, that we want to configure with basic stuff
    :param dict profile: dictionary with measured data
    :param str func: function that will be used for aggregation of the data
    :param str x_axis_label: label on the x axis
    :param str y_axis_label: label on the y axis
    :param str graph_title: name of the graph
    :param int graph_width: width of the created bokeh graph
    """
    # Stylize the graph
    _configure_graph_canvas(graph, graph_width)
    _configure_axis(graph.xaxis, x_axis_label)
    _configure_axis(graph.yaxis, y_axis_label)
    _configure_title(graph.title, graph_title)
    _configure_legend(graph)
    _configure_grid(graph.ygrid)
    _configure_grid(graph.grid)

    # If of key is ammount, add unit
    if func not in ('count', 'nunique') and not y_axis_label.endswith("]"):
        profile_type = profile['header']['type']
        type_unit = profile['header']['units'][profile_type]
        graph.yaxis.axis_label = y_axis_label + " [{}]".format(type_unit)


def add_y_units(profile_header: MutableMapping[str, Any], of_key: str, y_axis_label: str) -> str:
    """Add units to Y axis label if the Y dimension has one.

    :param profile_header: the header part of a profile.
    :param of_key: the Y dimension name.
    :param y_axis_label: the current Y dimension label.

    :returns: the Y dimension label with a unit, if eligible.
    """
    if of_key in ('count', 'nunique') or y_axis_label.endswith("]"):
        # Skip if the label already has a unit or the of_key doesn't have a unit
        return y_axis_label
    # The of_key should have a unit
    profile_type = profile_header['type']
    type_unit = None
    try:
        # Check if we have a 'unit' corresponding to the profile type
        type_unit = profile_header['units'][profile_type]
    except KeyError:
        # The profile type might be called a bit differently in the 'units', e.g.,
        # 'mixed' -> 'mixed(time delta)'
        for unit_name, unit in profile_header["units"].items():
            if profile_type in unit_name:
                type_unit = unit
                break
    return y_axis_label if type_unit is None else f"{y_axis_label} [{type_unit}]"


# TODO: remove
def save_graphs_in_column(graphs, filename, view_in_browser=False):
    """
    :param list graphs: list of bokeh figure that will be outputed in stretchable graph
    :param str filename: name of the file, where the column graph will be saved
    :param bool view_in_browser: true if the outputed graph should be viewed straight in the browser
    """
    output = bk_layouts.column(graphs, sizing_mode="stretch_both")
    bk_plotting.output_file(filename)

    if view_in_browser:
        bk_plotting.show(output)
    else:
        bk_plotting.save(output, filename)


# TODO: update
def process_profile_to_graphs(factory_module, profile, filename, view_in_browser, func, of_key,
                              **kwargs):
    """Wrapper function for constructing the graphs from profile, saving it and viewing.

    Wrapper function that takes the factory module, constructs the graph for the given profile,
    and then saves it in filename and optionally view in the registered browser.

    :param module factory_module: module which will create the the graph
    :param dict profile: profile that will be processed
    :param str filename: output filename for the bokeh graph
    :param bool view_in_browser: true if the created graph should be view in registered browser
        after it is constructed.
    :param function func: function used for aggregation of the data
    :param str of_key: key that will be aggregated in the graph
    :param dict kwargs: rest of the keyword arguments
    :raises AttributeError: when the factory_module has not some of the functions
    """
    profiles.is_key_aggregatable_by(profile, func, of_key, "of_key")

    graph = factory_module.create_from_params(profile, func, of_key, **kwargs)
    save_graphs_in_column([graph], filename, view_in_browser)