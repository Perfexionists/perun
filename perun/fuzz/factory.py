"""Collection of global methods for fuzz testing."""

__author__ = 'Tomas Fiedor, Matus Liscinsky'

import copy
import difflib
import itertools
import os
import os.path as path
import signal
import sys
import time
import threading
from subprocess import CalledProcessError, TimeoutExpired
from uuid import uuid4
import numpy as np

import perun.utils.decorators as decorators
import perun.fuzz.interpret as interpret
import perun.fuzz.filesystem as filesystem
import perun.fuzz.filetype as filetype
import perun.utils.log as log
import perun.fuzz.randomizer as randomizer
import perun.utils as utils
from perun.fuzz.structs import FuzzingProgress

# to ignore numpy division warnings
np.seterr(divide='ignore', invalid='ignore')

FP_ALLOWED_ERROR = 0.00001
RATIO_INCR_CONST = 0.05
RATIO_DECR_CONST = 0.01
MAX_FILES_PER_RULE = 100
SAMPLING = 1.0


def compute_safe_ratio(lhs, rhs):
    """Computes safely the ratio between lhs and rhs

    In case the @p rhs is equal to zero, then the ratio is approximated

    :param int lhs: statistic of method
    :param int rhs: overall statistic
    :return: probability for applying
    """
    try:
        ratio = lhs / rhs
        ratio = 0.1 if (ratio < 0.1) else ratio
    except ZeroDivisionError:
        ratio = 1
    return ratio


def get_max_size(seeds, max_size, max_percentual, max_adjunct):
    """ Finds out max size among the sample files and compare it to specified
    max size of mutated file.

    :param list seeds: list of paths to sample files and their fuzz history
    :param int max_size: user defined max size of mutated file
    :param max_percentual: size specified by percentage
    :param max_adjunct: size to adjunct to max
    :return int: `max_size` if defined, otherwise value depending on adjusting method
                 (percentage portion, adding constant size)
    """
    seed_max = 0
    # gets the largest seed's size
    for file in seeds:
        file_size = path.getsize(file["path"])
        if file_size > seed_max:
            seed_max = file_size

    # --max option was not specified
    if max_size is None:
        if max_percentual is not None:
            return int(seed_max * max_percentual)  # percentual adjusting
        else:
            return seed_max + max_adjunct  # adjusting by size(B)
    else:
        if seed_max >= max_size:
            log.warn("Warning: Specified max size is smaller than the largest workload.")
        return max_size


def fuzz_question(strategy, fuzz_stats, index):
    """ Function decides how many workloads will be generated using certain fuzz method.

    Strategies:
        - "unitary" - always 1
        - "proportional" - depends on how many degradations was caused by this method
        - "probabilistic" - depends on ratio between: num of degradations caused by this method and
                            num of all degradations yet
        - "mixed" - mixed "proportional" and "probabilistic" strategy

    :param str strategy: determines which strategy for deciding will be used
    :param list fuzz_stats: stats of fuzz methods
    :param int index: index in list `fuzz_stats` corresponding to stats of actual method
    :return int: number of generated mutations for rule
    """
    if strategy == "unitary":
        return 1
    elif strategy == "proportional":
        return min(int(fuzz_stats[index])+1, MAX_FILES_PER_RULE)
    elif strategy == "probabilistic":
        ratio = compute_safe_ratio(fuzz_stats[index], fuzz_stats[-1])
        rand = randomizer.rand_from_range(0, 10) / 10
        return 1 if rand <= ratio else 0
    elif strategy == "mixed":
        ratio = compute_safe_ratio(fuzz_stats[index], fuzz_stats[-1])
        rand = randomizer.rand_from_range(0, 10) / 10
        return min(int(fuzz_stats[index])+1, MAX_FILES_PER_RULE) if rand <= ratio else 0


def same_lines(lines, fuzzed_lines, is_binary):
    """Compares two string list and check if they are equal.

    :param list lines: lines of original file
    :param list fuzzed_lines: lines fo fuzzed file
    :param bool is_binary: determines whether a files are binaries or not
    :return bool: True if lines are the same, False otherwise
    """
    if is_binary:
        delta = difflib.unified_diff(
            [line.decode('utf-8', errors='ignore') for line in lines],
            [f_line.decode('utf-8', errors='ignore') for f_line in fuzzed_lines]
        )
    else:
        delta = difflib.unified_diff(lines, fuzzed_lines)
    return len(list(delta)) == 0


