"""Module for providing coverage-based testing. 

Collects functions for preparing the workspace before testing (so it removes remaining files), 
collecting source files, initial and common testing and gathering coverage information by 
executing gcov tool and parsing its output. 
"""

import os
import os.path as path
import subprocess
import statistics

import perun.utils as utils

__author__ = 'Matus Liscinsky'

ProgramErrorSignals = {"8": "SIGFPE",
                       "4": "SIGILL",
                       "11": "SIGSEGV",
                       "10": "SIGBUS",
                       "7": "SIGBUS",
                       "6": "SIGABRT",
                       "12": "SIGSYS",
                       "31": "SIGSYS",
                       "5": "SIGTRAP"}


def prepare_workspace(source_path):
    """Prepares workspace for yielding coverage information using gcov.

    The .gcda file is generated when a program containing object files built with the GCC 
    -fprofile-arcs() option is executed. We use --coverage which is used to compile and link code
    instrumented for coverage analysis. The option is a synonym for -fprofile-arcs -ftest-coverage 
    (when compiling) and -lgcov (when linking).
    A separate .gcda file is created for each object file compiled with this option. It contains arc
    transition counts, and some summary information. Files with coverage data created using gcov
    utility have extension .gcov.
    Before meaningful testing, residual .gcda and .gcov files have to be removed.

    :param str source_path: path to dir with source files, where coverage info files are stored
    """
    for f in os.listdir(source_path):
        if f.endswith(".gcda") or f.endswith(".gcov"):
            os.remove(path.join(source_path, f))


