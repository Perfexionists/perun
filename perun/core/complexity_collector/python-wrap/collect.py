""" Standardized 'collect.py' module to run the specific complexity collector.

"""


import os
import subprocess


def collect(collector_exec_path):
    """ Runs the collector executable

    Arguments:
        collector_exec_path(str): path to the collector executable

    Returns:
        int: return code of the collector executable
    """
    collector_dir, collector_exec = _get_collector_executable_and_dir(collector_exec_path)
    return subprocess.call(('./' + collector_exec), cwd=collector_dir)


def _get_collector_executable_and_dir(collector_exec_path):
    """ Extracts the collector executable name and location directory

    Arguments:
        collector_exec_path(str): path to the collector executable

    Returns:
        tuple: the collector directory path
               the collector executable name
    """
    collector_exec_path = os.path.realpath(collector_exec_path)
    delim = collector_exec_path.rfind('/')
    if delim != -1:
        collector_dir = collector_exec_path[:delim + 1]
        collector_exec = collector_exec_path[delim+1:]
    else:
        collector_dir = ''
        collector_exec = collector_exec_path
    return collector_dir, collector_exec
