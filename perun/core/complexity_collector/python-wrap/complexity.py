""" Standardized complexity collector module with before, collect and after functions to perform
    the initialization, collection and postprocessing of collection data

"""


import os
import subprocess
import collections

import makefiles
import symbols
import configurator
import complexity_exceptions


profile_record = collections.namedtuple('record', ['action', 'func', 'timestamp'])


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
    'file-name': '../trace.log',
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

    Returns:
        dict: modified kwargs with bin value representing the executable
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
    return dict(kwargs)


def collect(**kwargs):
    """ Runs the collector executable

    Arguments:
        kwargs(dict): dictionary containing the configuration settings for the complexity collector

    Returns:
        int: return code of the collector executable
    """
    collector_dir, collector_exec = _get_collector_executable_and_dir(kwargs['bin'])
    return subprocess.call(('./' + collector_exec), cwd=collector_dir)


def after(**kwargs):
    """ Handles the complexity collector post processing

    Arguments:
        kwargs(dict): dictionary containing the configuration settings for the complexity collector

    Returns:
        dict: kwargs with resources value
    """
    # Get the trace log path
    pos = kwargs['bin'].rfind('/')
    path = kwargs['bin'][:pos + 1] + kwargs['file-name']
    address_map = symbols.extract_symbol_address_map(kwargs['bin'])

    resources = []
    call_stack = []
    with open(path, 'r') as profile:
        for line in profile:
            # Split the line into action, function name and timestamp
            record = profile_record(*line.split())
            if record.action == 'i':
                call_stack.append(record)
            elif call_stack[-1].action == 'i' and call_stack[-1].func == record.func:
                # Function exit, match with the function enter to create resources record
                matching_record = call_stack.pop()
                resources.append({'amount': int(record.timestamp) - int(matching_record.timestamp),
                                  'uid': address_map[record.func],
                                  'type': 'complexity',
                                  'subtype': 'todo',
                                  'structure-unit-size': 'todo'})
            else:
                raise complexity_exceptions.TraceLogCallStackError('Current:' + record.func + ', call stack top: ' +
                                                                   call_stack[-1].func)
    kwargs['resources'] = resources
    return kwargs


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

