"""A simple clusterization technique, that considers a broader range of values according to the
sliding window.

The size of the window can be augmented with type (relative vs absolute), or by its size (width
and height).
"""
from __future__ import annotations

from typing import Any

import perun.utils.log as log


def compute_window_width(window_width: float, width_measure: str, resource_number: int) -> float:
    """Computes the sliding window width for the next cluster

    The computation of the new width of the cluster is dependent on the used measure,
    which can be either relative, absolute or weighted. The absolute size of the window
    takes always the same number of similar values; the relative size takes the number
    relative (i.e. the percentage) to the size of the resources; while weighted takes
    the number of resources w.r.t frequency of their values (i.e. the more common amounts
    are clustered in more fine way).

    :param float window_width: the rate of the window width, dependent on width_measure,
        either percents or absolute number
    :param str width_measure: type of the width measure (absolute, relative or weighted)
    :param int resource_number: number of resources
    :return: computed width for new sliding window
    """
    if width_measure == "absolute":
        return window_width
    else:
        # assert width_measure == 'relative':
        return resource_number * window_width


def compute_window_height(resource_amount: int, window_height: int, height_measure: str) -> int:
    """Computes the sliding window height for the next cluster

    The computation of the new height of the cluster is dependent on the used measure,
    which can be either relative or absolute. The absolute height takes the amount of
    the resource and adds absolute size of the window for each member. The relative size
    computes the height as the percentage of the resource amount.

    :param int resource_amount: resource for which we are computing the height
    :param int window_height: height of the sliding window
    :param str height_measure: type of the height measure (absolute or relative)
    :return: computed height for new sliding window
    """
    if height_measure == "absolute":
        return window_height + resource_amount
    else:
        # assert height_measure == 'relative'
        return resource_amount * (1 + window_height)


def clusterize(
    sorted_resources: list[dict[str, Any]],
    window_width: float,
    width_measure: str,
    window_height: int,
    height_measure: str,
    **_: Any,
) -> None:
    """Clusterize the list of sorted resources w.r.t sliding window

    Iterates through sorted resources, and classifies each of the resource to appropriate cluster
    according to the sliding window. Each time, we fell out of the window, we recompute the sizes
    (width and height) of the window and increment the cluster

    :param list sorted_resources: list of sorted resource
    :param float window_width: the rate of the window width, dependent on width_measure,
        either percents or absolute number
    :param str width_measure: type of the width measure (absolute, relative or weighted)
    :param int window_height: height of the sliding window
    :param str height_measure: type of the height measure (absolute or relative)
    :param _: rest of the keyword arguments, not used in the function
    """
    if width_measure not in ("absolute", "relative"):
        log.error("'{}' is not supported window width measure".format(width_measure))
    if height_measure not in ("absolute", "relative"):
        log.error("'{}' is not supported window width measure".format(height_measure))

    # Initialize the cluster and width
    resource_number = len(sorted_resources)
    current_cluster = 1
    resource_width = 0

    # Initialize the width and height of the window w.r.t params and first resource
    current_width = compute_window_width(window_width, width_measure, resource_number)
    current_height = compute_window_height(
        sorted_resources[0]["amount"], window_height, height_measure
    )
    log.info("clustering with window of ({}, {})".format(current_width, current_height))

    # Iterate through all of the resources
    for resource in sorted_resources:
        resource_height = resource["amount"]
        # If we are out of the window, we recompute the width and height and move to next cluster
        if resource_width >= current_width or resource_height > current_height:
            current_width = compute_window_width(window_width, width_measure, resource_number)
            current_height = compute_window_height(resource_height, window_height, height_measure)
            current_cluster += 1
            resource_width = 0
            log.info("creating new cluster of ({}, {})".format(current_width, current_height))

        # Update the cluster of the resource
        resource_width += 1
        resource["cluster"] = current_cluster
