""" Standardized complexity collector module with before, collect and after functions to perform
    the initialization, collection and postprocessing of collection data

"""


import os
import subprocess
import collections

import makefiles
import symbols
import configurator
import perun.utils.exceptions as exceptions


# Test configuration dictionary
config = {
    'target_dir': './target',
    'files': [
        '../cpp_sources/test_workload/main.cpp',
        '../cpp_sources/test_workload/SLList.h',
        '../cpp_sources/test_workload/SLListcls.h'
    ],
    'rules': [
        'func1',
        'SLList_init',
        'SLList_insert',
        'SLList_search',
        'SLList_destroy',
        'SLListcls',
        '~Sllistcls',
        'Insert',
        'Remove',
        'Search'
    ],
    'file-name': 'trace.log',
    'init-storage-size': 20000,
    'sampling': [
        {'func': 'SLList_insert', 'sample': 1},
        {'func': 'func1', 'sample': 1},
    ],
    'recursion': 'no'
}


# The profiling record template
_ProfileRecord = collections.namedtuple('record', ['action', 'func', 'timestamp', 'size'])

# The collect phase status messages
_collector_status_msg = {
    0:  'OK',
    1:  'Err: profile output file cannot be opened.',
    2:  'Err: profile output file closed unexpectedly.',
    11: 'Err: runtime configuration file does not exists.',
    12: 'Err: runtime configuration file syntax error.'
}

# The collector subtypes
_collector_subtypes = {
    'delta': 'time delta'
}


def before(**kwargs):
    """ Builds, links and configures the complexity collector executable

    Arguments:
        kwargs(dict): dictionary containing the configuration settings for the complexity collector

    Returns:
        tuple: int as a status code, nonzero values for errors
               string as a status message, mainly for error states
               dict of modified kwargs with bin value representing the executable
    """
    try:
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
        configurator.create_runtime_config(exec_path, runtime_filter, include_list, kwargs)

        kwargs['bin'] = exec_path
        return 0, _collector_status_msg[0], dict(kwargs)
    # The "expected" exception types
    except (OSError, ValueError, subprocess.CalledProcessError,
            UnicodeError, exceptions.UnexpectedPrototypeSyntaxError) as e:
        return 1, repr(e), kwargs


def collect(**kwargs):
    """ Runs the collector executable

    Arguments:
        kwargs(dict): dictionary containing the configuration settings for the complexity collector

    Returns:
        tuple: int as a status code, nonzero values for errors
               string as a status message, mainly for error states
               dict of modified kwargs with bin value representing the executable
    """
    collector_dir, collector_exec = _get_collector_executable_and_dir(kwargs['bin'])
    return_code = subprocess.call(('./' + collector_exec), cwd=collector_dir)
    return return_code, _collector_status_msg[return_code], dict(kwargs)


def after(**kwargs):
    """ Handles the complexity collector post processing

    Arguments:
        kwargs(dict): dictionary containing the configuration settings for the complexity collector

    Returns:
        tuple: int as a status code, nonzero values for errors
               string as a status message, mainly for error states
               dict of modified kwargs with bin value representing the executable
    """
    # Get the trace log path
    pos = kwargs['bin'].rfind('/')
    path = kwargs['bin'][:pos + 1] + kwargs['file-name']
    address_map = symbols.extract_symbol_address_map(kwargs['bin'])

    resources = []
    call_stack = []
    with open(path, 'r') as profile:
        for line in profile:
            # Split the line into action, function name, timestamp and size
            record = _ProfileRecord(*line.split())
            if record.action == 'i':
                call_stack.append(record)
            elif call_stack[-1].action == 'i' and call_stack[-1].func == record.func:
                # Function exit, match with the function enter to create resources record
                matching_record = call_stack.pop()
                resources.append({'amount': int(record.timestamp) - int(matching_record.timestamp),
                                  'uid': address_map[record.func],
                                  'type': 'mixed',
                                  'subtype': _collector_subtypes['delta'],
                                  'structure-unit-size': int(record.size)})
            else:
                # Call stack function frames not matching
                err_msg = 'Call stack error: ' + record.func + ', call stack top: ' + call_stack[-1].func
                return 1, err_msg, kwargs
    kwargs['profile'] = resources
    return 0, _collector_status_msg[0], kwargs


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


# Test run
# code, msg, config = before(**config)
# print('code: {0}, msg: {1}\n'.format(code, msg))
# code, msg, config = collect(**config)
# print('code: {0}, msg: {1}\n'.format(code, msg))
# code, msg, config = after(**config)
# print('code: {0}, msg: {1}\n'.format(code, msg))
