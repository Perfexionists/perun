""" Module for cmake generator and executables build process.

    In order to create final collector executable, some mid-step stages are required. Notably,
    the configuration executable is required, as it provides useful data for creation of time
    efficient collector executable.

    Configuration executable is simply a executable built from the workload source and header files,
    with no additional compiler settings or libraries. It is used for function symbols extraction
    and their filtering in order to create symbols exclude list (see symbols.py).

    Collector executable is the final executable used to collect the profiling data. Additional
    compiler settings are configured, such as -finstrument-functions flag and exclude list.
    The C++ profiling library is dynamically linked to this executable to allow the capture,
    processing and storage of records.

    Thoughts: - not only source files but also libraries - requires also heavy extension of
                profiling library
              - add global error log
              - enable the users to also specify their own compiler flags and settings?
"""

import os
import subprocess

import perun.utils.log as log
import perun.utils as utils

# Cmake constants that may be changed
CMAKE_VERSION = '2.8'
CMAKE_BIN_TARGET = 'bin'
CMAKE_CONFIG_TARGET = 'WorkloadCfg'
CMAKE_COLLECT_TARGET = 'Workload'
CMAKE_PROF_LIB_NAME = 'profile'
CMAKE_API_LIB_NAME = 'profapi'


def create_config_cmake(target_path, file_paths):
    """ Creates the cmake file for workload configuration executable

    :param str target_path: cmake target directory path
    :param list file_paths: paths to the workload source and header files

    :return str: absolute path to the created cmake file
    """

    # Open the cmake file and get the path
    cmake_path = _construct_cmake_file_path(target_path)
    with open(cmake_path, 'w+') as cmake_handle:
        # Write the basic cmake configuration
        _init_cmake(cmake_handle)

        # Write the build configuration
        _add_build_data(cmake_handle, CMAKE_CONFIG_TARGET, file_paths)

        # Add the api library
        libraries = [_find_library(cmake_handle, CMAKE_API_LIB_NAME, _get_libs_path())]

        # Link with the api library
        _link_libraries(cmake_handle, libraries, CMAKE_CONFIG_TARGET)

    return cmake_path


def create_collector_cmake(target_path, file_paths, exclude_list):
    """ Creates the cmake file for workload collector executable

    :param str target_path: cmake target directory path
    :param list file_paths: paths to the workload source and header files
    :param list exclude_list: function names that should be statically excluded

    :return str: absolute path to the created cmake file
    """
    # Open the cmake file and get the path
    cmake_path = _construct_cmake_file_path(target_path)
    with open(cmake_path, 'w+') as cmake_handle:
        # Write the basic cmake configuration
        _init_cmake(cmake_handle)
        # Extend the configuration for profiling
        _add_profile_instructions(cmake_handle, exclude_list)

        # Write the build configuration
        _add_build_data(cmake_handle, CMAKE_COLLECT_TARGET, file_paths)

        # Add the profiling and api library
        libraries = [_find_library(cmake_handle, CMAKE_API_LIB_NAME, _get_libs_path()),
                     _find_library(cmake_handle, CMAKE_PROF_LIB_NAME, _get_libs_path())]

        # Link with the profiling and api library
        _link_libraries(cmake_handle, libraries, CMAKE_COLLECT_TARGET)

    return cmake_path


def build_executable(cmake_path, target_name):
    """ Invokes call sequence of cmake -> make to build the executable
       Warning - can be time expensive function due to cmake generator and g++ compilation

    :param str cmake_path: path to the CMakeLists.txt file
    :param str target_name: the target executable name (CMAKE_CONFIG_TARGET or CMAKE_COLLECT_TARGET,
                            depending on the generated cmake type)

    :return str: absolute path to the built executable
    """
    # Get the cmake directory
    cmake_dir = os.path.dirname(cmake_path)

    # Try to execute the build commands
    returncode = utils.run_external_command(['cmake', '.'], cwd=cmake_dir,
                                            stdout=subprocess.DEVNULL)
    if returncode != 0:
        raise subprocess.CalledProcessError(returncode, 'cmake')
    returncode = utils.run_external_command(['make'], cwd=cmake_dir, stdout=subprocess.DEVNULL)
    if returncode != 0:
        raise subprocess.CalledProcessError(returncode, 'make')

    # Get the executable path
    return os.path.realpath(os.path.join(cmake_dir, CMAKE_BIN_TARGET, target_name))


