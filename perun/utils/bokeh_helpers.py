"""Collection of helper functions for working with bokeh graphs"""

import bokeh.palettes as palettes

import perun.utils.log as log

__author__ = 'Tomas Fiedor'

GRAPH_LR_PADDING = 50
GRAPH_TB_PADDING = 100


def get_unique_colours_for_(data_source, key):
    """
    Arguments:
        graph(graph): bokeh graf that will have assigned unique colours
    """
    unique_keys = data_source[key].unique()
    unique_keys_num = len(unique_keys)

    if unique_keys_num > 256:
        log.error("plotting to Bokeh backend currently supports only 256 colours")

    # This is temporary workaround for non-sorted legends
    keys_to_colour = list(zip(unique_keys, palettes.viridis(unique_keys_num)))
    keys_to_colour.sort()

    return list(map(lambda x: x[1], keys_to_colour))
