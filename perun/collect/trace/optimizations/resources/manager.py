"""The dispatcher for various resource extraction and storage functions.

Specifically, each resource should implement an 'extract' / 'storage' function so that the
interface is unified.
"""

from enum import Enum

from perun.collect.trace.optimizations.resources import angr_provider
import perun.collect.trace.optimizations.resources.perun_call_graph as perun_cg
import perun.collect.trace.optimizations.resources.perun_dynamic_stats as perun_stats


class Resources(Enum):
    """An enumeration for all currently used optimization resources and their corresponding
    extraction / storage methods, if any.
    """

    CALL_GRAPH_ANGR = (angr_provider.extract,)
    PERUN_CALL_GRAPH = perun_cg.extract, perun_cg.store
    PERUN_STATS = perun_stats.extract, perun_stats.store


def extract(resource, **kwargs):
    """Extract the selected resource.

    :param resource: the requested optimization resource
    :param kwargs: additional extraction parameters

    :return: the extracted resource object
    """
    provider_method = resource.value[0]
    resource = provider_method(**kwargs)
    return resource


def store(resource, **kwargs):
    """Store the selected resource.

    :param resource: the stored optimization resource
    :param kwargs: additional parameters for the specific methods
    """
    store_method = resource.value[1]
    store_method(**kwargs)