def fuzz(parent, max_bytes, fuzz_stats, output_dir, fuzzing_methods, strategy):
    """ Provides fuzzing on workload parent using all the implemented methods.

    Reads the file and store the lines in list. Makes a copy of the list to send it to every
    single function providing one fuzzing method. With every fuzzing method: creates a new file
    with unique name, but with the same extension. It copies the fuzzing history given by
    `fuzz_history`, append the id of used fuzz method and assign it to the new file. If the new file
    would be bigger than specified limit (`max_bytes`), the remainder is cut off.

    :param str parent: path of parent workload file, which will be fuzzed
    :param list fuzz_stats: stats of fuzzing (mutation) strategies
    :param str output_dir: path to the output directory
    :param list fuzzing_methods: selected fuzzing (mutation) strategies
    :param int max_bytes: specify maximum size of created file in bytes
    :param str strategy: string determining strategy for selection number of allowed muts for rules
    :return list: list of touples(new_file, its_fuzzing_history)
    """

    mutations = []

    is_binary, _ = filetype.get_filetype(parent["path"])
    if is_binary:
        fp_in = open(parent["path"], "rb")
    else:
        fp_in = open(parent["path"], "r")

    # reads the file
    lines = fp_in.readlines()
    fp_in.close()

    # "blank file"
    if len(lines) == 0:
        return []

    # split the file to name and extension
    _, file = path.split(parent["path"])
    file, file_extension = path.splitext(file)

    # fuzzing
    for i, method in enumerate(fuzzing_methods):
        for _ in range(fuzz_question(strategy, fuzz_stats, i)):
            fuzzed_lines = lines[:]
            # calling specific fuzz method with copy of parent
            method[0](fuzzed_lines)

            # compare, whether new lines are the same
            if same_lines(lines, fuzzed_lines, is_binary):
                continue

            # new mutation filename and fuzz history
            filename = output_dir + "/" +\
                file.split("-")[0] + "-" + \
                str(uuid4().hex) + file_extension
            new_fh = copy.copy(parent["history"])
            new_fh.append(i)

            predecessor = parent if parent["predecessor"] is None else parent["predecessor"]
            mutations.append(
                {"path": filename, "history": new_fh, "cov": 0,
                 "deg_ratio": 0, "predecessor": predecessor})

            if is_binary:
                fp_out = open(filename, "wb")
                fp_out.write((b"".join(fuzzed_lines))[:max_bytes])
            else:
                fp_out = open(filename, "w")
                fp_out.write("".join(fuzzed_lines)[:max_bytes])

            fp_out.close()

    return mutations


def print_legend(fuzz_stats, fuzzing_methods):
    """ Prints stats of each fuzzing method.

    :param list fuzz_stats: stats of fuzzing (mutation) strategies
    :param list fuzzing_methods: selected fuzzing (mutation) strategies
    """
    print("="*32 + " MUTATION RULES " + "="*32)
    print("id\t Caused deg | cov incr\t Desription ")
    for i, method in enumerate(fuzzing_methods):
        print(str(i) + "\t " +
              str(fuzz_stats[i]) + " times" + "\t\t " + method[1])


