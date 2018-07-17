"""A wrapper of the classical time linux utility.

Time collects the runtime of given commands with repetition of the measurements. First we do a
several warm-up executions, followed by the actual timing.
"""

import sys
import click
import time as systime

import perun.logic.runner as runner
import perun.utils as utils
from perun.utils.helpers import CollectStatus

__author__ = 'Tomas Fiedor'

TIME_TYPES = ('real', 'user', 'sys')


def collect(repeat=10, warmup=3, **kwargs):
    """Times the runtime of the given command, with stated repeats.

    :param dict kwargs: dictionary with key, value options
    :param int repeat: number of repeats of the the timing, by default 10
    :return:
    """
    print('Executing the warmup-phase ', end='')
    for timing in range(0, warmup):
        command = " ".join([
            'time -p', kwargs['cmd'], kwargs.get('args', ''), kwargs['workload']
        ]).split(' ')
        utils.get_stdout_from_external_command(command).split('\n')
        print('.', end='')
        sys.stdout.flush()
    print("")

    print('Begin timing of {} {} time{} '.format(
        kwargs.get('cmd'), repeat, "s" if repeat != 1 else ""
    ), end='')
    times = []

    before_timing = systime.time()
    for timing in range(1, repeat + 1):
        command = " ".join([
            'time -p', kwargs['cmd'], kwargs.get('args', ''), kwargs['workload']
        ]).split(' ')
        collected_data = utils.get_stdout_from_external_command(command).split('\n')

        times.extend([
            (timing, t[0], t[1]) for t in map(lambda x: x.split(' '), collected_data)
            if len(t) == 2 and t[0] in TIME_TYPES
        ])
        print('.', end='')
        sys.stdout.flush()
    print("")
    overall_time = systime.time() - before_timing

    return CollectStatus.OK, "", {'profile': {
        "global": {
            "timestamp": overall_time,
            "resources": [
                {
                    "amount": float(timing),
                    "uid": kwargs['cmd'],
                    "order": order,
                    "subtype": key,
                    "type": "time",
                    "workload": kwargs['workload']
                } for (order, key, timing) in times
            ]
        }
    }}


@click.command()
@click.option('--warm-up-repetition', '-w', 'warmup',
              default=3, nargs=1, type=click.INT, metavar='<int>',
              help='Before the actual timing, the collector will execute <int> warm-up executions.')
@click.option('--repeat', '-r',
              default=10, nargs=1, type=click.INT, metavar='<int>',
              help='The timing of the given binaries will be repeated <int> times.')
@click.pass_context
def time(ctx, **kwargs):
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
            "subtype": "sys",
            "uid": cmd
            "order": 1
        }

    Refer to :ref:`collectors-time` for more thorough description and examples
    of `complexity` collector.
    """
    runner.run_collector_from_cli_context(ctx, 'time', kwargs)
