"""This module contains the Flow usage graph creating functions"""
from __future__ import annotations

# Standard Imports
from typing import TYPE_CHECKING, Hashable, cast, Protocol

# Third-Party Imports
import holoviews as hv

# Perun Imports
from perun.profile import convert
from perun.utils.common import view_kit

if TYPE_CHECKING:
    import pandas as pd

    from perun.profile.factory import Profile


class IntTableLike(Protocol):
    def get(self, key: int, default: int) -> int:
        """"""


def create_from_params(
    profile: Profile,
    func: str,
    of_key: str,
    through_key: str,
    by_key: str,
    stacked: bool,
    accumulate: bool,
    x_axis_label: str,
    y_axis_label: str,
    graph_title: str,
) -> hv.Overlay:
    """Creates Flow graph according to the given parameters.

    The data are grouped according to the 'by_key' and then grouped again for each 'through' key.
    For this, atomic groups aggregation function is used.

    :param profile: a Perun profile.
    :param func: function that will be used for data aggregation.
    :param of_key: the data column (Y-axis) key.
    :param through_key: the X-axis values column key.
    :param by_key: the group-by column bey.
    :param stacked: specifies whether the flow graph should be in stacked format or not.
    :param accumulate: specifies whether the previous X values should be accumulated.
    :param x_axis_label: X-axis label text.
    :param y_axis_label: Y-axis label text
    :param graph_title: title of the graph.
    :returns: a constructed Overlay object containing the individual Area plots.
    """
    view_kit.lazy_init_holoviews()

    # Convert profile to pandas data grid
    data_frame = convert.resources_to_pandas_dataframe(profile)
    data_source = construct_data_source_from(
        data_frame, func, of_key, by_key, through_key, accumulate
    )

    # Obtain colours, which will be sorted in reverse
    key_colours = view_kit.get_unique_colours_for_(
        data_frame, by_key, sort_color_style=view_kit.ColourSort.REVERSE
    )

    # Construct the Area objects and combine them into an overlay
    flow_graph = hv.Overlay(
        [hv.Area(y_values, label=source_name) for source_name, y_values in data_source.items()]
    )
    # For stacked flow graph, we need to stack the individual Area objects from the overlay
    if stacked:
        flow_graph = hv.Area.stack(flow_graph)
    # Configuration options for the individual Area objects
    flow_graph.opts(hv.opts.Area(color=hv.Cycle(key_colours), fill_alpha=1 if stacked else 0.7))
    # Configuration options for the entire plot
    flow_graph.opts(
        title=graph_title,
        tools=["zoom_in", "zoom_out"],
        responsive=True,
        xlabel=x_axis_label,
        ylabel=view_kit.add_y_units(profile["header"], of_key, y_axis_label),
        legend_position="top_left",
    )
    return flow_graph


def construct_data_source_from(
    data_frame: pd.DataFrame,
    func: str,
    of_key: str,
    by_key: str,
    through_key: str,
    accumulate: bool,
) -> dict[Hashable, list[int]]:
    """Transforms the data frame using the aggregating functions, breaking it into groups.

    Takes the original data frame, groups it by the 'by_key' and then for each group, groups values
    again by the 'through_key', which are further aggregated by func and optionally accumulated.

    :param data_frame: source data for the aggregated data frame.
    :param func: the aggregation function's name.
    :param of_key: the data column (Y-axis) key.
    :param through_key: the X-axis values column key.
    :param by_key: the group-by column bey.
    :param accumulate: specifies whether the previous X values should be accumulated.
    :returns: the transformed source data.
    """
    # Compute extremes for X axis
    #  -> this is needed for offsetting of the values for the area chart
    minimal_x_value: int = data_frame[through_key].min()
    maximal_x_value: int = data_frame[through_key].max()

    # Construct the data source: first we group the values by 'by_key' (one graph per each key).
    #   And then we compute the aggregations of the data grouped again, but by through key
    #   (i.e. for each value on X axis), the values are either accumulated or not
    data_source: dict[Hashable, list[int]] = {}
    for group_name, by_key_group_data_frame in data_frame.groupby(by_key):
        data_source[group_name] = [0] * (maximal_x_value + 1)
        source_data_frame = group_and_aggregate(by_key_group_data_frame, through_key, func)
        if accumulate:
            accumulated_value = 0
            for index in range(minimal_x_value, maximal_x_value):
                # FIXME: This should be handled better, since, we simply assume it is [int, int]
                accumulated_value += cast(IntTableLike, source_data_frame[of_key]).get(
                    index + minimal_x_value, 0
                )
                data_source[group_name][index] = accumulated_value
        else:
            # FIXME: This should be handled better, since, we simply assume it is [int, int]
            for through_key_value, of_key_value in cast(
                list[tuple[int, int]], source_data_frame[of_key].items()
            ):
                data_source[group_name][through_key_value - minimal_x_value] = of_key_value
    return data_source


def group_and_aggregate(data: pd.DataFrame, group_through_key: str, func: str) -> pd.DataFrame:
    """Groups the data by group_through_key and then aggregates it through the 'func'.

    :param data: partially grouped data.
    :param group_through_key: key by which to further aggregate.
    :param func: name of the aggregation function to use.
    :returns: the grouped and aggregated data.
    """
    # Aggregate the data according to the func grouped by through_key
    through_data_group = data.groupby(group_through_key)
    # Note that at this point, we should be protected that the function is valid of the data group
    aggregation_function = getattr(through_data_group, func)
    return aggregation_function()