def print_results(general_fuzz_information, fuzz_stats, fuzzing_methods):
    """Prints results of fuzzing.

    :param dict general_fuzz_information: general information about current fuzzing
    :param list fuzz_stats: stats of fuzzing (mutation) strategies
    :param list fuzzing_methods: selected fuzzing (mutation) strategies
    """
    print("="*35 + " RESULTS " + "="*35)
    print("Fuzzing time: " + "%.2f" %
          (general_fuzz_information["end_time"] - general_fuzz_information["start_time"]) + "s")
    print("Coverage testing:", general_fuzz_information["coverage_testing"])
    if general_fuzz_information["coverage_testing"]:
        print("Program executions for coverage testing:",
              general_fuzz_information["cov_execs"])
        print("Program executions for performance testing:",
              general_fuzz_information["perun_execs"])
        print("Total program tests:", str(
            general_fuzz_information["perun_execs"] + general_fuzz_information["cov_execs"]))
        print("Maximum coverage ratio:", str(
            general_fuzz_information["max_cov"]))
    else:
        print("Program executions for performance testing:",
              general_fuzz_information["perun_execs"])
    print("Founded degradation mutations:", str(
        general_fuzz_information["degradations"]))
    print("Hangs:", str(general_fuzz_information["hangs"]))
    print("Faults:", str(general_fuzz_information["faults"]))
    print("Worst-case mutation:", str(general_fuzz_information["worst-case"]))
    print_legend(fuzz_stats, fuzzing_methods)


def init_testing(method, *args, **kwargs):
    """ Calls initializing function for `method` testing.

    :param method: testing method, can be "perun_based" or "coverage"
    :param list args: list of arguments for testing
    :param kwargs: additional information for testing
    :return: result of initial testing depending on `method`
    """
    result = utils.dynamic_module_function_call(
        "perun.fuzz", method, "init", *args, **kwargs)
    return result


def testing(method, *args, **kwargs):
    """ Calls testing function for `method` testing.

    :param method: testing method, can be "perun_based" or "coverage"
    :param list args: list of arguments for testing
    :param kwargs: additional information for testing
    :return: result of testing, type depends on `method`
    """
    result = utils.dynamic_module_function_call(
        "perun.fuzz", method, "test", *args, **kwargs)
    return result


def rate_parent(fuzz_progress, parent):
    """ Rate the `parent` with fitness function and adds it to list with fitness values.

    :param FuzzingProgress fuzz_progress: progress of the fuzzing
    :param str parent: path to a file which is classified as parent
    :return int: 1 if a file is the same as any parent, otherwise 0
    """
    increase_cov_rate = parent["cov"] / fuzz_progress.base_cov

    fitness_value = increase_cov_rate + parent["deg_ratio"]

    # empty list or the value is actually the largest
    if not fuzz_progress.parents_fitness_values \
            or fitness_value >= fuzz_progress.parents_fitness_values[-1]["value"]:
        fuzz_progress.parents_fitness_values.append(
            {"value": fitness_value, "mut": parent})
        return 0
    else:
        for index, par_fit_val in enumerate(fuzz_progress.parents_fitness_values):
            if fitness_value <= par_fit_val["value"]:
                fuzz_progress.parents_fitness_values.insert(
                    index, {"value": fitness_value, "mut": parent})
                return 0
            # if the same file was generated before
            elif abs(fitness_value - par_fit_val["value"]) <= FP_ALLOWED_ERROR:
                # additional file comparing
                is_binary_file = filetype.get_filetype(parent["path"])[0]
                mode = "rb" if is_binary_file else "r"
                if same_lines(open(par_fit_val["mut"]["path"], mode).readlines(),
                              open(parent["path"], mode).readlines(), is_binary_file):
                    return 1


def update_rate(parents_fitness_values, parent):
    """ Update rate of the `parent` according to degradation ratio yielded from perf testing.

    :param list parents_fitness_values: sorted list of fitness score of parents
    :param str parent: path to a file which is classified as parent
    """
    for index, par_fit_val in enumerate(parents_fitness_values):
        if par_fit_val["mut"] == parent:
            fitness_value = par_fit_val["value"] * (
                1 + parent["deg_ratio"])
            del parents_fitness_values[index]
            break

    # if its the best rated yet, we save the program from looping
    if fitness_value >= parents_fitness_values[-1]["value"]:
        parents_fitness_values.append(
            {"value": fitness_value, "mut": parent})
        return

    for i in range(index, len(parents_fitness_values)):
        if fitness_value <= parents_fitness_values[i]["value"]:
            parents_fitness_values.insert(
                i, {"value": fitness_value, "mut": parent})
            break