def execute_bin(command, timeout=15, stdin=None):
    """Executes command with certain timeout. 
    
    :param list command: command to be executed
    :param int timeout: if the process does not end before the specified timeout,
                        the process is terminated
    :param handle stdin: the command input as a file handle
    """
    command = list(filter(None, command))
    process = subprocess.Popen(
        command, stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    process.communicate(timeout=timeout)
    exit_code = process.wait()

    if exit_code != 0 and str(-exit_code) in ProgramErrorSignals:
        return (-exit_code)
    return


def get_src_files(source_path):
    """ Gathers all C/C++ source files in the directory specified by `source_path`

    C/C++ files are identified with extensions: .c, .cc, .cpp. All these types of files located in
    source directory are collected together.

    :param str source_path: path to directory with source files
    :return list: list of source files (their absolute paths) located in `source_path`
    """
    sources = []

    for root, _, files in os.walk(source_path):
        if files:
            sources.extend(
                [path.abspath(root) + "/" + filename for filename in files
                 if path.splitext(filename)[-1] in [".c", ".cpp", ".cc", ".h"]])

    return sources


def init(*args, **kwargs):
    """ Coverage based testing initialization. Wrapper over function `get_initial_coverage`.

    :param list args: list of arguments for initial testing [cmd, args, workloads]
    :param kwargs: additional information about paths to .gcno files and source files 
    :return tuple: median of measured coverages, paths to .gcov files, paths to source_files
    """
    return get_initial_coverage(kwargs["gcno_path"],
                                kwargs["source_path"], kwargs["hang_timeout"],
                                args[0], args[1], args[2])


def get_initial_coverage(gcno_path, source_path, timeout, cmd, args, seeds):
    """ Provides initial testing with initial samples given by user. 

    :param str gcno_path: path to .gcno files, created within building the project (--coverage flag)
    :param str source_path: path to project source files
    :param str cmd: string with command that will be executed
    :param str args: additional parameters to command
    :param list seeds: initial sample files 
    :return tuple: median of measured coverages, paths to .gcov files, paths to source_files
    """
    # get source files (.c, .cc, .cpp, .h)
    source_files = get_src_files(source_path)

    coverages = []

    # run program with each seed
    for file in seeds:

        prepare_workspace(gcno_path)

        command = " ".join([path.abspath(cmd), args, file["path"]]).split(' ')

        exit_report = execute_bin(command, timeout)
        if exit_report != None:
            print("Initial testing with file " +
                  file["path"] + " causes " + ProgramErrorSignals[str(exit_report)] )
            exit(1)
        file["cov"], gcov_files = get_coverage_info(
            source_files, gcno_path, os.getcwd(), None)

        coverages.append(file["cov"])

    return int(statistics.median(coverages)), gcov_files, source_files


def test(*args, **kwargs):
    """
    Testing function for coverage based fuzzing. Before testing it prepares the workspace 
    using `prepare_workspace` func, executes given command and `get_coverage_info` to 
    obtain coverage information.

    :param list args: list of arguments for testing
    :param kwargs: additional information containing base result and path to .gcno files
    :return int: Greater coverage of the two (base coverage, just measured coverage)
    """
    gcno_path = kwargs["gcno_path"]
    prepare_workspace(gcno_path)
    workload = args[2]

    command = " ".join([args[0], args[1], workload["path"]]).split(' ')

    exit_report = execute_bin(command, kwargs["hang_timeout"])
    if exit_report != None:
        print("Testing with file " +
              workload["path"] + " causes " + ProgramErrorSignals[str(exit_report)] )
        raise subprocess.CalledProcessError(exit_report, command)

    workload["cov"], _ = get_coverage_info(
        kwargs["source_files"], gcno_path, os.getcwd(), kwargs["gcov_files"])

    return set_cond(kwargs["base_cov"], workload["cov"], kwargs["icovr"])


def get_coverage_info(source_files, gcno_path, cwd, gcov_files):
    """ Executes gcov utility with source files, and gathers all output .gcov files.

    First of all, it changes current working directory to directory specified by 
    `source_path` and then executes utility gcov over all source files. 
    By execution, .gcov files was created as output in intermediate text format("-i"). 
    These files are collected together for further processing by function
    get_coverage. Current working directory is now changed back.

    Opens every .gcov file, which in intermediate text format, and reads the
        number of executions of every line. Searches for line where "lcount" appears,
        reads the second number (first is line number, second is the number of executions
        of this line) and adds it to total count stored in `execs`.

        Example of .gcov file in intermediate text format:
            file:wordcount.c
            function:29,244,print_tab
            function:37,1,main
            lcount:29,244
            lcount:31,244
            lcount:32,244
            lcount:37,1
            lcount:41,1
            lcount:43,1
            branch:43,nottaken
            branch:43,taken
            lcount:45,0
            lcount:46,0
            lcount:49,1
            lcount:52,1
            lcount:57,1

        In this case, `execs` would be equal to 738.

    :param str gcno_path: path to the directory with files containing coverage information
    :param str source_files: source files of the target project
    :param str cwd: current working directory for changing back
    :return list: absolute paths of generated .gcov files
    """
    os.chdir(gcno_path)
    command = ["gcov", "-i", "-o", "."]
    command.extend(source_files)
    execute_bin(command)

    if gcov_files == None:
        gcov_files = []
        for f in os.listdir("."):
            if path.isfile(f) and f.endswith("gcov"):
                gcov_file = path.abspath(path.join(".", f))
                gcov_files.append(gcov_file)
    execs = 0
    for gcov_file in gcov_files:
        fp = open(gcov_file, "r")
        for line in fp:
            if "lcount" in line:
                execs += int(line.split(",")[1])
        fp.close()
    os.chdir(cwd)
    return execs, gcov_files


def set_cond(base_cov, cov, increase_ratio=1.5):
    """ Condition for adding mutated input to set of canditates(parents).

    :param int base_cov: base coverage
    :param int cov: measured coverage
    :param int cov: desired coverage increase ration between `base_cov` and `cov`
    :return bool: True if `cov` is greater than `base_cov` * `deg_ratio`, False otherwise
    """
    tresh_cov = int(base_cov * increase_ratio)
    return True if cov > tresh_cov else False