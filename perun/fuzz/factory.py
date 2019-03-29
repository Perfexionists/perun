"""Collection of global methods for fuzz testing."""

__author__ = 'Tomas Fiedor, Matus Liscinsky'

import click
import copy
import itertools
import numpy as np
import os
import os.path as path
import random
import signal
import subprocess
import sys
import time
from uuid import uuid4

import perun.check.factory as check
import perun.fuzz.coverage as coverage
import perun.utils.decorators as decorators
import perun.logic.runner as run
import perun.utils as utils
from perun.fuzz.filetype import choose_methods, get_filetype
from perun.utils.structs import PerformanceChange

# to ignore numpy division warnings
np.seterr(divide='ignore', invalid='ignore')


def get_corpus(workloads):
    """ Iteratively search for files to fill input corpus.

    :param list workloads: list of paths to sample files or directories of sample files
    :return list: list of dictonaries, dictionary contains information about file
    """
    init_seeds = []

    for w in workloads:
        if path.isdir(w) and os.access(w, os.R_OK):
            for root, _, files in os.walk(w):
                if files:
                    init_seeds.extend(
                        [{"path": path.abspath(root) + "/" + filename, "history": [], "cov": 0,
                          "deg_ratio": 0} for filename in files])
        else:
            init_seeds.append({"path": path.abspath(w), "history": [],
                               "cov": 0, "deg_ratio": 0})
    return init_seeds


def get_max_size(seeds, max_size, max_percentual, max_adjunct):
    """ Finds out max size among the sample files and compare it to specified 
    max size of mutated file.

    :param list seeds: list of paths to sample files and their fuzz history
    :param int max_size: user defined max size of mutated file
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
    """ Function decides how many inputs will be generated using certain fuzz method.

    Strategies:
        - "unitary" - always 1
        - "proportional" - depends on how many degradations was caused by this method
        - "probabilistic" - depends on ratio between: num of degradations caused by this method and 
                            num of all degradations yet
        - "mixed" - mixed "proportional" and "probabilistic" strategy 

    :param str strategy: determines which strategy for deciding will be used
    :param list fuzz_stats: stats of fuzz methods
    :param int index: index in list `fuzz_stats` corresponding to stats of actual method 
    """
    if strategy == "unitary":
        return 1
    elif strategy == "proportional":
        return int(fuzz_stats[index])+1
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
        return int(fuzz_stats[index])+1 if rand <= probability else 0


def fuzz(parent, fuzz_history, max_bytes, fuzz_stats, output_dir, fuzzing_methods, strategy):
    """ Provides fuzzing on input parent using all the implemented methods. 

    Reads the file and store the lines in list. Makes a copy of the list to send it to every 
    single function providing one fuzzing method. With every fuzzing method: creates a new file 
    with unique name, but with the same extension. It copies the fuzzing history given by 
    `fuzz_history`, append the id of used fuzz method and assign it to the new file. If the new file
    would be bigger than specified limit (`max_bytes`), the remainder is cut off.

    :param str parent: path of parent input file, which will be fuzzed
    :param list fuzz_history: history of used fuzz methods on parent file
    :param int max_bytes: specify maximum size of created file in bytes
    :return list: list of touples(new_file, its_fuzzing_history)
    """

    lines = []
    mutations = []

    is_binary, _ = get_filetype(parent)

    if is_binary:
        fp_in = open(parent, "rb")
    else:
        fp_in = open(parent, "r")

    # reads the file
    for line in fp_in:
        lines.append(line)
    fp_in.close()

    # "blank file"
    if len(lines) == 0:
        return []

    # split the file to name and extension
    _, file = path.split(parent)
    file, file_extension = path.splitext(file)

    # fuzzing
    for i in range(len(fuzzing_methods)):
        for _ in range(fuzz_question(strategy, fuzz_stats, i)):
            fuzzed_lines = lines[:]
            # calling specific fuzz method with copy of parent
            fuzzing_methods[i][0](fuzzed_lines)

            # new mutation filename and fuzz history
            filename = output_dir + "/" +\
                file.split("-")[0] + "-" + \
                str(uuid4().hex) + file_extension
            new_fh = copy.copy(fuzz_history)
            new_fh.append(i)

            mutations.append(
                {"path": filename, "history": new_fh, "cov": 0, "deg_ratio": 0})

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
    """
    print_msg("="*30 + " FUZZING STRATEGIES " + "="*30)
    print("id\t Caused degradation | coverage increase\t Desription ")
    for i in range(len(fuzzing_methods)):
        print(str(i) + "\t " +
              str(fuzz_stats[i]) + " times" + "\t\t\t " + fuzzing_methods[i][1])


