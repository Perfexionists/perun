""" The extraction and storage methods for the Dynamic Stats resource.
"""


import perun.logic.stats as stats


def extract(stats_name, reset_cache, **_):
    """ Load the Dynamic Stats file from the last profiled version.

    :param str stats_name: name of the Dynamic Stats file
    :param bool reset_cache: determines whether the Dynamic Stats should be recreated or not

    :return dict: the Dynamic Stats dictionary
    """
    # Obtain the dynamic baseline statistics from the file
    if reset_cache:
        # We ignore the dynamic stats file
        return {}
    else:
        dyn_stats = stats.get_latest(stats_name, ['dynamic-baseline']).get('dynamic-baseline', {})
        return dyn_stats


def store(stats_name, stats_map, **_):
    """ Store the supplied Dynamic Stats resource object

    :param str stats_name: name of the stats file
    :param dict stats_map: the Dynamic Stats content
    """
    stats.add_stats(stats_name, ['dynamic-baseline'], [stats_map])
