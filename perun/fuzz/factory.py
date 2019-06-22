"""Collection of global methods for fuzz testing."""

__author__ = 'Tomas Fiedor, Matus Liscinsky'

import click
import copy
import difflib
import itertools
import matplotlib.pyplot as plt
import numpy as np
import os
import os.path as path
import random
import signal
import subprocess
import sys
import time
import threading
from uuid import uuid4

import perun.check.factory as check
import perun.fuzz.coverage as coverage
import perun.utils.decorators as decorators
import perun.fuzz.filesystem as filesystem
import perun.fuzz.interpret as interpret
import perun.logic.runner as run
import perun.utils as utils
from perun.fuzz.filetype import choose_methods, get_filetype
from perun.utils.structs import PerformanceChange

# to ignore numpy division warnings
np.seterr(divide='ignore', invalid='ignore')

FP_ALLOWED_ERROR = 0.00001
RATIO_INCR_CONST = 0.05
RATIO_DECR_CONST = 0.01
MAX_FILES_PER_RULE = 100


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
    if max_size == None:
        if max_percentual != None:
            return int(seed_max * max_percentual)  # percentual adjusting
        else:
            return seed_max + max_adjunct  # adjusting by size(B)
    else:
        if seed_max >= max_size:
            print("Warning: Specified max size is smaller than the largest workload.")
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
        try:
            probability = fuzz_stats[index] / fuzz_stats[-1]
            probability = 0.1 if (probability < 0.1) else probability
        except ZeroDivisionError:
            probability = 1
        rand = random.uniform(0, 1)
        return 1 if rand <= probability else 0
    elif strategy == "mixed":
        try:
            probability = fuzz_stats[index] / fuzz_stats[-1]
            probability = 0.1 if (probability < 0.1) else probability
        except ZeroDivisionError:
            probability = 1
        rand = random.uniform(0, 1)
        return min(int(fuzz_stats[index])+1, MAX_FILES_PER_RULE) if rand <= probability else 0


def same_lines(lines, fuzzed_lines, is_binary):
    """Compares two string list and check if they are equal.

    :param list lines: lines of original file
    :param list fuzzed_lines: lines fo fuzzed file
    :param is_binary bool: determines whether a files are binaries or not
    :return bool: True if lines are the same, False otherwise
    """
    if is_binary:
        delta = difflib.unified_diff([line.decode('utf-8', errors='ignore') for line in lines],
                                     [f_line.decode('utf-8', errors='ignore') for f_line in fuzzed_lines])
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
    :param list fuzz_history: history of used fuzz methods on parent file
    :param list fuzz_stats: stats of fuzzing (mutation) strategies 
    :param str output_dir: path to the output directory
    :param list fuzzing_methods: selected fuzzing (mutation) strategies
    :param int max_bytes: specify maximum size of created file in bytes
    :param str strategy: string determining strategy for selection number of allowed muts for rules
    :return list: list of touples(new_file, its_fuzzing_history)
    """

    lines = []
    mutations = []

    is_binary, _ = get_filetype(parent["path"])
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
    for i in range(len(fuzzing_methods)):
        for _ in range(fuzz_question(strategy, fuzz_stats, i)):
            fuzzed_lines = lines[:]
            # calling specific fuzz method with copy of parent
            fuzzing_methods[i][0](fuzzed_lines)

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
    for i in range(len(fuzzing_methods)):
        print(str(i) + "\t " +
              str(fuzz_stats[i]) + " times" + "\t\t " + fuzzing_methods[i][1])


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


def rate_parent(parents_fitness_values, parent, base_cov=1):
    """ Rate the `parent` with fitness function and adds it to list with fitness values.

    :param list parents_fitness_values: sorted list of fitness score of parents
    :param str parent: path to a file which is classified as parent
    :param int base_cov: baseline coverage
    :return int: 1 if files is the same as some parent, otherwise 0 
    """
    increase_cov_rate = parent["cov"]/base_cov

    fitness_value = increase_cov_rate + parent["deg_ratio"]

    # empty list or the value is actually the largest
    if not parents_fitness_values or fitness_value >= parents_fitness_values[-1]["value"]:
        parents_fitness_values.append(
            {"value": fitness_value, "mut": parent})
        return 0
    else:
        for index in range(len(parents_fitness_values)):
            if fitness_value <= parents_fitness_values[index]["value"]:
                parents_fitness_values.insert(
                    index, {"value": fitness_value, "mut": parent})
                return 0
            # if the same file was generated before
            elif abs(fitness_value - parents_fitness_values[index]["value"]) <= FP_ALLOWED_ERROR:
                # additional file comparing
                if same_lines(open(parents_fitness_values[index]["mut"]["path"]).readlines(),
                              open(parent["path"]).readlines(), get_filetype(parent["path"])[0]):
                    return 1


def update_rate(parents_fitness_values, parent):
    """ Update rate of the `parent` according to degradation ratio yielded from perf testing.

    :param list parents_fitness_values: sorted list of fitness score of parents
    :param str parent: path to a file which is classified as parent
    """
    for index in range(len(parents_fitness_values)):
        if parents_fitness_values[index]["mut"] == parent:
            fitness_value = parents_fitness_values[index]["value"] * (
                1 + parent["deg_ratio"])
            del parents_fitness_values[index]
            break

    # if its the best rated yet, we save the program from looping
    if fitness_value >= parents_fitness_values[-1]["value"]:
        parents_fitness_values.append(
            {"value": fitness_value, "mut": parent})
        return

    for i in range(index, len(parents_fitness_values)):
        if fitness_value <= parents_fitness_values[i]['value']:
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
    :param num_intervals: number of intervals to which parents will be splitted
    :return list: absolute path to chosen file
    """
    max = len(parents_fitness_values)
    if max < num_intervals:
        return (random.choice(parents_fitness_values))["mut"]

    triangle_num = (num_intervals*num_intervals + num_intervals) / 2
    bottom = 0
    tresh = int(max/num_intervals)
    top = tresh
    intervals = []
    weights = []

    # creates borders of intervals
    for i in range(num_intervals):
        # remainder
        if max - top < tresh:
            top = max
        intervals.append((bottom, top))
        weights.append((i+1)/triangle_num)
        bottom = top
        top += tresh

    # choose an interval
    interval_idx = np.random.choice(
        range(num_intervals), replace=False, p=weights)
    # choose a parent from the interval
    return (random.choice(parents_fitness_values[intervals[interval_idx][0]:
                                                 intervals[interval_idx][1]]))["mut"]


