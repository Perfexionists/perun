"""Collection of global methods for fuzz testing."""

from __future__ import annotations

# Standard Imports
import copy
import filecmp
import itertools
import os
import signal
import sys
import threading
import time
from subprocess import CalledProcessError, TimeoutExpired
from typing import Optional, Any, cast, TYPE_CHECKING, Iterable
from uuid import uuid4

# Third-Party Imports
import numpy as np
import tabulate

# Perun Imports
from perun.fuzz import interpret, filesystem, filetype, randomizer
from perun.fuzz.structs import (
    Mutation,
    FuzzingConfiguration,
    FuzzingProgress,
    FuzzingStats,
    RuleSet,
    TimeSeries,
)
from perun.utils import log
from perun.utils.exceptions import SuppressedExceptions
import perun.fuzz.evaluate.by_perun as evaluate_workloads_by_perun
import perun.fuzz.evaluate.by_coverage as evaluate_workloads_by_coverage
from perun.deltadebugging.factory import delta_debugging_algorithm

if TYPE_CHECKING:
    import types
    from perun.profile.factory import Profile
    from perun.utils.structs.common_structs import Executable, MinorVersion, CollectStatus, Job

# to ignore numpy division warnings
np.seterr(divide="ignore", invalid="ignore")

FP_ALLOWED_ERROR = 0.00001
MAX_FILES_PER_RULE = 100
SAMPLING = 1.0


def compute_safe_ratio(lhs: float, rhs: float) -> float:
    """Computes safely the ratio between lhs and rhs

    In case the @p rhs is equal to zero, then the ratio is approximated

    :param lhs: statistic of method
    :param rhs: overall statistic
    :return: probability for applying
    """
    try:
        return 0.1 if (lhs / rhs < 0.1) else lhs / rhs
    except ZeroDivisionError:
        return 1.0


def get_max_size(
    seeds: list[Mutation],
    max_size: Optional[int],
    max_size_ratio: Optional[float],
    max_size_gain: int,
) -> int:
    """Finds out max size among the sample files and compare it to specified
    max size of mutated file.

    :param seeds: list of paths to sample files and their fuzz history
    :param max_size: user defined max size of mutated file
    :param max_size_ratio: size specified by percentage
    :param max_size_gain: size to adjunct to max
    :return: `max_size` if defined, otherwise value depending on adjusting method
                 (percentage portion, adding constant size)
    """
    # gets the largest seed's size
    seed_max = max(os.path.getsize(seed.path) for seed in seeds)

    # --max option was not specified
    if max_size is None:
        if max_size_ratio is not None:
            return int(seed_max * max_size_ratio)  # percentual adjusting
        else:
            return seed_max + max_size_gain  # adjusting by size(B)

    if seed_max >= max_size:
        log.warn("Warning: Specified max size is smaller than the largest workload.")
    return max_size


def strategy_to_generation_repeats(strategy: str, rule_set: RuleSet, index: int) -> int:
    """Function decides how many workloads will be generated using certain fuzz method.

    Strategies:
        - "unitary" - always 1
        - "proportional" - depends on how many degradations was caused by this method
        - "probabilistic" - depends on ratio between: num of degradations caused by this method and
                            num of all degradations yet
        - "mixed" - mixed "proportional" and "probabilistic" strategy

    :param strategy: determines which strategy for deciding will be used
    :param rule_set: stats of fuzz methods
    :param index: index in list `fuzz_stats` corresponding to stats of actual method
    :return: number of generated mutations for rule
    """
    if strategy == "proportional":
        return min(int(rule_set.hits[index]) + 1, MAX_FILES_PER_RULE)
    elif strategy == "probabilistic":
        ratio = compute_safe_ratio(rule_set.hits[index], rule_set.hits[-1])
        rand = randomizer.rand_from_range(0, 10) / 10
        return 1 if rand <= ratio else 0
    elif strategy == "mixed":
        ratio = compute_safe_ratio(rule_set.hits[index], rule_set.hits[-1])
        rand = randomizer.rand_from_range(0, 10) / 10
        return min(int(rule_set.hits[index]) + 1, MAX_FILES_PER_RULE) if rand <= ratio else 0
    else:
        # Default, also holds for strategy == 'unitary'
        return 1


