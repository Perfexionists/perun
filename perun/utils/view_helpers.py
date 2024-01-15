"""Collection of helper functions for working with bokeh graphs"""
from __future__ import annotations

# Standard Imports
from enum import Enum
from typing import TYPE_CHECKING, Any

# Third-Party Imports
import bokeh.palettes as bk_palettes
import bokeh.plotting as bk_plot
import bokeh.themes.theme as bk_theme
import holoviews as hv

# Perun Imports
from perun.utils import decorators, log
import perun.profile.helpers as profiles

if TYPE_CHECKING:
    import pandas as pd

    from collections.abc import MutableMapping, Iterable
    from types import ModuleType
    from perun.profile.factory import Profile


GRAPH_LR_PADDING: int = 0
GRAPH_B_PADDING: int = 100
GRAPH_T_PADDING: int = 50


class ColourSort(Enum):
    """Enumeration of sort modes"""

    REVERSE = 1
    BY_OCCURRENCE = 2


def _sort_colours(
    colours: bk_palettes.Palette, sort_color_style: ColourSort, keys: Iterable[str]
) -> list[str]:
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
    data_source: pd.DataFrame,
    key: str,
    sort_color_style: ColourSort = ColourSort.BY_OCCURRENCE,
) -> list[str]:
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
        }
    )


def add_y_units(profile_header: MutableMapping[str, Any], of_key: str, y_axis_label: str) -> str:
    """Add units to Y axis label if the Y dimension has one.

    :param profile_header: the header part of a profile.
    :param of_key: the Y dimension name.
    :param y_axis_label: the current Y dimension label.

    :returns: the Y dimension label with a unit, if eligible.
    """
    if of_key in ("count", "nunique") or y_axis_label.endswith("]"):
        # Skip if the label already has a unit or the of_key doesn't have a unit
        return y_axis_label
    # The of_key should have a unit
    profile_type = profile_header["type"]
    type_unit = None
    try:
        # Check if we have a 'unit' corresponding to the profile type
        type_unit = profile_header["units"][profile_type]
    except KeyError:
        # The profile type might be called a bit differently in the 'units', e.g.,
        # 'mixed' -> 'mixed(time delta)'
        for unit_name, unit in profile_header["units"].items():
            if profile_type in unit_name:
                type_unit = unit
                break
    return y_axis_label if type_unit is None else f"{y_axis_label} [{type_unit}]"


def save_view_graph(
    graph: hv.Chart | hv.Layout | hv.Overlay,
    filename: str,
    view_in_browser: bool = False,
) -> None:
    """Save or view the provided holoviews graph.

    :param graph: a holoviews figure (or their composition) that will be rendered.
    :param filename: name of the output file, where the graph will be saved.
    :param view_in_browser: ``True`` if the graph should be displayed straight in the browser.
    """
    if view_in_browser:
        bk_plot.output_file(filename)
        bk_plot.show(hv.render(graph))
    else:
        hv.save(graph, filename)


def process_profile_to_graphs(
    factory_module: ModuleType,
    profile: Profile,
    filename: str,
    view_in_browser: bool,
    func: str,
    of_key: str,
    **kwargs: Any,
) -> None:
    """Wrapper function for constructing the graphs from profile, saving it and viewing.

    Wrapper function that takes the factory module, constructs the graph for the given profile,
    and then saves it in filename and optionally view in the registered browser.

    :param factory_module: module which will create the graph.
    :param profile: a Perun profile that will be processed.
    :param filename: output filename for the graph.
    :param view_in_browser: ``True`` if the created graph should be displayed in registered browser
           after it is constructed.
    :param func: function used for aggregation of the data.
    :param of_key: key that will be aggregated in the graph.
    :param kwargs: rest of the keyword arguments.
    :raises AttributeError: when the factory_module is missing some of the functions.
    :raises InvalidParameterException: if the of_key does not support the given aggregation func.
    """
    profiles.is_key_aggregatable_by(profile, func, of_key, "of_key")
    graph = factory_module.create_from_params(profile, func, of_key, **kwargs)
    save_view_graph(graph, filename, view_in_browser)


@decorators.always_singleton
def lazy_init_holoviews() -> bool:
    """
    Lazily inits bokeh extension and sets theme for the renderer
    """
    hv.extension("bokeh")
    hv.renderer("bokeh").theme = build_bokeh_theme()
    # This is mostly done, so this function can be singleton
    return True
