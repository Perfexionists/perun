""" Collects functions for init and common testing for performance change.

In general, this testing is trying to find performance degradation in newly generated target
profile comparing with baseline profile.
"""

import itertools

import perun.check.factory as check
import perun.logic.runner as run
from perun.utils.structs import PerformanceChange

__author__ = 'Matus Liscinsky'

DEGRADATION_RATIO_TRESHOLD = 0


def init(cmd, args, seeds, collector, postprocessor,
         minor_version_list, **kwargs):
    """ Generates a profile for specified command with init seeds, compares each other.

    :param list cmd: list of commands that will be run
    :param list args: lists of additional arguments to the job
    :param list workload: list of workloads
    :param list collector: list of collectors
    :param list postprocessor: list of postprocessors
    :param list minor_version_list: list of MinorVersion info
    :param dict kwargs: dictionary of additional params for postprocessor and collector
    :return generator: copy of baseline profile generator
    """

    # create baseline profile
    base_pg = run.generate_profiles_for(
        [cmd], [args], [seeds[0]["path"]], [collector], postprocessor, minor_version_list, **kwargs
    )

    for file in seeds[1:]:
        # target profile
        target_pg = run.generate_profiles_for(
            [cmd], [args], [file["path"]], [collector], postprocessor, minor_version_list, **kwargs
        )

        # making copies of generators
        base_pg_copy, base_pg = itertools.tee(base_pg)
        target_pg_copy, target_pg = itertools.tee(target_pg)

        try:
            # check
            file["deg_ratio"] = check_for_change(base_pg_copy, target_pg_copy)
            if (file["deg_ratio"] > DEGRADATION_RATIO_TRESHOLD):
                base_pg = target_pg
        except ZeroDivisionError:
            pass
    return base_pg


def test(cmd, args, workload, collector, postprocessor,
         minor_version_list, **kwargs):
    """ Generates a profile for specified command with fuzzed workload, compares with
    baseline profile.

    :param list cmd: list of commands that will be run
    :param list args: lists of additional arguments to the job
    :param list workload: list of workloads
    :param list collector: list of collectors
    :param list postprocessor: list of postprocessors
    :param list minor_version_list: list of MinorVersion info
    :param dict kwargs: dictionary of additional params for postprocessor and collector
    :return bool: True if performance degradation was detected, False otherwise.
    """
    # baseline profile
    base_result = kwargs["base_result"]

    # target profile with a new workload
    target_pg = run.generate_profiles_for(
        [cmd], [args], [workload["path"]], [collector], postprocessor, minor_version_list, **kwargs
    )

    # copy of target profile generator
    target_pg_copy, target_pg = itertools.tee(target_pg)

    try:
        # check
        workload["deg_ratio"] = check_for_change(base_result, target_pg_copy)
        return (workload["deg_ratio"] > DEGRADATION_RATIO_TRESHOLD)
    except (NameError, ZeroDivisionError):
        return False

def check_for_change(base_pg, target_pg):
    for base_prof, target_prof in zip(base_pg, target_pg):
        checks = 0
        degs = 0
        for perf_change in check.degradation_between_profiles(base_prof[1], target_prof[1]):
            checks += 1
            print(perf_change.result)
            if(perf_change.result == PerformanceChange.Degradation):
                degs += 1
    return degs/checks