def fuzz(
    parent: Mutation, max_bytes: int, rule_set: RuleSet, config: FuzzingConfiguration
) -> list[Mutation]:
    """Provides fuzzing on workload parent using all the implemented methods.

    Reads the file and store the lines in list. Makes a copy of the list to send it to every
    single function providing one fuzzing method. With every fuzzing method: creates a new file
    with unique name, but with the same extension. It copies the fuzzing history given by
    `fuzz_history`, append the id of used fuzz method and assign it to the new file. If the new file
    would be bigger than specified limit (`max_bytes`), the remainder is cut off.

    :param parent: path of parent workload file, which will be fuzzed
    :param rule_set: stats of fuzzing (mutation) strategies
    :param max_bytes: specify maximum size of created file in bytes
    :param config: configuration of the fuzzing
    :return: list of tuples(new_file, its_fuzzing_history)
    """

    mutations = []

    is_binary, _ = filetype.get_filetype(parent.path)
    with open(parent.path, "rb") if is_binary else open(parent.path, "r") as fp_in:
        lines = fp_in.readlines()

    # "blank file"
    if len(lines) == 0:
        return []

    # split the file to name and extension
    _, file = os.path.split(parent.path)
    file, ext = os.path.splitext(file)

    # fuzzing
    for i, method in enumerate(rule_set.rules):
        for _ in range(strategy_to_generation_repeats(config.mutations_per_rule, rule_set, i)):
            fuzzed_lines = lines[:]
            # calling specific fuzz method with copy of parent
            method[0](fuzzed_lines)

            # compare, whether new lines are the same
            if lines == fuzzed_lines:
                continue

            # new mutation filename and fuzz history
            mutation_name = file.split("-")[0] + "-" + str(uuid4().hex) + ext
            filename = os.path.join(config.output_dir, mutation_name)
            new_fh = copy.copy(parent.history)
            new_fh.append(i)

            predecessor = parent.predecessor or parent
            mutations.append(Mutation(filename, new_fh, predecessor))

            if is_binary:
                with open(filename, "wb") as bp_out:
                    # Note: At this point, we know that fuzzed_lines is `list[bytes]` since
                    # `is_binary == True`
                    bp_out.write((b"".join(cast(list[bytes], fuzzed_lines)))[:max_bytes])
            else:
                with open(filename, "w") as fp_out:
                    # Note: At this point, we know, that fuzzed_lines is `list[str]` since
                    # `is_binary == False`
                    fp_out.write("".join(cast(list[str], fuzzed_lines))[:max_bytes])

    return mutations


def print_legend(rule_set: RuleSet) -> None:
    """Prints stats of each fuzzing method.

    :param rule_set: selected fuzzing (mutation) strategies and their stats
    """
    log.minor_info("Statistics of rule set", end="\n\n")
    log.write(
        tabulate.tabulate(
            [[i, rule_set.hits[i], method[1]] for (i, method) in enumerate(rule_set.rules)],
            headers=["id", "Rule Efficiency", "Description"],
        )
    )