def print_results(timeout, fuzz_stats, fuzzing_methods):
    """ Prints results of fuzzing.
    """
    print_msg("="*35 + " RESULTS " + "="*35)
    print("exec time: " + "%.2f" % timeout + "s")
    print_legend(fuzz_stats, fuzzing_methods)


def move_mutation_to(mutation, dir):
    """ Useful function for moving mutation file to special directory in case of fault or hang.

    :param str mutation: path to a mutation file
    :param str dir: path of destination directory, where `mutation` should be moved
    """
    _, file = path.split(mutation)
    os.rename(mutation, dir + "/" + file)


def make_output_dirs(output_dir):
    """ Creates special directories for mutations causing fault or hang.

    :param str output_dir: path to user-specified output directory
    :return tuple: paths to newly created directories 
    """
    os.makedirs(output_dir + "/hangs", exist_ok=True)
    os.makedirs(output_dir + "/faults", exist_ok=True)
    return output_dir + "/hangs", output_dir + "/faults"


def init_testing(method, *args, **kwargs):
    """ Calls initializing function for `method` testing.

    :param method: testing method, can be "perun_based" or "coverage"
    :param list args: list of arguments for testing
    :param kwargs: additional information for testing
    :return InitFuzzResult: result of initial testing depending on `method`
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


def del_temp_files(final_results, output_dir):
    """ Deletes temporary files that are not positive results of fuzz testing

    :param list final_results: succesfully mutated files causing degradation, yield of testing
    :param str output_dir: path to directory, where fuzzed files are stored
    """
    final_results_paths = [mutation["path"] for mutation in final_results]
    for file in os.listdir(output_dir):
        f = path.abspath(path.join(output_dir, file))
        if path.isfile(f) and f not in final_results_paths:
            os.remove(f)


def rate_parent(parents_fitness_values, parent, base_cov=1):
    """ Rate the `parent` with fitness function and adds it to list with fitness values.

    :param list parents_fitness_values: sorted list of fitness score of parents
    :param str parent: path to a file which is classified as parent
    :param int base_cov: baseline coverage
    """
    try:
        increase_cov_rate = parent["cov"]/base_cov
    except ZeroDivisionError:
        increase_cov_rate = 0

    fitness_value = increase_cov_rate + parent["deg_ratio"]

    # empty list or the value is actually the largest
    if not parents_fitness_values or fitness_value > parents_fitness_values[-1]["value"]:
        parents_fitness_values.append(
            {"value": fitness_value, "mut": parent})

    else:
        for index, mut in enumerate(parents_fitness_values):
            if fitness_value < mut["value"]:
                parents_fitness_values.insert(
                    index, {"value": fitness_value, "mut": parent})
                break


def choose_parent(parents_fitness_values, num_intervals=5):
    """ Chooses one of the input file, that will be fuzzed. 

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
    """ Temporary solution for printing fuzzing messages to the output.

    :param msg: message to be printed
    """
    print("-"*50)
    print(msg)
    print("-"*50)


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
    interesting_inputs = []
    parents_fitness_values = []
    final_results = []
    timeout = kwargs["timeout"]
    base_cov = 1

    output_dir = path.abspath(kwargs["output_dir"])
    hangs_dir, faults_dir = make_output_dirs(output_dir)
    coverage_testing = (kwargs.get("source_path")
                        and kwargs.get("gcno_path")) != None

    parents = get_corpus(initial_workload)

    fuzzing_methods = choose_methods(
        parents[0]["path"], kwargs["regex_rules"])
    fuzz_stats = [0] * (len(fuzzing_methods) + 1)

    max_bytes = get_max_size(parents, kwargs.get("max", None),
                             kwargs.get("max_size_percentual", None),
                             kwargs.get("max_size_adjunct"))

    # Init testing with seeds
    if coverage_testing:
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

    base_result_profile = init_testing("perun_based", cmd, args, parents, collector,
                                       postprocessor, minor_version_list, **kwargs)

    if base_cov == 0:
        coverage_testing = False
        print_msg("No .gcno files were found.")

    # Rate seeds
    for s in parents:
        rate_parent(parents_fitness_values, s, base_cov)

    print_msg("INITIAL TESTING COMPLETED")
    execs = 0
    icovr = kwargs['icovr']

    start = time.time()
    # SIGINT (CTRL-C) signal handler

    def signal_handler(sig, frame):
        del_temp_files(final_results, output_dir)
        print_results(time.time() - start, fuzz_stats, fuzzing_methods)
        sys.exit(0)
    signal.signal(signal.SIGINT, signal_handler)

    while (time.time() - start) < timeout:

        # Gathering interesting inputs
        if coverage_testing:
            print_msg("Coverage based fuzzing")
            method = "coverage"
            execs = 0

            while len(interesting_inputs) < kwargs["interesting_files_limit"] and \
                    execs < kwargs["execs"]:

                current_input = choose_parent(parents_fitness_values)
                mutations = fuzz(current_input["path"],
                                 current_input["history"], max_bytes, fuzz_stats,
                                 output_dir, fuzzing_methods, kwargs["mut_count_strategy"])

                for i in range(len(mutations)):

                    try:
                        # testing for coverage
                        result = testing(method, cmd, args, mutations[i], collector,
                                         postprocessor, minor_version_list, base_cov=base_cov,
                                         source_files=source_files, gcov_version=gcov_version,
                                         gcov_files=gcov_files, **kwargs)
                    except subprocess.CalledProcessError:
                        move_mutation_to(mutations[i]["path"], faults_dir)
                        continue
                    except subprocess.TimeoutExpired:
                        print("Timeout ({}s) reached when testing. See {}.".format(
                            kwargs["hang_timeout"], hangs_dir))
                        move_mutation_to(mutations[i]["path"], hangs_dir)
                        continue

                    execs += 1

                    if result:
                        print("Increase of coverage, cov:",
                              result, mutations[i])
                        parents.append(mutations[i])
                        interesting_inputs.append(mutations[i])
                        rate_parent(parents_fitness_values,
                                    mutations[i], base_cov)
                        fuzz_stats[(mutations[i]["history"])[-1]] += 1
                        fuzz_stats[-1] += 1
                    else:
                        try:
                            os.remove(mutations[i]["path"])
                        except FileNotFoundError:
                            pass
            if interesting_inputs:
                icovr += 0.01
            else:
                if icovr > 0.01:
                    icovr -= 0.01

        else:
            current_input = choose_parent(parents_fitness_values)
            interesting_inputs = fuzz(current_input["path"],
                                      current_input["history"], max_bytes, fuzz_stats,
                                      output_dir, fuzzing_methods, kwargs["mut_count_strategy"])
        method = "perun_based"

        print_msg("Performance testing")

        for i in range(len(interesting_inputs)):
            base_result_profile, base_copy = itertools.tee(
                base_result_profile)  # creates copy of generator

            # testing with perun
            try:
                result = testing(method, cmd, args, interesting_inputs[i], collector,
                                 postprocessor, minor_version_list, base_result=base_copy,
                                 **kwargs)
            except Exception as e:
                print("Executing binary raised an exception: ", e)
                continue
            execs += 1

            if result:
                fuzz_stats[(interesting_inputs[i]["history"])[-1]] += 1
                fuzz_stats[-1] += 1
                if not coverage_testing:
                    parents.append(interesting_inputs[i])
                    rate_parent(parents_fitness_values,
                                interesting_inputs[i])
                final_results.append(interesting_inputs[i])
            else:
                if not coverage_testing:
                    try:
                        os.remove(interesting_inputs[i]["path"])
                    except FileNotFoundError:
                        pass
        # deletes interesting inputs for next run
        del interesting_inputs[:]

    # deletes parents which are not final results, good parents but not causing deg
    del_temp_files(final_results, output_dir)
    for r in final_results:
        print(r["cov"]/base_cov+r["deg_ratio"], r["path"], r["history"])
    # print info about fuzzing
    print_results(time.time()-start, fuzz_stats, fuzzing_methods)
    print_msg("Fuzzing successfully finished.")
