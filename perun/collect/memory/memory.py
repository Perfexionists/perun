"""This module contains methods needed by Perun logic"""
import json
import subprocess
from decimal import Decimal
import perun.collect.memory.filter as filter
import perun.collect.memory.parsing as parser
from perun.utils.helpers import CollectStatus

__author__ = 'Radim Podola'


def run(cmd, args, workload):
    """
    Arguments:
        cmd(string): binary file to profile
        args(string): executing arguments
        workload(string): file that has to be provided to binary

    Returns:
        int: return code of executed binary
    """
    sys_call = ('LD_PRELOAD="$PWD/malloc.so" ' + cmd +
                ' ' + args + ' ' + workload)

    return subprocess.call(sys_call, shell=True)


def collect(cmd, params, workload, **kwargs):
    """ Phase for collection of the profile data
    Arguments:
        cmd(string): binary file to profile
        params(string): executing arguments
        workload(string): file that has to be provided to binary
        kwargs(dict): profile's header

    Returns:
        tuple: (return code, status message, updated kwargs)
    """
    result = run(cmd, params, workload)
    if result:
        error_msg = 'Execution of binary failed with error code: '
        error_msg += str(result)
        return CollectStatus.ERROR, error_msg, {}

    return CollectStatus.OK, '', {}


def after(collect_params, cmd, **kwargs):
    """ Phase after the collection for minor postprocessing
        that needs to be done after collect
    Arguments:
        collect_params(string): execution parameters of collector
        cmd(string): binary file to profile
        kwargs(dict): profile's header

    Returns:
        tuple: (return code, message, updated kwargs)
    """
    # TODO parsing collect_params
    try:
        profile = parser.parse_log('MemoryLog', cmd, Decimal('0.001'))
    except IndexError:
        return CollectStatus.ERROR, 'Info missing in log file', {}
    except ValueError:
        return CollectStatus.ERROR, 'Wrong format of log file', {}

    # filter.remove_allocators(profile)
    # filter.function_filter(profile, 'main')
    filter.trace_filter(profile, source='unreachable')

    return CollectStatus.OK, '', {'profile': profile}


if __name__ == "__main__":
    pass


header = {'type': 'memory',
          'cmd': './test',
          'params': '-a 5',
          'workload': '',
          'units': {'memory': 'MB'}
         }

print(collect(**header))
r = after('-s 0.001', **header)
print(r[0], r[1], json.dumps(r[2], indent=2))
