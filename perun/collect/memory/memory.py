"""Time module contains methods needed by Perun logic"""
import json
import subprocess
from decimal import Decimal
import perun.collect.memory.parsing as parser

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
        tuple: (return code, message, updated kwargs)
    """
    result = run(cmd, params, workload)
    if result:
        error_msg = 'Execution of binary failed with error code: '
        error_msg += str(result)
        return 1, error_msg, {}

    return 0, '', {}


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
    try:
        profile = parser.parse_log('MemoryLog', cmd, Decimal('0.001'))
    except IndexError:
        return 1, 'Wrong format of log file', {}
    except ValueError:
        return 1, 'Wrong format of log file', {}

    return 0, '', {'profile': profile}


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
