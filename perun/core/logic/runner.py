"""Collection of functions for running collectors and postprocessors"""

import perun.utils.log as perun_log

from perun.utils import get_module
from perun.utils.helpers import CollectStatus, PostprocessStatus

__author__ = 'Tomas Fiedor'


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
    runner_verb = runner_type[:-2]

    for phase in ['before', runner_verb, 'after']:
        phase_function = getattr(runner, phase, None)
        if phase_function:
            ret_val, ret_msg, updated_params = phase_function(**runner_params)
            runner_params.update(updated_params or {})
            if ret_val != ok_status:
                perun_log.error("error while {}{} phase: {}".format(
                    phase, ("_" + runner_verb)*(phase != runner_verb), ret_msg
                ))
        elif phase == runner_verb:
            perun_log.error("missing {}() function for {}".format(
                runner_verb, runner.__name__
            ))

    # Return the processed profile
    if 'profile' not in runner_params.keys():
        perun_log.error("missing generated profile for {} {}".format(
            runner_type, runner.__name__
        ))
    return runner_params['profile']


def run_collector(collector_name, job):
    """Run the job of colelctor of the given name.

    Tries to look up the module containinig the collector specified by the
    collector name, and then runs it with the parameters and returns collected profile.

    Arguments:
        collector_name(str): name of the called collector
        job(Job): additional information about the running job

    Returns:
        (int, str): status of the collection, string message of the status
    """
    try:
        collector = get_module('.'.join(['perun.collect', collector_name, collector_name]))
    except ImportError:
        return CollectStatus.ERROR, "{} does not exist".format(collector_name)

    # First init the collector by running the before phases (if it has)
    job_params = dict(job._asdict())
    profile = run_all_phases_for(collector, 'collector', job_params)

    return CollectStatus.OK, "Profile collected", profile


def run_postprocessor(postprocessor_name, job, prof):
    """Run the job of postprocess of the given name.

    Tries to look up the module containinig the postprocessor specified by the
    postprocessor name, and then runs it with the parameters and returns processed
    profile.

    Arguments:
        postprocessor_name(str): name of the postprocessor that will be run
        job(Job): additional information about the running job
        prof(dict): dictionary with profile

    Returns:
        (int, str): status of the collection, string message of the status
    """
    try:
        postprocessor = get_module('.'.join([
            'perun.postprocess', postprocessor_name, postprocessor_name
        ]))
    except ImportError:
        return PostprocessStatus.ERROR, "{} does not exist".format(postprocessor_name)

    # First init the collector by running the before phases (if it has)
    job_params = dict(job._asdict())
    job_params.update({'profile': prof})
    profile = run_all_phases_for(postprocessor, 'postprocessor', job_params)

    return PostprocessStatus.OK, "Profile postprocessed", profile
