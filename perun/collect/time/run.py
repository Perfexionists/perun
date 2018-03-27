"""Time module is a simple wrapper over command line tool time"""

import click

import perun.logic.runner as runner
import perun.utils as utils
from perun.utils.helpers import CollectStatus

__author__ = 'Tomas Fiedor'

TIME_TYPES = ('real', 'user', 'sys')


def collect(**kwargs):
    """Phase for collection of the profile data"""
    command = " ".join([
        'time -p', kwargs['cmd'], kwargs.get('args', ''), kwargs['workload']
    ]).split(' ')
    collected_data = utils.get_stdout_from_external_command(command).split('\n')

    times = {
        t[0]: t[1] for t in map(lambda x: x.split(' '), collected_data)
        if len(t) == 2 and t[0] in TIME_TYPES
    }

    return CollectStatus.OK, "", {'profile': {
        "global": {
            "timestamp": max(times.values()),
            "resources": [
                {"amount": float(timing), "uid": key} for (key, timing) in times.items()
            ]
        }
    }}


@click.command()
@click.pass_context
def time(ctx):
    """Generates `time` performance profile, capturing overall running times of
    the profiled command.

    \b
      * **Limitations**: `none`
      * **Metric**: running `time`
      * **Dependencies**: `none`
      * **Default units**: `s`

    This is a wrapper over the ``time`` linux unitility and captures resources
    in the following form:

    .. code-block:: json

        \b
        {
            "amount": 0.59,
            "type": "time",
            "uid": "sys"
        }

    Refer to :ref:`collectors-time` for more thorough description and examples
    of `complexity` collector.
    """
    runner.run_collector_from_cli_context(ctx, 'time', {})
