"""A simple clusterization technique, which classifies resources according to sorted values."""

__author__ = 'Tomas Fiedor'

from typing import List, Dict, Any


def clusterize(sorted_resources: List[Dict[str, Any]], **_):
    """Clusterizes the resources according to their sort order

    Simple strategy for clusterizing the values according to the sort order

    :param list sorted_resources: list of sorted resources
    """
    for sort_no, resource in enumerate(sorted_resources):
        resource['cluster'] = sort_no + 1
