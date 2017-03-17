"""Time module is a simple wrapper over command line tool time"""

import perun.utils as utils

from perun.utils.helpers import CollectStatus

__author__ = 'Tomas Fiedor'


def collect(**kwargs):
    """Phase for collection of the profile data"""
    assert {'bin', 'workload'}.issubset(kwargs.keys())

    command = " ".join([
        'time -p', kwargs['bin'], kwargs.get('args', ''), kwargs['workload']
    ]).split(' ')
    collected_data = utils.get_stdout_from_external_command(command).split('\n')

    times = {
        t[0]: t[1] for t in map(lambda x: x.split(' '), collected_data) if len(t) == 2
    }

    return CollectStatus.OK, "", {'profile': {
        "global": {
            "timestamp": max(times.values()),
            "resources": [
                {"amount": float(timing), "uid": key} for (key, timing) in times.items()
            ]
        }
    }}


if __name__ == "__main__":
    pass