def print_results(
    fuzzing_report: FuzzingStats,
    fuzzing_config: FuzzingConfiguration,
    rule_set: RuleSet,
) -> None:
    """Prints results of fuzzing.

    :param fuzzing_report: general information about current fuzzing
    :param fuzzing_config: configuration of the fuzzing
    :param rule_set: selected fuzzing (mutation) strategies and their stats
    """
    log.major_info("Summary of Fuzzing")
    log.minor_status(
        "Fuzzing time", status=f"{fuzzing_report.end_time - fuzzing_report.start_time:.2f}s"
    )
    log.minor_status("Coverage testing", status=f"{fuzzing_config.coverage_testing}")
    log.increase_indent()
    if fuzzing_config.coverage_testing:
        log.minor_status(
            "Program executions for coverage testing", status=f"{fuzzing_report.cov_execs}"
        )
        log.minor_status(
            "Program executions for performance testing", status=f"{fuzzing_report.perun_execs}"
        )
        log.minor_status(
            "Total program tests",
            status=f"{fuzzing_report.perun_execs + fuzzing_report.cov_execs}",
        )
        log.minor_status("Maximum coverage ratio", status=f"{fuzzing_report.max_cov}")
    else:
        log.minor_status(
            "Program executions for performance testing", status=f"{fuzzing_report.perun_execs}"
        )
    log.decrease_indent()
    log.minor_status("Founded degradation mutations", status=f"{fuzzing_report.degradations}")
    log.minor_status("Hangs", status=f"{fuzzing_report.hangs}")
    log.minor_status("Faults", status=f"{fuzzing_report.faults}")
    log.minor_status("Worst-case mutation", status=f"{log.path_style(fuzzing_report.worst_case)}")
    print_legend(rule_set)


def rate_parent(fuzz_progress: FuzzingProgress, mutation: Mutation) -> bool:
    """Rate the `mutation` with fitness function and adds it to list with fitness values.

    :param fuzz_progress: progress of the fuzzing
    :param mutation: path to a file which is classified as mutation
    :return: True if a file is the same as any parent, otherwise False
    """
    increase_cov_rate = mutation.cov / fuzz_progress.base_cov

    fitness_value = increase_cov_rate + mutation.deg_ratio
    mutation.fitness = fitness_value

    # empty list or the value is actually the largest
    if not fuzz_progress.parents or fitness_value >= fuzz_progress.parents[-1].fitness:
        fuzz_progress.parents.append(mutation)
    else:
        for index, parent in enumerate(fuzz_progress.parents):
            if fitness_value <= parent.fitness:
                fuzz_progress.parents.insert(index, mutation)
                return False
            # if the same file was generated before
            elif abs(fitness_value - parent.fitness) <= FP_ALLOWED_ERROR:
                # additional file comparing
                return filecmp.cmp(parent.path, mutation.path, shallow=False)
    return False


def update_parent_rate(parents: list[Mutation], mutation: Mutation) -> None:
    """Update rate of the `parent` according to degradation ratio yielded from perf testing.

    :param parents: sorted list of fitness score of parents
    :param mutation: path to a file which is classified as parent
    """
    index, fitness_value = 0, -1.0
    for index, par_fit_val in enumerate(parents):
        if par_fit_val == mutation:
            fitness_value = par_fit_val.fitness * (1 + mutation.deg_ratio)
            del parents[index]
            break

    # if it is the best rated yet, we save the program from looping
    if fitness_value >= parents[-1].fitness:
        mutation.fitness = fitness_value
        parents.append(mutation)
        return

    for i in range(index, len(parents)):
        if fitness_value <= parents[i].fitness:
            mutation.fitness = fitness_value
            parents.insert(i, mutation)
            break


def choose_parent(parents: list[Mutation], num_intervals: int = 5) -> Mutation:
    """Chooses one of the workload file, that will be fuzzed.

    If number of parents is smaller than intervals, function provides random choice.
    Otherwise, it splits parents to intervals, each interval assigns weight(probability)
    and does weighted-interval selection. Then provides random choice of file from
    selected interval.

    :param parents: list of mutations sorted according to their fitness score
    :param num_intervals: number of intervals to which parents will be split
    :return: absolute path to chosen file
    """
    num_of_parents = len(parents)
    if num_of_parents < num_intervals:
        return randomizer.rand_choice(parents)

    triangle_num = (num_intervals * num_intervals + num_intervals) / 2
    bottom = 0
    thresh = int(num_of_parents / num_intervals)
    top = thresh
    intervals = []
    weights = []

    # creates borders of intervals
    for i in range(num_intervals):
        # remainder
        if num_of_parents - top < thresh:
            top = num_of_parents
        intervals.append((bottom, top))
        weights.append((i + 1) / triangle_num)
        bottom = top
        top += thresh

    # choose an interval
    interval_idx = np.random.choice(range(num_intervals), replace=False, p=weights)
    # choose a parent from the interval
    return randomizer.rand_choice(parents[intervals[interval_idx][0] : intervals[interval_idx][1]])