def choose_parent(parents_fitness_values, num_intervals=5):
    """ Chooses one of the workload file, that will be fuzzed.

    If number of parents is smaller than intervals, function provides random choice.
    Otherwise, it splits parents to intervals, each interval assigns weight(probability)
    and does weighted interval selection. Then provides random choice of file from
    selected interval.

    :param list parents_fitness_values: list of mutations sorted according to their fitness score
    :param int num_intervals: number of intervals to which parents will be splitted
    :return list: absolute path to chosen file
    """
    num_of_parents = len(parents_fitness_values)
    if num_of_parents < num_intervals:
        return (randomizer.rand_choice(parents_fitness_values))["mut"]

    triangle_num = (num_intervals*num_intervals + num_intervals) / 2
    bottom = 0
    tresh = int(num_of_parents/num_intervals)
    top = tresh
    intervals = []
    weights = []

    # creates borders of intervals
    for i in range(num_intervals):
        # remainder
        if num_of_parents - top < tresh:
            top = num_of_parents
        intervals.append((bottom, top))
        weights.append((i+1)/triangle_num)
        bottom = top
        top += tresh

    # choose an interval
    interval_idx = np.random.choice(
        range(num_intervals), replace=False, p=weights)
    # choose a parent from the interval
    return (randomizer.rand_choice(
        parents_fitness_values[intervals[interval_idx][0]:intervals[interval_idx][1]]
    ))["mut"]


def save_fuzz_state(time_series, state):
    """Saves current state of fuzzing for plotting.

    :param TimeSeries time_series: list of data for x-axis (typically time values) and y-axis
    :param state: current value of measured variable
    """
    if len(time_series.y_axis) > 1 and state == time_series.y_axis[-2]:
        time_series.x_axis[-1] += SAMPLING
    else:
        time_series.x_axis.append(time_series.x_axis[-1] + SAMPLING)
        time_series.y_axis.append(state)


def teardown(fuzz_progress, output_dirs, parents, fuzz_stats, fuzzing_methods, output_dir, **kwargs
             ):
    """Teardown function at the end of the fuzzing, either by natural rundown of timeout or because
    of unnatural circumstances (e.g. exception)

    :param FuzzingProgress fuzz_progress: Progress of the fuzzing process
    :param str output_dir: output dir for the logs and files
    :param dict output_dirs: dictionary of output dirs for distinct files
    :param list parents: list of parents
    :param list fuzz_stats: list of stats for individual fuzzing methods
    :param list fuzzing_methods: list of fuzzing methods
    :param dict kwargs: rest of the options
    """
    log.info("Executing teardown of the fuzzing. ")
    if not kwargs["no_plotting"]:
        # Plot the results as time series
        log.info("Plotting time series of fuzzing process...")
        interpret.plot_fuzz_time_series(
            fuzz_progress.deg_time_series, output_dirs["graphs"] + "/degradations_ts.pdf",
            "Fuzzing in time", "time (s)", "degradations"
        )
        if fuzz_progress.stats["coverage_testing"]:
            interpret.plot_fuzz_time_series(
                fuzz_progress.cov_time_series, output_dirs["graphs"] + "/coverage_ts.pdf",
                "Max path during fuzing", "time (s)", "executed lines ratio"
            )
    # Plot the differences between seeds and inferred mutation
    interpret.files_diff(fuzz_progress, output_dirs["diffs"])
    # Save log files
    interpret.save_log_files(output_dirs["logs"], fuzz_progress)
    # Clean-up remaining mutations
    filesystem.del_temp_files(parents, fuzz_progress, output_dir)

    fuzz_progress.stats["end_time"] = time.time()
    fuzz_progress.stats["worst-case"] = fuzz_progress.parents_fitness_values[-1]["mut"]["path"]
    print_results(fuzz_progress.stats, fuzz_stats, fuzzing_methods)
    log.done()
    sys.exit(0)


