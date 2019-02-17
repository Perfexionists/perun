"""Collection of global methods for fuzz testing"""
__author__ = 'Tomas Fiedor'

import perun.utils.decorators as decorators
import perun.logic.runner as run

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
    for workload in initial_workload:
        run.run_single_job(
            [cmd], [args], workload, [collector], postprocessor, minor_version_list, **kwargs
        )
