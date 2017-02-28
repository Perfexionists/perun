"""Collection of functions for running collectors and postprocessors"""

import termcolor

from perun.utils import get_module
from perun.utils.helpers import CollectStatus, PostprocessStatus, \
    COLLECT_PHASE_ERROR

__author__ = 'Tomas Fiedor'


def run_all_phases_for(runner, runner_type, runner_params):
    """
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
            ret_val, ret_msg = phase_function(**runner_params)
            if ret_val != ok_status:
                print(termcolor.colored("fatal: error while {}{} phase: {}".format(
                    phase, ("_" + runner_verb)*(phase != runner_verb), ret_msg
                ), COLLECT_PHASE_ERROR))
                exit(1)
        elif phase == runner_verb:
            print(termcolor.colored("fatal: missing {}() function for {}".format(
                runner_verb, runner.__name__
            ), COLLECT_PHASE_ERROR))
            exit(1)


def run_collector(collector_name, job):
    """
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
    run_all_phases_for(collector, 'collector', job_params)

    return CollectStatus.OK, "Profile collected"


def run_postprocessor(postprocessor_name, job):
    """
    Arguments:
        postprocessor_name(str): name of the postprocessor that will be run
        job(Job): additional information about the running job

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
    run_all_phases_for(postprocessor, 'postprocessor', job_params)

    return PostprocessStatus.OK, "Profile postprocessed"
