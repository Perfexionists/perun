"""Module for providing coverage-based testing.

Collects functions for preparing the workspace before testing (so it removes remaining files),
collecting source files, initial and common testing and gathering coverage information by
executing gcov tool and parsing its output.
"""

import os
import os.path as path
import subprocess
import statistics

import perun.utils.log as log

from perun.utils.decorators import always_singleton

__author__ = 'Matus Liscinsky'

PROGRAM_ERROR_SIGNALS = {
    "8": "SIGFPE",
    "4": "SIGILL",
    "11": "SIGSEGV",
    "10": "SIGBUS",
    "7": "SIGBUS",
    "6": "SIGABRT",
    "12": "SIGSYS",
    "31": "SIGSYS",
    "5": "SIGTRAP"
}


@always_singleton
def get_gcov_version():
    """Checks the version of the gcov

    :return: version of the gcov
    """
    gcov_output = execute_bin(["gcov", "--version"])
    return int((gcov_output["output"].split("\n")[0]).split()[-1][0])


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
    for file in os.listdir(source_path):
        if file.endswith(".gcda") or file.endswith(".gcov") or file.endswith('.gcov.json.gz'):
            os.remove(path.join(source_path, file))


def execute_bin(command, timeout=None, stdin=None):
    """Executes command with certain timeout.

    :param list command: command to be executed
    :param int timeout: if the process does not end before the specified timeout,
                        the process is terminated
    :param handle stdin: the command input as a file handle
    :return dict: exit code and output string
    """
    command = list(filter(None, command))
    try:
        process = subprocess.Popen(
            command, stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        output, _ = process.communicate(timeout=timeout)
        exit_code = process.wait()

    except subprocess.TimeoutExpired:
        process.terminate()
        raise

    if exit_code != 0 and str(-exit_code) in PROGRAM_ERROR_SIGNALS:
        return {"exit_code": (-exit_code), "output": PROGRAM_ERROR_SIGNALS[str(-exit_code)]}
    return {"exit_code": 0, "output": output.decode('utf-8')}


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
            sources.extend([
                path.join(path.abspath(root), filename) for filename in files
                if path.splitext(filename)[-1] in [".c", ".cpp", ".cc", ".h"]
            ])

    return sources


def baseline_testing(executable, workloads, config, **_):
    """ Coverage based testing initialization. Wrapper over function `get_initial_coverage`.

    :param Executable executable: called command with arguments
    :param list workloads: workloads for initial testing
    :param FuzzingConfiguration config: configuration of the fuzzing
    :param dict _: additional information about paths to .gcno files and source files
    :return tuple: median of measured coverages, paths to .gcov files, paths to source_files
    """
    # get source files (.c, .cc, .cpp, .h)
    config.coverage.source_files = get_src_files(config.coverage.source_path)
    config.coverage.gcov_version = get_gcov_version()
    log.info('Detected gcov version ', end='')
    log.cprint("{}".format(config.coverage.gcov_version), 'white')
    log.info("")

    return get_initial_coverage(executable, workloads, config.hang_timeout, config)


def get_initial_coverage(executable, seeds, timeout, fuzzing_config):
    """ Provides initial testing with initial samples given by user.

    :param int timeout: specified timeout for run of target application
    :param Executable executable: called command with arguments
    :param list seeds: initial sample files
    :param FuzzingConfiguration fuzzing_config: configuration of the fuzzing
    :return int: median of measured coverages
    """
    coverages = []

    # run program with each seed
    for seed in seeds:
        prepare_workspace(fuzzing_config.coverage.gcno_path)

        command = " ".join([path.abspath(executable.cmd), executable.args, seed.path]).split(' ')

        exit_report = execute_bin(command, timeout)
        if exit_report["exit_code"] != 0:
            log.error("Initial testing with file " + seed.path + " caused " + exit_report["output"])
        seed.cov = get_coverage_info(os.getcwd(), fuzzing_config.coverage)

        coverages.append(seed.cov)

    return int(statistics.median(coverages))


def target_testing(executable, workload, *_, config=None, parent=None, fuzzing_progress=None, **__):
    """
    Testing function for coverage based fuzzing. Before testing it prepares the workspace
    using `prepare_workspace` func, executes given command and `get_coverage_info` to
    obtain coverage information.

    :param Executable executable: called command with arguments
    :param list workload: list of workloads
    :param Mutation parent: parent we are mutating
    :param FuzzingConfiguration config: config of the fuzzing
    :param FuzzingProgress fuzzing_progress: progress of the fuzzing process
    :param list _: additional information containing base result and path to .gcno files
    :param dict __: additional information containing base result and path to .gcno files
    :return int: Greater coverage of the two (base coverage, just measured coverage)
    """
    gcno_path = config.coverage.gcno_path
    prepare_workspace(gcno_path)
    command = executable

    command = " ".join([command.cmd, command.args, workload.path]).split(' ')

    exit_report = execute_bin(command, config.hang_timeout)
    if exit_report["exit_code"] != 0:
        log.error(
            "Testing with file " + workload.path + " caused " + exit_report["output"],
            recoverable=True
        )
        raise subprocess.CalledProcessError(exit_report, command)

    workload.cov = get_coverage_info(os.getcwd(), config.coverage)
    return evaluate_coverage(
        fuzzing_progress.base_cov, workload.cov, parent.cov, config.cov_rate
    )


def get_gcov_files(directory):
    """ Searches for gcov files in `directory`.
    :param str directory: path of a directory, where searching will be provided
    :return list: absolute paths of found gcov files
    """
    gcov_files = []
    for file in os.listdir(directory):
        if path.isfile(file) and file.endswith("gcov"):
            gcov_file = path.abspath(path.join(directory, file))
            gcov_files.append(gcov_file)
    return gcov_files


def parse_line(line, coverage_config):
    """

    :param str line: one line in coverage info
    :param CoverageConfiguration coverage_config: configuration of the coverage
    :return: coverage info from one line
    """
    try:
        # intermediate text format
        if coverage_config.has_intermediate_format() and "lcount" in line:
            return int(line.split(",")[1])
        # standard gcov file format
        elif coverage_config.has_common_format():
            return int(line.split(":")[0])
        else:
            return 0
    except ValueError:
        return 0


def get_coverage_info(cwd, coverage_config):
    """ Executes gcov utility with source files, and gathers all output .gcov files.

    First of all, it changes current working directory to directory specified by
    `source_path` and then executes utility gcov over all source files.
    By execution, .gcov files was created as output in intermediate text format("-i") if possible.
    Otherwise, standard gcov output file format  will be parsed.
    Current working directory is now changed back.

    :param str cwd: current working directory for changing back
    :param CoverageConfiguration coverage_config: configuration for coverage
    :return list: absolute paths of generated .gcov files
    """
    os.chdir(coverage_config.gcno_path)

    if coverage_config.has_intermediate_format():
        command = ["gcov", "-i", "-o", "."]
    else:
        command = ["gcov", "-o", "."]
    command.extend(coverage_config.source_files)
    execute_bin(command)

    # searching for gcov files, if they are not already known
    if not coverage_config.gcov_files:
        coverage_config.gcov_files = get_gcov_files(".")

    execs = 0
    for gcov_file in coverage_config.gcov_files:
        with open(gcov_file, "r") as gcov_fp:
            for line in gcov_fp:
                execs += parse_line(line, coverage_config)
    os.chdir(cwd)
    return execs


def evaluate_coverage(base_cov, cov, parent_cov, increase_ratio=1.5):
    """ Condition for adding mutated input to set of candidates(parents).

    :param int base_cov: base coverage
    :param int cov: measured coverage
    :param int parent_cov: coverage of mutation parent
    :param int increase_ratio: desired coverage increase ration between `base_cov` and `cov`
    :return bool: True if `cov` is greater than `base_cov` * `deg_ratio`, False otherwise
    """
    tresh_cov = int(base_cov * increase_ratio)
    return cov > tresh_cov and cov > parent_cov
