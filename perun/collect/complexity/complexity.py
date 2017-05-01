""" Standardized complexity collector module with before, collect and after functions to perform
    the initialization, collection and postprocessing of collection data

"""


import os
import sys
import subprocess
import collections

import makefiles
import symbols
import configurator
import exceptions
import data_provider
import analysis
from regression_analysis.regression_models import Models

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

# The time conversion constant
_MICRO_TO_SECONDS = 1000000.0


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
        print('Building the configuration executable...')
        cmake_path = makefiles.create_config_cmake(kwargs['target_dir'], kwargs['files'])
        exec_path = makefiles.build_executable(cmake_path, makefiles.CMAKE_CONFIG_TARGET)
        print('Build complete.')
        # Extract some configuration data using the configuration executable
        print('Extracting the configuration...')
        function_sym = symbols.extract_symbols(exec_path)
        include_list, exclude_list, runtime_filter = symbols.filter_symbols(function_sym, kwargs['rules'])
        # Create the collector cmake and build the collector executable
        print('Building the collector executable...')
        cmake_path = makefiles.create_collector_cmake(kwargs['target_dir'], kwargs['files'], exclude_list)
        exec_path = makefiles.build_executable(cmake_path, makefiles.CMAKE_COLLECT_TARGET)
        print('Build complete.\n')
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
    print('Running the collector...')
    collector_dir, collector_exec = _get_collector_executable_and_dir(kwargs['bin'])
    return_code = subprocess.call(('./' + collector_exec), cwd=collector_dir)
    print('Done.\n')
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
    print('Starting the post-processing phase...')
    pos = kwargs['bin'].rfind('/')
    path = kwargs['bin'][:pos + 1] + kwargs['file-name']
    address_map = symbols.extract_symbol_address_map(kwargs['bin'])

    resources, call_stack = [], []
    profile_start, profile_end = 0, 0

    with open(path, 'r') as profile:

        is_first_line = True
        for line in profile:
            # Split the line into action, function name, timestamp and size
            record = _ProfileRecord(*line.split())

            # Process the record
            if _process_file_record(record, call_stack, resources, address_map) != 0:
                # Stack error
                err_msg = 'Call stack error, record: ' + record.func + ', ' + record.action
                if not call_stack:
                    err_msg += ', stack top: empty'
                else:
                    err_msg += ', stack top: ' + call_stack[-1].func + ', ' + call_stack[-1].action
                return 1, err_msg, kwargs

            # Get the first and last record timestamps to determine the profiling time
            profile_end = record.timestamp
            if is_first_line:
                is_first_line = False
                profile_start = record.timestamp

    # Update the profile dictionary
    kwargs['profile'] = {
        'global': {
            'time': str((int(profile_end) - int(profile_start)) / _MICRO_TO_SECONDS) + 's',
            'resources': resources
        }
    }
    print('Done.\n')
    return 0, _collector_status_msg[0], dict(kwargs)


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


def _process_file_record(record, call_stack, resources, address_map):
    """ Processes the next profile record and tries to pair it with stack record if possible

    Arguments:
        record(namedtuple): the _ProfileRecord tuple containing the record data
        call_stack(list): the call stack with file records
        resources(list): the list of resource dictionaries
        address_map(dict): the function address: demangled name map

    Returns:
        int: the status code, nonzero values for errors
    """
    if record.action == 'i':
        call_stack.append(record)
        return 0
    elif call_stack and call_stack[-1].action == 'i' and call_stack[-1].func == record.func:
        # Function exit, match with the function enter to create resources record
        matching_record = call_stack.pop()
        resources.append({'amount': int(record.timestamp) - int(matching_record.timestamp),
                          'uid': address_map[record.func],
                          'type': 'mixed',
                          'subtype': _collector_subtypes['delta'],
                          'structure-unit-size': int(record.size)})
        return 0
    else:
        # Call stack function frames not matching
        return 1


# Prepare the paths for test run to work correctly for everyone
# Suppose there is no perun directory above the project one
# Test config

_dir_name = os.path.dirname(os.path.abspath(__file__))
_base_pos = _dir_name.find('/complexity')
if _base_pos == -1:
    print("Module not located in complexity directory, cannot do the test run!", file=sys.stderr)
else:
    _complexity_dir = _dir_name[:_base_pos] + '/complexity/'

    # Test configuration dictionary
    _config = {
        'target_dir': _complexity_dir + 'target',
        'files': [
            _complexity_dir + 'cpp_sources/test_workload/main.cpp',
            _complexity_dir + 'cpp_sources/test_workload/SLList.h',
            _complexity_dir + 'cpp_sources/test_workload/SLListcls.h',
            _complexity_dir + 'cpp_sources/test_workload/skiplist.cpp',
            _complexity_dir + 'cpp_sources/test_workload/skiplist.h'
        ],
        'rules': [
            # 'Insert',
            'Search',
            'insert_sort',
            'skiplistInsert',
            'skiplistSearch',
            'QuickSort',
            # 'SLList_insert',
            'SLList_search'
        ],
        'file-name': 'trace.log',
        'init-storage-size': 20000,
        'sampling': [
            {'func': 'Search', 'sample': 1},
            {'func': 'Insert', 'sample': 100},
            {'func': 'skiplistInsert', 'sample': 1},
            {'func': 'skiplistSearch', 'sample': 3},
            {'func': 'SLList_search', 'sample': 3}
        ],
    }

    # # Test run
    # code, msg, _config = before(**_config)
    # print('code: {0}, msg: {1}\n'.format(code, msg))
    # for i in range(1):
    #     code, msg, _config = collect(**_config)
    #     print('code: {0}, msg: {1}\n'.format(code, msg))
    #
    # code, msg, _config = after(**_config)
    # print('code: {0}, msg: {1}\n'.format(code, msg))
    # data_provider.store_profile_to_file('testprofile', _config['profile'])
    #
    # # The computation models demonstration
    # analysis.interval_computation(data_provider.complexity_collector_provider('testprofile'), [Models.all],
    #                               2, 'testprofile')
    #
    # analysis.iterative_computation(data_provider.complexity_collector_provider('testprofile'), [Models.all],
    #                                3, 'testprofile')
    # analysis.full_computation(data_provider.complexity_collector_provider('testprofile'), [Models.all], 'testprofile')
