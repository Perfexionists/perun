""" Collects functions for init and common testing for performance change.

In general, this testing is trying to find performance degradation in newly generated target
profile comparing with baseline profile.
"""

import perun.check.factory as check
import perun.logic.runner as run
from perun.utils.structs import PerformanceChange

__author__ = 'Matus Liscinsky'

DEGRADATION_RATIO_TRESHOLD = 0


def baseline_testing(executable, seeds, collector, postprocessor, minor_version_list, **kwargs):
    """ Generates a profile for specified command with init seeds, compares each other.

    :param Executable executable: called command with arguments
    :param list seeds: list of workloads
    :param str collector: list of collectors
    :param list postprocessor: list of postprocessors
    :param list minor_version_list: list of MinorVersion info
    :param dict kwargs: dictionary of additional params for postprocessor and collector
    :return generator: copy of baseline profile generator
    """

    # create baseline profile
    base_pg = list(run.generate_profiles_for(
        [executable.cmd], [executable.args], [seeds[0].path], [collector], postprocessor,
        minor_version_list, **kwargs
    ))

    for file in seeds[1:]:
        # target profile
        target_pg = list(run.generate_profiles_for(
            [executable.cmd], [executable.args], [file.path], [collector], postprocessor,
            minor_version_list, **kwargs
        ))

        file.deg_ratio = check_for_change(base_pg, target_pg)
        if file.deg_ratio > DEGRADATION_RATIO_TRESHOLD:
            base_pg = target_pg
    return base_pg


def target_testing(
        executable, workload, collector, postprocessor, minor_version_list, base_result, **kwargs):
    """ Generates a profile for specified command with fuzzed workload, compares with
    baseline profile.

    :param Executable executable: called command with arguments
    :param Mutation workload: list of workloads
    :param str collector: list of collectors
    :param list postprocessor: list of postprocessors
    :param list minor_version_list: list of MinorVersion info
    :param iterable base_result: list of results for baseline
    :param dict kwargs: dictionary of additional params for postprocessor and collector
    :return bool: True if performance degradation was detected, False otherwise.
    """
    # target profile with a new workload
    target_pg = list(run.generate_profiles_for(
        [executable.cmd], [executable.args], [workload.path], [collector], postprocessor,
        minor_version_list, **kwargs
    ))

    # check
    workload.deg_ratio = check_for_change(base_result, target_pg)
    return workload.deg_ratio > DEGRADATION_RATIO_TRESHOLD


def check_for_change(base_pg, target_pg, method='best-model'):
    """Function that randomly choose an index from list.

    :param generator base_pg: base performance profile generator
    :param generator target_pg: target performance profile generator
    :param method: name of detection models strategy to obtains relevant model kinds

    :return int: ratio between checks and founded degradations
    """
    for base_prof, target_prof in zip(base_pg, target_pg):
        checks = 0
        degs = 0
        for perf_change in check.degradation_between_profiles(base_prof[1], target_prof[1], method):
            checks += 1
            degs += perf_change.result == PerformanceChange.Degradation
        return degs / checks if checks else 0
    return 0