def save_fuzz_state(time_series: TimeSeries, state: int) -> None:
    """Saves current state of fuzzing for plotting.

    :param time_series: list of data for x-axis (typically time values) and y-axis
    :param state: current value of measured variable
    """
    if len(time_series.y_axis) > 1 and state == time_series.y_axis[-2]:
        time_series.x_axis[-1] += SAMPLING
    else:
        time_series.x_axis.append(time_series.x_axis[-1] + SAMPLING)
        time_series.y_axis.append(state)


def teardown(
    fuzz_progress: FuzzingProgress,
    output_dirs: dict[str, str],
    parents: list[Mutation],
    rule_set: RuleSet,
    config: FuzzingConfiguration,
) -> None:
    """Teardown function at the end of the fuzzing, either by natural rundown of timeout or because
    of unnatural circumstances (e.g. exception)

    :param fuzz_progress: Progress of the fuzzing process
    :param output_dirs: dictionary of output dirs for distinct files
    :param parents: list of parents
    :param rule_set: list of fuzzing methods and their stats
    :param config: configuration of the fuzzing
    """
    log.major_info("Teardown")
    if not config.no_plotting:
        # Plot the results as time series
        interpret.plot_fuzz_time_series(
            fuzz_progress.deg_time_series,
            output_dirs["graphs"] + "/degradations_ts.pdf",
            "Fuzzing in time",
            "time (s)",
            "degradations",
        )
        log.minor_success(f"Plotting {log.highlight('degradations')} in time graph")
        if config.coverage_testing:
            interpret.plot_fuzz_time_series(
                fuzz_progress.cov_time_series,
                output_dirs["graphs"] + "/coverage_ts.pdf",
                "Max path during fuzzing",
                "time (s)",
                "executed lines ratio",
            )
            log.minor_success(f"Plotting {log.highlight('coverage')} in time graph")
    # Plot the differences between seeds and inferred mutation
    interpret.files_diff(fuzz_progress, output_dirs["diffs"])
    # Save log files
    interpret.save_log_files(output_dirs["logs"], fuzz_progress)
    # Clean-up remaining mutations
    filesystem.del_temp_files(parents, fuzz_progress, config.output_dir)

    fuzz_progress.stats.end_time = time.time()
    fuzz_progress.stats.worst_case = fuzz_progress.parents[-1].path
    print_results(fuzz_progress.stats, config, rule_set)
    sys.exit(0)


def process_successful_mutation(
    executable: Executable,
    mutation: Mutation,
    collector: str,
    postprocessor: list[str],
    minor_version_list: list[MinorVersion],
    parents: list[Mutation],
    fuzz_progress: FuzzingProgress,
    rule_set: RuleSet,
    config: FuzzingConfiguration,
    base_result_profile: Iterable[tuple[CollectStatus, Profile, Job]],
    **kwargs: Any,
) -> None:
    """If the @p mutation is successful during the evaluation, we update the parent queue
    @p parents, as well as statistics for given rule in rule_set and stats stored in fuzzing
    progress.

    :param executable: tested executable
    :param collector: collector used to collect profiling data
    :param postprocessor: list of postprocessors, which are run after collection
    :param minor_version_list: list of minor version for which we are collecting
    :param mutation: successfully evaluated mutation
    :param fuzz_progress: collective state of fuzzing
    :param parents: list of parents, i.e. mutations which will be further mutated
    :param rule_set: set of applied rules
    :param config: configuration of the fuzzing
    :param baseline_profile: baseline against which we are checking the degradation
    :param kwargs: dictionary of additional params for postprocessor and collector
    """
    kwargs["mutation"] = mutation
    kwargs["collector"] = collector
    kwargs["postprocessor"] = postprocessor
    kwargs["minor_version_list"] = minor_version_list
    kwargs["base_result"] = base_result_profile
    delta_debugging_algorithm(executable, True, **kwargs)
    rule_set.hits[mutation.history[-1]] += 1
    rule_set.hits[-1] += 1
    # without cov testing we firstly rate the new parents here
    if not config.coverage_testing:
        parents.append(mutation)
        rate_parent(fuzz_progress, mutation)
    # for only updating the parent rate
    else:
        update_parent_rate(fuzz_progress.parents, mutation)

    # appending to final results
    fuzz_progress.final_results.append(mutation)
    fuzz_progress.stats.degradations += 1


