"""This module contains the BAR graphs creating functions"""
from __future__ import annotations

# Standard Imports
from typing import TYPE_CHECKING

# Third-Party Imports
import holoviews as hv

# Perun Imports
from perun.profile import convert
from perun.utils.common import view_kit

if TYPE_CHECKING:
    from perun.profile.factory import Profile


def create_from_params(
    profile: Profile,
    func: str,
    of_key: str,
    per_key: str,
    by_key: str,
    grouping_type: str,
    x_axis_label: str,
    y_axis_label: str,
    graph_title: str,
) -> hv.Bars:
    """Creates Bar graph according to the given parameters.

    The 'of_key' is a data column (Y-axis) that is further aggregated by the 'func' depending on
    the values of 'per_key' (X-axis). Values are further grouped by the 'by_key' column and
    visualised according to the 'grouping_type'.

    :param profile: a Perun profile.
    :param func: function that will be used for data aggregation.
    :param of_key: the data column (Y-axis) key.
    :param per_key: the X-axis values column key.
    :param by_key: the group-by column bey.
    :param grouping_type: determines if the bars are stacked or grouped w.r.t. the 'by_key'.
    :param x_axis_label: X-axis label text.
    :param y_axis_label: Y-axis label text
    :param graph_title: title of the graph.
    :returns: a constructed and configured Bar graph object.
    """
    view_kit.lazy_init_holoviews()

    # Convert profile to pandas data grid
    data_frame = convert.resources_to_pandas_dataframe(profile)
    data_frame.sort_values([per_key, by_key], inplace=True)

    # Holoviews improperly implements pandas aggregation for non-numeric dims. Their aggregation
    # accepts only np.size as an aggregation function for non-numeric columns. Let's do the data
    # preparation ourselves and let the users handle potential warnings when they select columns
    # and aggregation function combination that is invalid.
    grouped = data_frame[[per_key, by_key, of_key]].groupby([per_key, by_key], sort=False)
    data_frame = grouped[[of_key]].aggregate(func=func).reset_index()
    # Build the bar graph: X axis is multi-key, where the by_key is used in grouping/stacking
    bars = hv.Bars(data_frame, kdims=[per_key, by_key], vdims=[of_key])

    # Configure the plot's visual properties
    bars.opts(
        title=graph_title,
        xlabel=x_axis_label,
        ylabel=view_kit.add_y_units(profile["header"], of_key, y_axis_label),
        tools=["zoom_in", "zoom_out", "hover"],
        responsive=True,
        bar_width=1.0,
        color=hv.Cycle(view_kit.get_unique_colours_for_(data_frame, by_key)),
        stacked=grouping_type == "stacked",
        multi_level=False,
    )
    return bars
