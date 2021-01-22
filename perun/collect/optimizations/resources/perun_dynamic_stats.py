""" The extraction and storage methods for the Dynamic Stats resource.
"""


import perun.logic.stats as stats
import perun.logic.temp as temp
import perun.collect.optimizations.dynamic_stats as dyn_stats


def extract(stats_name, reset_cache, **_):
    """ Load the DynamicStats cache (in file) from the last profiled version.

    :param str stats_name: name of the Dynamic Stats file
    :param bool reset_cache: determines whether the Dynamic Stats should be recreated or not

    :return DynamicStats: the Dynamic Stats object
    """
    dynamic_stats = dyn_stats.DynamicStats()
    if not reset_cache:
        # Obtain the dynamic baseline statistics from cache, if any
        cached_stats = stats.get_latest(stats_name, ['dynamic-stats']).get('dynamic-stats', {})
        if cached_stats:
            dynamic_stats = dyn_stats.DynamicStats.from_dict(cached_stats)
    return dynamic_stats


def store(stats_name, dynamic_stats, **_):
    """ Store the supplied DynamicStats resource object

    :param str stats_name: name of the stats file
    :param DynamicStats dynamic_stats: the DynamicStats content
    """
    dict_stats = dynamic_stats.to_dict()
    stats.add_stats(stats_name, ['dynamic-stats'], [dict_stats])
    # Temporary storage for debugging
    temp.store_temp('optimization/dynamic-stats.json', dict_stats, json_format=True)