def save_state(fuzz_progress: FuzzingProgress) -> None:
    """Saves the state of the fuzzing at given time and schedules next save after SAMPLING time

    :param fuzz_progress:
    """
    save_fuzz_state(fuzz_progress.deg_time_series, fuzz_progress.stats.degradations)
    save_fuzz_state(fuzz_progress.cov_time_series, fuzz_progress.stats.max_cov)

    timer = threading.Timer(
        SAMPLING,
        lambda: save_state(fuzz_progress),
    )
    timer.daemon = True
    timer.start()


def perform_baseline_coverage_testing(
    executable: Executable, parents: list[Mutation], config: FuzzingConfiguration
) -> int:
    """Performs the baseline testing for the coverage

    :param executable: tested executable
    :param parents: list of parents
    :param config: configuration of the fuzzing process
    :return: base coverage of parents
    """
    base_cov = 0
    try:
        # Note that evaluate workloads modifies config as a side effect
        base_cov = evaluate_workloads_by_coverage.baseline_testing(executable, parents, config)
        log.minor_success("Coverage-based testing on parent seeds.")
    except TimeoutExpired:
        log.minor_fail("Coverage-based testing on parent seeds.")
        log.error(
            f"Timeout ({config.hang_timeout}s) reached when testing with initial files. "
            f"Adjust hang timeout using option --hang-timeout, resp. -h."
        )
    return base_cov


