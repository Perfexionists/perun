"""Module for cmake generator and executables build process.

In order to create final collector executable, some mid-step stages are required. Notably,
the configuration executable is required, as it provides useful data for creation of time
efficient collector executable.

Configuration executable is simply an executable built from workload source and header files,
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

from __future__ import annotations

# Standard Imports
import os
from subprocess import DEVNULL, CalledProcessError
from typing import TextIO

# Third-Party Imports

# Perun Imports
from perun.utils import log
from perun.utils.external import commands

# Cmake constants that may be changed
CMAKE_VERSION = "3.15.0"
CMAKE_BIN_TARGET = "bin"
CMAKE_CONFIG_TARGET = "WorkloadCfg"
CMAKE_COLLECT_TARGET = "Workload"
CMAKE_PROF_LIB_NAME = "profile"
CMAKE_API_LIB_NAME = "profapi"


def create_config_cmake(target_path: str, file_paths: list[str]) -> str:
    """Creates the cmake file for workload configuration executable

    :param target_path: cmake target directory path
    :param file_paths: paths to the workload source and header files

    :return: absolute path to the created cmake file
    """

    # Open the cmake file and get the path
    cmake_path = _construct_cmake_file_path(target_path)
    with open(cmake_path, "w+") as cmake_handle:
        # Write the basic cmake configuration
        _init_cmake(cmake_handle)

        # Write the build configuration
        _add_build_data(cmake_handle, CMAKE_CONFIG_TARGET, file_paths)

        # Add the api library
        libraries = [_find_library(cmake_handle, CMAKE_API_LIB_NAME, _get_libs_path())]

        # Link with the api library
        _link_libraries(cmake_handle, libraries, CMAKE_CONFIG_TARGET)

    return cmake_path


def create_collector_cmake(target_path: str, file_paths: list[str], exclude_list: list[str]) -> str:
    """Creates the cmake file for workload collector executable

    :param target_path: cmake target directory path
    :param file_paths: paths to the workload source and header files
    :param exclude_list: function names that should be statically excluded

    :return: absolute path to the created cmake file
    """
    # Open the cmake file and get the path
    cmake_path = _construct_cmake_file_path(target_path)
    with open(cmake_path, "w+") as cmake_handle:
        # Write the basic cmake configuration
        _init_cmake(cmake_handle)
        # Extend the configuration for profiling
        _add_profile_instructions(cmake_handle, exclude_list)

        # Write the build configuration
        _add_build_data(cmake_handle, CMAKE_COLLECT_TARGET, file_paths)

        # Add the profiling and api library
        libraries = [
            _find_library(cmake_handle, CMAKE_API_LIB_NAME, _get_libs_path()),
            _find_library(cmake_handle, CMAKE_PROF_LIB_NAME, _get_libs_path()),
        ]

        # Link with the profiling and api library
        _link_libraries(cmake_handle, libraries, CMAKE_COLLECT_TARGET)

    return cmake_path


def build_executable(cmake_path: str, target_name: str) -> str:
    """Invokes call sequence of cmake -> make to build the executable
       Warning - can be time expensive function due to cmake generator and g++ compilation

    :param cmake_path: path to the CMakeLists.txt file
    :param target_name: the target executable name (CMAKE_CONFIG_TARGET or CMAKE_COLLECT_TARGET,
                            depending on the generated cmake type)

    :return: absolute path to the built executable
    """
    # Get the cmake directory
    cmake_dir = os.path.dirname(cmake_path)

    # Try to execute the build commands
    returncode = commands.run_external_command(["cmake", "."], cwd=cmake_dir, stdout=DEVNULL)
    if returncode != 0:
        raise CalledProcessError(returncode, "cmake")
    returncode = commands.run_external_command(["make"], cwd=cmake_dir, stdout=DEVNULL)
    if returncode != 0:
        raise CalledProcessError(returncode, "make")

    # Get the executable path
    return os.path.realpath(os.path.join(cmake_dir, CMAKE_BIN_TARGET, target_name))


def _construct_cmake_file_path(target_path: str) -> str:
    """Constructs the cmake file absolute path

    :param target_path: cmake target directory path

    :return: the constructed cmake file path
    """
    # Extend the path accordingly
    return os.path.realpath(os.path.join(target_path, "CMakeLists.txt"))


def _init_cmake(cmake_file: TextIO) -> None:
    """Writes init configuration to the cmake file

    :param cmake_file: file handle to the opened cmake file
    """
    # Note: We assume that the compiler is fresh enough to support `-no-pie`
    cc_flags = "-std=c++11 -g -fno-pic"
    cc_flags += " -no-pie"
    # Sets the cmake version, paths and compiler config
    cmake_file.write(
        f"cmake_minimum_required(VERSION {CMAKE_VERSION})\n\n"
        f"project(complexity)\n"
        f"# set the paths\n"
        f"set(CMAKE_BINARY_DIR ${{CMAKE_SOURCE_DIR}}/{CMAKE_BIN_TARGET})\n"
        f"set(EXECUTABLE_OUTPUT_PATH ${{CMAKE_BINARY_DIR}})\n\n"
        f"# set the compiler\n"
        f'set(CMAKE_CXX_COMPILER "g++")\n'
        f'set(CMAKE_CXX_FLAGS "${{CMAKE_CXX_FLAGS}} {cc_flags}")\n\n'
    )


def _add_profile_instructions(cmake_file: TextIO, exclude_list: list[str]) -> None:
    """Extends the compiler configuration with instrumentation options

    :param cmake_file: file handle to the opened cmake file
    :param exclude_list: names of statically excluded functions from profiling
    """
    # Enable the instrumentation
    cmake_file.write(
        "# extend the compiler flags for profiling\n"
        'set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -finstrument-functions'
    )
    # Set the excluded functions
    if exclude_list:
        # Create 'sym,sym,sym...' string list from excluded names
        exclude_string = ",".join(exclude_list)
        cmake_file.write(f" -finstrument-functions-exclude-function-list={exclude_string}")
    cmake_file.write('")\n\n')


def _add_build_data(cmake_file: TextIO, target_name: str, source_files: list[str]) -> None:
    """Writes build configuration to the cmake file

    :param cmake_file: file handle to the opened cmake file
    :param target_name: build target name
    :param source_files: paths to the workload source and header files
    """
    # Set the source variable
    cmake_file.write("# set the sources\nset(SOURCE_FILES\n\t")
    # Supply all the workload source files
    sources = "\n\t".join(str(source) for source in source_files)
    sources += "\n)\n\n"
    cmake_file.write(sources)

    # Specify the executable
    cmake_file.write(f"# create the executable\nadd_executable({target_name} ${{SOURCE_FILES}})\n")


def _find_library(cmake_file: TextIO, lib_name: str, lib_path: str) -> str:
    """Finds the profiling library location


    :param cmake_file: file handle to the opened cmake file
    :param lib_name: the name of the library to search for
    :param lib_path: the path to the library directory to search for

    :return: the cmake variable representing the library
    """
    # Create the library variable name
    library_var = f"LIB_{lib_name}"
    # Create instruction to find the library
    cmake_file.write(
        f'\n# Find the library\nfind_library({library_var} {lib_name} PATHS "{lib_path}")\n'
    )
    return library_var


def _link_libraries(cmake_file: TextIO, library_vars: list[str], target_name: str) -> None:
    """Links the profiling library with the collection executable

    :param cmake_file: file handle to the opened cmake file
    :param library_vars: list of libraries to be linked
    :param target_name: build target to be linked with
    """
    # Create the string list of all libraries
    libraries = " ".join(f"${{{lib}}}" for lib in library_vars)
    # Create the target
    cmake_file.write(
        f"\n# Link the libraries to the target\ntarget_link_libraries({target_name} {libraries})\n"
    )


def _get_libs_path() -> str:
    """Return the path to the directory where the libraries needed for compilation should be
    located, or a default location if the directory cannot be found.

    :return: path where the libraries should be located
    """
    try:
        # Get the path to the 'lib' dir within the complexity collector
        libs_dir = os.path.join(os.path.dirname(__file__), "lib")
        if not _libraries_exist(libs_dir):
            log.cprintln(
                (
                    "\nOne or more required libraries are missing - please compile them, "
                    "otherwise the data collection will not work."
                ),
                "white",
            )
        return libs_dir
    except NameError:
        # If the __file__ is not available, the user has to supply the libraries manually
        log.cprintln(
            (
                "\nUnable to locate the directory with profiling libraries automatically, "
                'please supply them manually into the "--target-dir" location'
            ),
            "white",
        )
        return "${CMAKE_SOURCE_DIR}"


def _libraries_exist(libs_dir: str) -> bool:
    """Checks if the required libraries are present in the given directory

    :param libs_dir: the path to the libraries location

    :return: True if both libraries exist in the path
    """
    return os.path.exists(os.path.join(libs_dir, "libprofapi.so")) and os.path.exists(
        os.path.join(libs_dir, "libprofile.so")
    )
