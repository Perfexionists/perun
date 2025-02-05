"""The extraction and storage methods for the Dynamic Stats resource."""

import perun.logic.stats as stats
import perun.logic.temp as temp
import perun.collect.trace.optimizations.dynamic_stats as dyn_stats
from perun.utils.exceptions import StatsFileNotFoundException, SuppressedExceptions


def extract(stats_name, reset_cache, **_):
    """Load the DynamicStats cache (in file) from the last profiled version.

    :param stats_name: name of the Dynamic Stats file
    :param reset_cache: determines whether the Dynamic Stats should be recreated or not

    :return: the Dynamic Stats object
    """
    dynamic_stats = dyn_stats.DynamicStats()
    if not reset_cache:
        # Obtain the dynamic baseline statistics from cache, if any
        cached_stats = stats.get_latest(stats_name, ["dynamic-stats"]).get("dynamic-stats", {})
        if cached_stats:
            dynamic_stats = dyn_stats.DynamicStats.from_dict(cached_stats)
    return dynamic_stats


def store(stats_name, dynamic_stats, no_update, **_):
    """Store the supplied DynamicStats resource object

    :param stats_name: name of the stats file
    :param dynamic_stats: the DynamicStats content
    :param no_update: disables dynamic stats updates
    """
    if no_update:
        # Do not save the file again if it already exists
        with SuppressedExceptions(StatsFileNotFoundException):
            stats.get_stats_file_path(stats_name, check_existence=True)
            return
    dict_stats = dynamic_stats.to_dict()
    stats.add_stats(stats_name, ["dynamic-stats"], [dict_stats])
    # Temporary storage for debugging
    temp.store_temp("optimization/dynamic-stats.json", dict_stats, json_format=True)