@log.print_elapsed_time
def run_fuzzing_for_command(
    executable: Executable,
    input_sample: list[str],
    collector: str,
    postprocessor: list[str],
    minor_version_list: list[MinorVersion],
    **kwargs: Any,
) -> None:
    """Runs fuzzing for a command w.r.t initial set of workloads

    :param executable: called command with arguments
    :param input_sample: initial sample of workloads for fuzzing
    :param collector: collector used to collect profiling data
    :param postprocessor: list of postprocessors, which are run after collection
    :param minor_version_list: list of minor version for which we are collecting
    :param kwargs: rest of the keyword arguments
    """
    log.major_info("Fuzzing")

    # Initialization
    fuzz_progress = FuzzingProgress()
    config = FuzzingConfiguration(**kwargs)

    output_dirs = filesystem.make_output_dirs(config.output_dir)

    # getting workload corpus
    parents = filesystem.get_corpus(input_sample, config.workloads_filter)
    # choosing appropriate fuzzing methods
    rule_set = filetype.choose_ruleset(parents[0].path, config.regex_rules)

    # getting max size for generated mutations
    max_bytes = get_max_size(parents, config.max_size, config.max_size_ratio, config.max_size_gain)

    # Init coverage testing with seeds
    if config.coverage_testing:
        fuzz_progress.base_cov = perform_baseline_coverage_testing(executable, parents, config)

    # No gcno files were found, no coverage testing
    if not fuzz_progress.base_cov:
        fuzz_progress.base_cov = 1  # avoiding possible further zero division
        config.coverage_testing = False
        log.warn("No .gcno files were found.")

    # Init performance testing with seeds
    base_result_profile = evaluate_workloads_by_perun.baseline_testing(
        executable, parents, collector, postprocessor, minor_version_list, **kwargs
    )
    log.minor_success("Perun-based testing on parent seeds")

    log.minor_info("Rating parents")
    # Rate seeds
    log.increase_indent()
    for parent_seed in parents:
        rate_parent(fuzz_progress, parent_seed)
        log.minor_status(f"{log.path_style(parent_seed.path)}", status=f"{parent_seed.fitness}")
    log.decrease_indent()

    save_state(fuzz_progress)
    fuzz_progress.stats.start_time = time.time()

    # SIGINT (CTRL-C) signal handler
    def signal_handler(sig: int, _: Optional[types.FrameType]) -> None:
        log.warn(f"Fuzzing process interrupted by signal {sig}...")
        teardown(fuzz_progress, output_dirs, parents, rule_set, config)

    signal.signal(signal.SIGINT, signal_handler)

    # MAIN LOOP
    while (time.time() - fuzz_progress.stats.start_time) < config.timeout:
        # Gathering interesting workloads
        if config.coverage_testing:
            execs = config.exec_limit

            while len(fuzz_progress.interesting_workloads) < config.precollect_limit and execs > 0:
                current_workload = choose_parent(fuzz_progress.parents)
                mutations = fuzz(current_workload, max_bytes, rule_set, config)

                for mutation in mutations:
                    try:
                        execs -= 1
                        fuzz_progress.stats.cov_execs += 1
                        # testing for coverage
                        result = evaluate_workloads_by_coverage.target_testing(
                            executable,
                            mutation,
                            config,
                            current_workload,
                            fuzz_progress,
                            **kwargs,
                        )
                    # error occurred
                    except CalledProcessError:
                        fuzz_progress.stats.faults += 1
                        mutation.path = filesystem.move_file_to(
                            mutation.path, output_dirs["faults"]
                        )
                        fuzz_progress.faults.append(mutation)
                        result = True
                    # timeout expired
                    except TimeoutExpired:
                        fuzz_progress.stats.hangs += 1
                        log.warn(
                            f"Timeout ({config.hang_timeout}s) reached when testing. See {output_dirs['hangs']}."
                        )
                        mutation.path = filesystem.move_file_to(mutation.path, output_dirs["hangs"])
                        fuzz_progress.hangs.append(mutation)
                        continue

                    # if successful mutation
                    if result and not rate_parent(fuzz_progress, mutation):
                        fuzz_progress.update_max_coverage()
                        parents.append(mutation)
                        fuzz_progress.interesting_workloads.append(mutation)
                        rule_set.hits[mutation.history[-1]] += 1
                        rule_set.hits[-1] += 1
                    # not successful mutation or the same file as previously generated
                    else:
                        os.remove(mutation.path)

            # adapting increase coverage ratio
            config.refine_coverage_rate(fuzz_progress.interesting_workloads)
            log.minor_success("Gathering using coverage-based testing")

        # not coverage testing, only performance testing
        else:
            current_workload = choose_parent(fuzz_progress.parents)
            fuzz_progress.interesting_workloads = fuzz(
                current_workload, max_bytes, rule_set, config
            )
            log.minor_success("Gathering using Perun-based testing")

        log.minor_info("Evaluating mutations")
        log.increase_indent()
        for mutation in fuzz_progress.interesting_workloads:
            # creates copy of generator
            base_result_profile, base_copy = itertools.tee(base_result_profile)

            # testing with perun
            successful_result = False
            # We suppress the exceptions -> we will simply not have collected the data
            with SuppressedExceptions(Exception):
                fuzz_progress.stats.perun_execs += 1
                successful_result = evaluate_workloads_by_perun.target_testing(
                    executable,
                    mutation,
                    collector,
                    postprocessor,
                    minor_version_list,
                    base_copy,
                    **kwargs,
                )
                if successful_result:
                    process_successful_mutation(
                        executable,
                        mutation,
                        collector,
                        postprocessor,
                        minor_version_list,
                        parents,
                        fuzz_progress,
                        rule_set,
                        config,
                        base_copy,
                        **kwargs,
                    )

            log.minor_status(f"{mutation.path}", status=f"{mutation.fitness}")
            # in case of testing with coverage, parent will not be removed but used for mutation
            if not successful_result and not config.coverage_testing:
                os.remove(mutation.path)
        log.decrease_indent()

        # deletes interesting workloads for next run
        del fuzz_progress.interesting_workloads[:]

    # get end time
    fuzz_progress.stats.end_time = time.time()

    teardown(fuzz_progress, output_dirs, parents, rule_set, config)
