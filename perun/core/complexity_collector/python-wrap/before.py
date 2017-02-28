""" Standardized 'before.py' module to initialize the specific complexity collector.

"""


import makefiles
import symbols
import configurator


def before(configuration):
    """ Builds, links and configures the complexity collector executable

    Arguments:
        configuration(dict): dictionary containing the configuration settings for the complexity collector

    Returns:
        str: absolute path to the created collector executable
    """
    # Create the configuration cmake and build the configuration executable
    cmake_path = makefiles.create_config_cmake(configuration['target_dir'], configuration['files'])
    exec_path = makefiles.build_executable(cmake_path, makefiles.CMAKE_CONFIG_TARGET)
    # Extract some configuration data using the configuration executable
    function_sym = symbols.extract_symbols(exec_path)
    exclude_list, runtime_filter_list = symbols.filter_symbols(function_sym, configuration['rules'])
    # Create the collector cmake and build the collector executable
    cmake_path = makefiles.create_collector_cmake(configuration['target_dir'], configuration['files'], exclude_list)
    exec_path = makefiles.build_executable(cmake_path, makefiles.CMAKE_COLLECT_TARGET)
    # Create the internal configuration file
    configurator.create_ccicc(exec_path, runtime_filter_list, configuration)

    return exec_path
