"""Collection of functions for running collectors and postprocessors"""

import perun.utils as utils
import perun.utils.log as perun_log

from perun.utils import get_module
from perun.utils.helpers import COLLECT_PHASE_COLLECT, COLLECT_PHASE_POSTPROCESS, \
    CollectStatus, PostprocessStatus
__author__ = 'Tomas Fiedor'


def is_status_ok(returned_status, expected_status):
    """Helper function for checking the status of the runners.

    Since authors of the collectors and processors may not behave well, we need
    this function to check either for the expected value of the enum (if they return int
    instead of enum) or enum if they return politely enum.

    Arguments:
        returned_status(int or Enum): status returned from the collector
        expected_status(Enum): expected status

    Returns:
        bool: true if the status was 0, CollectStatus.OK or PostprocessStatus.OK
    """
    return returned_status == expected_status or returned_status == expected_status.value


def run_all_phases_for(runner, runner_type, runner_params):
    """Run all of the phases (before, runner_type, after) for given params.

    Runs three of the phases before, runner_type and after for the given runner params
    with runner (collector or postprocesser). During each phase, either error occurs,
    with given error message or updated params, that are used in next phase. This
    way the phases can pass the information.

    Returns the computed profile

    Arguments:
        runner(module): module that is going to be runned
        runner_type(str): string type of the runner (either collector or postprocessor)
        runner_params(dict): dictionary of arguments for runner
    """
    assert runner_type in ['collector', 'postprocessor']
    ok_status = CollectStatus.OK if runner_type == 'collector' else PostprocessStatus.OK
    error_status = CollectStatus.ERROR if runner_type == 'collector' else PostprocessStatus.ERROR
    runner_verb = runner_type[:-2]

    for phase in ['before', runner_verb, 'after']:
        phase_function = getattr(runner, phase, None)
        if phase_function:
            ret_val, ret_msg, updated_params = phase_function(**runner_params)
            runner_params.update(updated_params or {})
            if not is_status_ok(ret_val, ok_status):
                return error_status, "error while {}{} phase: {}".format(
                    phase, ("_" + runner_verb)*(phase != runner_verb), ret_msg
                ), {}
        elif phase == runner_verb:
            return error_status, "missing {}() function for {}".format(
                runner_verb, runner.__name__
            ), {}

    # Return the processed profile
    if 'profile' not in runner_params.keys():
        return error_status, "missing generated profile for {} {}".format(
            runner_type, runner.__name__
        ), {}
    return ok_status, "", runner_params['profile']


def run_collector(collector, job):
    """Run the job of collector of the given name.

    Tries to look up the module containing the collector specified by the
    collector name, and then runs it with the parameters and returns collected profile.

    Arguments:
        collector(Unit): object representing the collector
        job(Job): additional information about the running job

    Returns:
        (int, dict): status of the collection, generated profile
    """
    perun_log.print_current_phase(
        "Collecting data by {}", collector.name, COLLECT_PHASE_COLLECT
    )

    try:
        collector_module = get_module('perun.collect.{0}.run'.format(collector.name))
    except ImportError:
        return CollectStatus.ERROR, "{} does not exist".format(collector.name), {}

    # First init the collector by running the before phases (if it has)
    job_params = utils.merge_dictionaries(job._asdict(), collector.params)
    collection_status, collection_msg, profile \
        = run_all_phases_for(collector_module, 'collector', job_params)

    if collection_status != CollectStatus.OK:
        perun_log.error(collection_msg, recoverable=True)
    else:
        print("Successfully collected data from {}".format(job.cmd))

    return collection_status, profile


def run_postprocessor(postprocessor, job, prof):
    """Run the job of postprocess of the given name.

    Tries to look up the module containing the postprocessor specified by the
    postprocessor name, and then runs it with the parameters and returns processed
    profile.

    Arguments:
        postprocessor(Unit): dictionary representing the postprocessor
        job(Job): additional information about the running job
        prof(dict): dictionary with profile

    Returns:
        (int, dict): status of the collection, postprocessed profile
    """
    perun_log.print_current_phase(
        "Postprocessing data with {}", postprocessor.name, COLLECT_PHASE_POSTPROCESS
    )

    try:
        postprocessor_module = get_module('perun.postprocess.{0}.run'.format(postprocessor.name))
    except ImportError:
        return PostprocessStatus.ERROR, "{} does not exist".format(postprocessor.name), {}

    # First init the collector by running the before phases (if it has)
    job_params = utils.merge_dict_range(job._asdict(), {'profile': prof}, postprocessor.params)
    post_status, post_msg, profile \
        = run_all_phases_for(postprocessor_module, 'postprocessor', job_params)

    if post_status != PostprocessStatus.OK:
        perun_log.error(post_msg)
    else:
        print("Successfully postprocessed data by {}".format(postprocessor.name))

    return post_status, profile