def _construct_cmake_file_path(target_path):
    """ Constructs the cmake file absolute path

    :param str target_path: cmake target directory path

    :return str: the constructed cmake file path
    """
    # Extend the path accordingly
    return os.path.realpath(os.path.join(target_path, 'CMakeLists.txt'))


def _init_cmake(cmake_file):
    """ Writes init configuration to the cmake file

    :param file cmake_file: file handle to the opened cmake file
    """
    # Sets the cmake version, paths and compiler config
    cmake_file.write('cmake_minimum_required(VERSION {0})\n\n'
                     '# set the paths\n'
                     'set(CMAKE_BINARY_DIR ${{CMAKE_SOURCE_DIR}}/{1})\n'
                     'set(EXECUTABLE_OUTPUT_PATH ${{CMAKE_BINARY_DIR}})\n\n'
                     '# set the compiler\n'
                     'set(CMAKE_CXX_COMPILER "g++")\n'
                     'set(CMAKE_CXX_FLAGS "${{CMAKE_CXX_FLAGS}} -std=c++11 -g -fno-pic -no-pie")'
                     '\n\n'
                     .format(CMAKE_VERSION, CMAKE_BIN_TARGET))


def _add_profile_instructions(cmake_file, exclude_list):
    """ Extends the compiler configuration with instrumentation options

    :param file cmake_file: file handle to the opened cmake file
    :param list exclude_list: names of statically excluded functions from profiling
    """
    # Enable the instrumentation
    cmake_file.write('# extend the compiler flags for profiling\n'
                     'set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -finstrument-functions')
    # Set the excluded functions
    if exclude_list:
        # Create 'sym,sym,sym...' string list from excluded names
        exclude_string = ','.join(exclude_list)
        cmake_file.write(' -finstrument-functions-exclude-function-list={0}")\n\n'
                         .format(exclude_string))
    else:
        cmake_file.write('\n\n')


def _add_build_data(cmake_file, target_name, source_files):
    """ Writes build configuration to the cmake file

    :param file cmake_file: file handle to the opened cmake file
    :param str target_name: build target name
    :param list source_files: paths to the workload source and header files
    """
    # Set the source variable
    cmake_file.write('# set the sources\n'
                     'set(SOURCE_FILES\n\t')
    # Supply all the workload source files
    sources = '\n\t'.join(str(source) for source in source_files)
    sources += '\n)\n\n'
    cmake_file.write(sources)

    # Specify the executable
    cmake_file.write('# create the executable\n'
                     'add_executable({0} ${{SOURCE_FILES}})\n'
                     .format(target_name))


def _find_library(cmake_file, lib_name, lib_path):
    """ Finds the profiling library location


    :param cmake_file: file handle to the opened cmake file
    :param str lib_name: the name of the library to search for
    :param str lib_path: the path to the library directory to search for

    :return str: the cmake variable representing the library
    """
    # Create the library variable name
    library_var = 'LIB_{}'.format(lib_name)
    # Create instruction to find the library
    cmake_file.write('\n# Find the library\nfind_library({0} {1} PATHS "{2}")\n'
                     .format(library_var, lib_name, lib_path))
    return library_var


def _link_libraries(cmake_file, library_vars, target_name):
    """ Links the profiling library with the collection executable

    :param file cmake_file: file handle to the opened cmake file
    :param list library_vars: list of libraries to be linked
    :param str target_name: build target to be linked with
    """
    # Create the string list of all libraries
    libraries = ' '.join('${{{0}}}'.format(lib) for lib in library_vars)
    # Create the target
    cmake_file.write('\n# Link the libraries to the target\n'
                     'target_link_libraries({0} {1})\n'
                     .format(target_name, libraries))


def _get_libs_path():
    """Return the path to the directory where the libraries needed for compilation should be
    located, or a default location if the directory cannot be found.

    :return str: path where the libraries should be located
    """
    try:
        # Get the path to the 'lib' dir within the complexity collector
        libs_dir = os.path.join(os.path.dirname(__file__), 'lib')
        if (not os.path.exists(os.path.join(libs_dir, 'libprofapi.so')) or
                not os.path.exists(os.path.join(libs_dir, 'libprofile.so'))):
            log.cprintln('One or more required libraries are missing - please compile them, '
                         'otherwise the data collection will not work.', 'white')
        return libs_dir
    except NameError:
        # If the __file__ is not available, the user has to supply the libraries manually
        log.cprintln('Unable to locate the directory with profiling libraries automatically, '
                     'please supply them manually into the "--target-dir" location', 'white')
        return '${CMAKE_SOURCE_DIR}'