@log.print_elapsed_time
@decorators.phase_function('fuzz performance')
def run_fuzzing_for_command(cmd, args, initial_workload, collector, postprocessor,
                            minor_version_list, **kwargs):
    """Runs fuzzing for a command w.r.t initial set of workloads

    :param str cmd: command to which we will send the fuzzed data
    :param str args: additional commandline args for the command
    :param list initial_workload: initial sample of workloads for fuzzing
    :param str collector: collector used to collect profiling data
    :param list postprocessor: list of postprocessors, which are run after collection
    :param list minor_version_list: list of minor version for which we are collecting
    :param dict kwargs: rest of the keyword arguments
    """

    # Initialization
    fuzz_progress = FuzzingProgress(kwargs['timeout'])

    output_dir = path.abspath(kwargs["output_dir"])
    output_dirs = filesystem.make_output_dirs(
        output_dir, ["hangs", "faults", "diffs", "logs", "graphs"]
    )

    fuzz_progress.stats["coverage_testing"] = \
        (kwargs.get("source_path") and kwargs.get("gcno_path")) is not None

    # getting wokload corpus
    parents = filesystem.get_corpus(
        initial_workload, kwargs["workloads_filter"]
    )
    # choosing appropriate fuzzing methods
    fuzzing_methods = filetype.choose_methods(
        parents[0]["path"], kwargs["regex_rules"]
    )

    # last element is for total num of cov increases or perf degradations
    fuzz_stats = [0] * (len(fuzzing_methods) + 1)

    # getting max size for generated mutations
    max_bytes = get_max_size(
        parents, kwargs.get("max", None), kwargs.get("max_size_percentual", None),
        kwargs.get("max_size_adjunct")
    )

    # Init coverage testing with seeds
    if fuzz_progress.stats["coverage_testing"]:
        log.info("Performing coverage-based testing on parent seeds.")
        try:
            fuzz_progress.base_cov, gcov_version, gcov_files, source_files = init_testing(
                "coverage", cmd, args, parents, collector, postprocessor, minor_version_list,
                **kwargs
            )
            log.done()
        except TimeoutExpired:
            log.error(
                "Timeout ({}s) reached when testing with initial files. Adjust hang timeout using"
                " option --hang-timeout, resp. -h.".format(kwargs["hang_timeout"])
            )

    # No gcno files were found, no coverage testing
    if not fuzz_progress.base_cov:
        fuzz_progress.base_cov = 1  # avoiding possible further zero division
        fuzz_progress.stats["coverage_testing"] = False
        log.warn("No .gcno files were found.")

    log.info("Performing perun-based testing on parent seeds.")
    # Init performance testing with seeds
    base_result_profile = init_testing(
        "perun_based", cmd, args, parents, collector, postprocessor, minor_version_list, **kwargs
    )
    log.done()

    log.info("Rating parents ", end='')
    # Rate seeds
    for parent_seed in parents:
        rate_parent(fuzz_progress, parent_seed)
        log.info('.', end='')
    log.info('')

    # function for saving the state, stores information about run used for plotting graphs
    def save_state():
        save_fuzz_state(
            fuzz_progress.deg_time_series, fuzz_progress.stats["degradations"]
        )
        save_fuzz_state(
            fuzz_progress.cov_time_series, fuzz_progress.stats["max_cov"]
        )

        timer = threading.Timer(SAMPLING, save_state,)
        timer.daemon = True
        timer.start()

    save_state()
    fuzz_progress.stats["start_time"] = time.time()

    # SIGINT (CTRL-C) signal handler
    def signal_handler(sig, _):
        print("Fuzzing process interrupted by signal {}...".format(sig))
        teardown(fuzz_progress, output_dirs, parents, fuzz_stats, fuzzing_methods, **kwargs)

    signal.signal(signal.SIGINT, signal_handler)

    # MAIN LOOP
    while (time.time() - fuzz_progress.stats["start_time"]) < fuzz_progress.timeout:

        # Gathering interesting workloads
        if fuzz_progress.stats["coverage_testing"]:
            method = "coverage"
            execs = 0

            while len(fuzz_progress.interesting_workloads) < kwargs["interesting_files_limit"] and \
                    execs < kwargs["execs"]:

                current_workload = choose_parent(fuzz_progress.parents_fitness_values)
                mutations = fuzz(
                    current_workload, max_bytes, fuzz_stats, output_dir, fuzzing_methods,
                    kwargs["mut_count_strategy"]
                )

                for i, _ in enumerate(mutations):
                    try:
                        execs += 1
                        fuzz_progress.stats["cov_execs"] += 1
                        # testing for coverage
                        result = testing(
                            method, cmd, args, mutations[i], collector, postprocessor,
                            minor_version_list, base_cov=fuzz_progress.base_cov,
                            source_files=source_files, gcov_version=gcov_version,
                            gcov_files=gcov_files, parent=current_workload, **kwargs
                        )
                    # error occured
                    except CalledProcessError:
                        fuzz_progress.stats["faults"] += 1
                        result = True
                        mutations[i]["path"] = filesystem.move_file_to(
                            mutations[i]["path"], output_dirs["faults"]
                        )
                        fuzz_progress.faults.append(mutations[i])
                    # timeout expired
                    except TimeoutExpired:
                        fuzz_progress.stats["hangs"] += 1
                        print("Timeout ({}s) reached when testing. See {}.".format(
                            kwargs["hang_timeout"], output_dirs["hangs"])
                        )
                        mutations[i]["path"] = filesystem.move_file_to(
                            mutations[i]["path"], output_dirs["hangs"]
                        )
                        fuzz_progress.hangs.append(mutations[i])
                        continue

                    # if successful mutation
                    if result and not rate_parent(fuzz_progress, mutations[i]):
                        # TODO: Fix this ugly
                        fuzz_progress.stats["max_cov"] = \
                            fuzz_progress.parents_fitness_values[-1]["mut"]["cov"] / \
                            fuzz_progress.base_cov
                        parents.append(mutations[i])
                        fuzz_progress.interesting_workloads.append(mutations[i])
                        fuzz_stats[(mutations[i]["history"])[-1]] += 1
                        fuzz_stats[-1] += 1
                    # not successful mutation or the same file as previously generated
                    else:
                        os.remove(mutations[i]["path"])

            # adapting increase coverage ratio
            if fuzz_progress.interesting_workloads:
                kwargs["icovr"] += RATIO_INCR_CONST
            else:
                if kwargs["icovr"] > RATIO_DECR_CONST:
                    kwargs["icovr"] -= RATIO_DECR_CONST

        # not coverage testing, only performance testing
        else:
            current_workload = choose_parent(fuzz_progress.parents_fitness_values)
            fuzz_progress.interesting_workloads = fuzz(
                current_workload, max_bytes, fuzz_stats, output_dir, fuzzing_methods,
                kwargs["mut_count_strategy"]
            )
        method = "perun_based"

        for i, _ in enumerate(fuzz_progress.interesting_workloads):
            base_result_profile, base_copy = itertools.tee(
                base_result_profile
            )  # creates copy of generator

            # testing with perun
            try:
                fuzz_progress.stats["perun_execs"] += 1
                result = testing(
                    method, cmd, args, fuzz_progress.interesting_workloads[i], collector,
                    postprocessor, minor_version_list, base_result=base_copy, **kwargs
                )
            # temporarily we ignore error within individual perf testing without previous cov test
            except Exception as exc:
                log.warn("Executing binary raised an exception: ", exc)
                result = False

            if result:
                fuzz_stats[(fuzz_progress.interesting_workloads[i]["history"])[-1]] += 1
                fuzz_stats[-1] += 1
                # without cov testing we firstly rate the new parents here
                if not fuzz_progress.stats["coverage_testing"]:
                    parents.append(fuzz_progress.interesting_workloads[i])
                    rate_parent(fuzz_progress, fuzz_progress.interesting_workloads[i])
                # for only updating the parent rate
                else:
                    update_rate(
                        fuzz_progress.parents_fitness_values, fuzz_progress.interesting_workloads[i]
                    )

                # appending to final results
                fuzz_progress.final_results.append(fuzz_progress.interesting_workloads[i])
                fuzz_progress.stats["degradations"] += 1
            else:
                # in case of testing with coverage, parent wont be removed but used for mutation
                if not fuzz_progress.stats["coverage_testing"]:
                    os.remove(fuzz_progress.interesting_workloads[i]["path"])

        # deletes interesting workloads for next run
        del fuzz_progress.interesting_workloads[:]

    # get end time
    fuzz_progress.stats["end_time"] = time.time()

    teardown(fuzz_progress, output_dirs, parents, fuzz_stats, fuzzing_methods, **kwargs)
