""" The Dynamic Stats resource computation
"""


import numpy as np


# The quartiles
_Q1, _Q2, _Q3 = 25, 50, 75


def gather_stats(profile, config):
    """ using the profile and collection configuration, compute the aggregate statistics for the
    Dynamic Stats.

    :param Profile profile: the Perun profile generated during the profiling
    :param Configuration config: the collection configuration object

    :return dict: the Dynamic Stats dictionary
    """
    # Parse the profile in order to gather the measured values
    funcs = config.get_functions()
    func_values = {func_name: [] for func_name in funcs.keys()}

    for record in profile['global']['resources']:
        try:
            func_values[record['uid']].append(record['amount'])
        except KeyError:
            pass

    stats_map = {}
    for name, values in func_values.items():
        # Some functions might not have any values
        if not values:
            continue
        # Sort the 'amount' values in order to compute various statistics
        values.sort()
        percentiles = np.percentile(np.array(values), [_Q1, _Q2, _Q3])
        func_stats = {
            'count': len(values) + ((len(values) - 1) * (funcs[name]['sample'] - 1)),
            'sampled_count': len(values),
            'sample': funcs[name]['sample'],
            'total': sum(values),
            'min': values[0],
            'max': values[-1],
            'avg': sum(values) / len(values),
            'Q1': percentiles[0],
            'median': percentiles[1],
            'Q3': percentiles[2],
        }
        func_stats['IQR'] = func_stats['Q3'] - func_stats['Q1']
        stats_map[name] = func_stats

    return stats_map
