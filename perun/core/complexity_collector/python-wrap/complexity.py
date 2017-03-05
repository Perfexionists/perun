""" Standardized complexity collector module with before, collect and after functions to perform
    the initialization, collection and postprocessing of collection data

"""


import os
import subprocess


import makefiles
import symbols
import configurator


# Test configuration dictionary
config = {
    'target_dir': './target',
    'files': [
        '../../main.cpp',
        '../../SLList.h',
        '../../SLListcls.h'
    ],
    'rules': [
        'func1',
        'SLList_init',
        'SLList_insert',
        'SLList_search',
        'SLList_destroy'
    ],
    'file-name': 'trace.log',
    'init-storage-size': 20000,
    'sampling': [
        {'func': 'SLList_insert', 'sample': 2},
        {'func': 'func1', 'sample': 1},
    ],
    'recursion': 'no'
}


def before(**kwargs):
    """ Builds, links and configures the complexity collector executable

    Arguments:
        kwargs(dict): dictionary containing the configuration settings for the complexity collector
    """
    # Create the configuration cmake and build the configuration executable
    cmake_path = makefiles.create_config_cmake(kwargs['target_dir'], kwargs['files'])
    exec_path = makefiles.build_executable(cmake_path, makefiles.CMAKE_CONFIG_TARGET)
    # Extract some configuration data using the configuration executable
    function_sym = symbols.extract_symbols(exec_path)
    include_list, exclude_list, runtime_filter = symbols.filter_symbols(function_sym, kwargs['rules'])
    # Create the collector cmake and build the collector executable
    cmake_path = makefiles.create_collector_cmake(kwargs['target_dir'], kwargs['files'], exclude_list)
    exec_path = makefiles.build_executable(cmake_path, makefiles.CMAKE_COLLECT_TARGET)
    # Create the internal configuration file
    configurator.create_ccicc(exec_path, runtime_filter, include_list, kwargs)

    kwargs['bin'] = exec_path
    return


def collect(**kwargs):
    """ Runs the collector executable

    Arguments:
        kwargs(dict): dictionary containing the configuration settings for the complexity collector

    Returns:
        int: return code of the collector executable
    """
    collector_dir, collector_exec = _get_collector_executable_and_dir(kwargs['bin'])
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
