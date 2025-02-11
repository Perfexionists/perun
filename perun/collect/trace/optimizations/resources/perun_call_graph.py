"""The extraction and storage methods for the internal Perun call graph format. While
angr call graph provider extracts the call graph from a binary file or the current project version,
the Perun call graph provider handles storage of the internal call graph format in the 'stats'
and loading call graphs from previous project versions.
"""

import perun.logic.temp as temp
import perun.logic.stats as stats
from perun.utils.exceptions import StatsFileNotFoundException, SuppressedExceptions


def extract(stats_name, exclude_self, vcs_version, **_):
    """Load the call graph of latest previous version that has the file stored in 'stats'.

    :param stats_name: name of the call graph file
    :param exclude_self: specifies whether to also search in the current version directory
    :param vcs_version: specifies minor_version to search in

    :return: the internal Perun call graph format
    """
    if vcs_version is None:
        # Search for the closest stats if no version is specified
        return stats.get_latest(stats_name, ["perun_cg"], exclude_self=exclude_self).get(
            "perun_cg", {}
        )

    return stats.get_stats_of(stats_name, minor_version=vcs_version).get("perun_cg", {})


def store(stats_name, call_graph, cache, **_):
    """Store the internal call graph structure into the 'stats' directory

    :param stats_name: name of the stats file
    :param call_graph: the internal call graph format
    :param cache: sets the cache on / off configuration
    """
    if cache:
        # Do not save the file again if it already exists
        with SuppressedExceptions(StatsFileNotFoundException):
            stats.get_stats_file_path(stats_name, check_existence=True)
            return

    serialized = {
        "call_graph": {
            "cg_map": call_graph.cg_map,
            "recursive": list(call_graph.recursive),
        },
        "control_flow": call_graph.cfg,
        "minor_version": call_graph.minor,
    }
    stats.add_stats(stats_name, ["perun_cg"], [serialized])
    temp.store_temp(f"optimization/{stats_name}.json", serialized, json_format=True)