def print_msg(msg):
    """Temporary solution for printing fuzzing messages to the output.

    :param msg: message to be printed
    """
    print("-"*70)
    print(msg)
    print("-"*70)


@decorators.print_elapsed_time
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
    faults = []
    hangs = []
    interesting_workloads = []
    parents_fitness_values = []
    final_results = []
    timeout = kwargs["timeout"]
    general_fuzz_information = {"start_time": 0.0, "end_time": 0.0, "cov_execs": 0, "perun_execs": 0,
                                "degradations": 0, "max_cov": 1.0, "coverage_testing": False,
                                "worst-case": None, "hangs": 0, "faults": 0}
    base_cov = 1

    output_dir = path.abspath(kwargs["output_dir"])
    output_dirs = filesystem.make_output_dirs(
        output_dir, ["hangs", "faults", "diffs", "logs", "graphs"])

    general_fuzz_information["coverage_testing"] = (kwargs.get("source_path")
                                                    and kwargs.get("gcno_path")) != None

    # getting wokload corpus
    parents = filesystem.get_corpus(
        initial_workload, kwargs["workloads_filter"])
    # choosing appropriate fuzzing methods
    fuzzing_methods = choose_methods(
        parents[0]["path"], kwargs["regex_rules"])

    # last element is for total num of cov increases or perf degradations
    fuzz_stats = [0] * (len(fuzzing_methods) + 1)

    # getting max size for generated mutations
    max_bytes = get_max_size(parents, kwargs.get("max", None),
                             kwargs.get("max_size_percentual", None),
                             kwargs.get("max_size_adjunct"))

    # Init coverage testing with seeds
    if general_fuzz_information["coverage_testing"]:
        try:
            base_cov, gcov_version, gcov_files, source_files = init_testing("coverage", cmd, args,
                                                                            parents, collector,
                                                                            postprocessor,
                                                                            minor_version_list,
                                                                            **kwargs)
        except subprocess.TimeoutExpired:
            print(
                "Timeout ({}s) reached when testing with initial files. Adjust hang timeout using"
                " option --hang-timeout, resp. -h.".format(kwargs["hang_timeout"]))
            sys.exit(1)

    # Init performance testing with seeds
    base_result_profile = init_testing("perun_based", cmd, args, parents, collector,
                                       postprocessor, minor_version_list, **kwargs)

    # No gcno files were found, no coverage testing
    if base_cov == 0:
        base_cov = 1  # avoiding possible further zero division
        general_fuzz_information["coverage_testing"] = False
        print_msg("No .gcno files were found.")

    # Rate seeds
    for s in parents:
        rate_parent(parents_fitness_values, s, base_cov)

    print_msg("INITIAL TESTING COMPLETED")
    execs = 0

    # Time series plotting
    time_data = [0]
    degradations = [0]

    time_for_cov = [0]
    max_covs = [1.0]

    SAMPLING = 1.0

    # function for saving the state, stores information about run used for plotting graphs
    def save_state():
        # if number of degradations has NOT changed
        if len(degradations) > 1 and general_fuzz_information["degradations"] == degradations[-2]:
            time_data[-1] += SAMPLING
        else:
            time_data.append(time_data[-1] + SAMPLING)
            degradations.append(general_fuzz_information["degradations"])

        # if max cov has NOT changed
        if len(max_covs) > 1 and general_fuzz_information["max_cov"] == max_covs[-2]:
            time_for_cov[-1] += SAMPLING
        else:
            time_for_cov.append(time_for_cov[-1] + SAMPLING)
            max_covs.append(general_fuzz_information["max_cov"])

        t = threading.Timer(SAMPLING, save_state,)
        t.daemon = True
        t.start()

    save_state()
    general_fuzz_information["start_time"] = time.time()

    # SIGINT (CTRL-C) signal handler
    def signal_handler(sig, frame):
        print("Fuzzing process interrupted ...")
        print("Plotting graphs ...")
        interpret.plot_fuzz_time_series(
            time_data, degradations, output_dirs["graphs"] +
            "/degradations_ts.pdf", "Fuzzing in time",
            "time (s)", "degradations")
        if general_fuzz_information["coverage_testing"]:
            interpret.plot_fuzz_time_series(
                time_for_cov, max_covs, output_dirs["graphs"] +
                "/coverage_ts.pdf",
                "Max path during fuzing", "time (s)", "executed lines ratio")
        # diffs
        interpret.files_diff(final_results, faults,
                             hangs, output_dirs["diffs"])
        # save log files
        interpret.save_log_files(output_dirs["logs"], time_data, degradations, time_for_cov,
                                 max_covs, parents_fitness_values, base_cov, hangs, faults)
        # remove remaining mutations
        filesystem.del_temp_files(parents, final_results, hangs, faults, output_dir)

        general_fuzz_information["end_time"] = time.time()
        general_fuzz_information["worst-case"] = parents_fitness_values[-1]["mut"]["path"]
        print_results(general_fuzz_information, fuzz_stats, fuzzing_methods)
        sys.exit(0)
    signal.signal(signal.SIGINT, signal_handler)

    # MAIN LOOP
    while (time.time() - general_fuzz_information["start_time"]) < timeout:

        # Gathering interesting workloads
        if general_fuzz_information["coverage_testing"]:
            print_msg("Coverage based fuzzing")
            method = "coverage"
            execs = 0
            # print("icovr", kwargs["icovr"])
            while len(interesting_workloads) < kwargs["interesting_files_limit"] and \
                    execs < kwargs["execs"]:

                current_workload = choose_parent(parents_fitness_values)
                mutations = fuzz(current_workload, max_bytes, fuzz_stats,
                                 output_dir, fuzzing_methods, kwargs["mut_count_strategy"])

                for i in range(len(mutations)):
                    try:
                        execs += 1
                        general_fuzz_information["cov_execs"] += 1
                        # testing for coverage
                        result = testing(method, cmd, args, mutations[i], collector,
                                         postprocessor, minor_version_list, base_cov=base_cov,
                                         source_files=source_files, gcov_version=gcov_version,
                                         gcov_files=gcov_files, parent=current_workload, **kwargs)
                    # error occured
                    except subprocess.CalledProcessError:
                        general_fuzz_information["faults"] += 1
                        result = True
                        mutations[i]["path"] = filesystem.move_file_to(
                            mutations[i]["path"], output_dirs["faults"])
                        faults.append(mutations[i])
                    # timeout expired
                    except subprocess.TimeoutExpired:
                        general_fuzz_information["hangs"] += 1
                        print("Timeout ({}s) reached when testing. See {}.".format(
                            kwargs["hang_timeout"], output_dirs["hangs"]))
                        mutations[i]["path"] = filesystem.move_file_to(
                            mutations[i]["path"], output_dirs["hangs"])
                        hangs.append(mutations[i])
                        continue

                    # if successful mutation
                    if result:
                        if rate_parent(parents_fitness_values,
                                       mutations[i], base_cov):
                            try:
                                # the same file as previously generated
                                os.remove(mutations[i]["path"])
                            except FileNotFoundError:
                                pass
                        else:
                            # print("Increase of coverage",
                                #   result, mutations[i])
                            # print("|", end=' ')
                            general_fuzz_information["max_cov"] = parents_fitness_values[-1]["mut"]["cov"] / base_cov
                            parents.append(mutations[i])
                            interesting_workloads.append(mutations[i])
                            fuzz_stats[(mutations[i]["history"])[-1]] += 1
                            fuzz_stats[-1] += 1
                    # not successful mutation
                    else:
                        try:
                            pass
                            os.remove(mutations[i]["path"])
                        except FileNotFoundError:
                            pass

            # adapting increase coverage ratio
            if interesting_workloads:
                kwargs["icovr"] += RATIO_INCR_CONST
            else:
                if kwargs["icovr"] > RATIO_DECR_CONST:
                    kwargs["icovr"] -= RATIO_DECR_CONST

        # not coverage testing, only performance testing
        else:
            current_workload = choose_parent(parents_fitness_values)
            interesting_workloads = fuzz(current_workload, max_bytes, fuzz_stats,
                                         output_dir, fuzzing_methods, kwargs["mut_count_strategy"])
        method = "perun_based"

        print_msg("Performance testing")

        for i in range(len(interesting_workloads)):
            base_result_profile, base_copy = itertools.tee(
                base_result_profile)  # creates copy of generator

            # testing with perun
            try:
                general_fuzz_information["perun_execs"] += 1
                result = testing(method, cmd, args, interesting_workloads[i], collector,
                                 postprocessor, minor_version_list, base_result=base_copy,
                                 **kwargs)
            # temporarily we ignore error within individual perf testing without previous cov test
            except Exception as e:
                print("Executing binary raised an exception: ", e)
                result = False

            if result:
                fuzz_stats[(interesting_workloads[i]["history"])[-1]] += 1
                fuzz_stats[-1] += 1
                # without cov testing we firstly rate the new parents here
                if not general_fuzz_information["coverage_testing"]:
                    parents.append(interesting_workloads[i])
                    rate_parent(parents_fitness_values,
                                interesting_workloads[i], base_cov)
                # for only updating the parent rate
                else:
                    update_rate(parents_fitness_values,
                                interesting_workloads[i])

                # appending to final results
                final_results.append(interesting_workloads[i])
                general_fuzz_information["degradations"] += 1
            else:
                if not general_fuzz_information["coverage_testing"]:
                    try:
                        os.remove(interesting_workloads[i]["path"])
                    except FileNotFoundError:
                        pass

        # deletes interesting workloads for next run
        del interesting_workloads[:]

    # get end time
    general_fuzz_information["end_time"] = time.time()

    # print info about fuzzing
    print("="*79)  # temporary solution :) UI comming soon
    print("Fuzzing successfully finished.")

    # plotting time_data, data, filename, title, xlabel, ylabel
    print("Plotting graphs ...")
    interpret.plot_fuzz_time_series(
        time_data, degradations, output_dirs["graphs"] +
        "/degradations_ts.pdf", "Fuzzing in time",
        "time (s)", "degradations")

    if general_fuzz_information["coverage_testing"]:
        interpret.plot_fuzz_time_series(
            time_for_cov, max_covs, output_dirs["graphs"] +
            "/coverage_ts.pdf", "Max path during fuzing",
            "time (s)", "executed lines ratio")

    # diffs
    interpret.files_diff(final_results, faults, hangs, output_dirs["diffs"])

    # save log files
    interpret.save_log_files(output_dirs["logs"], time_data, degradations, time_for_cov,
                             max_covs, parents_fitness_values, base_cov, hangs, faults)

    # deletes parents which are not final results, good parents but not causing deg
    filesystem.del_temp_files(parents, final_results, hangs, faults, output_dir)
    # for x in parents_fitness_values:
    #     print(x["value"], "=", x["mut"]["cov"]/base_cov, "*( 1 +", x["mut"]["deg_ratio"], ")")

    general_fuzz_information["worst-case"] = parents_fitness_values[-1]["mut"]["path"]
    print_results(general_fuzz_information, fuzz_stats, fuzzing_methods)
