"""Collection of functions for running collectors and postprocessors"""

from __future__ import annotations

# Standard Imports
from typing import Any, Iterable, TYPE_CHECKING, cast, Callable, overload
import signal
import time
import subprocess

# Third-Party Imports
import click

# Perun Imports
from perun.vcs import vcs_kit
from perun.logic import pcs
from perun.utils import log
from perun.utils.common import common_kit
from perun.utils.exceptions import SignalReceivedException
from perun.utils.external import commands as external_commands
from perun.utils.structs.common_structs import (
    CollectStatus,
    Executable,
    GeneratorSpec,
    HandledSignals,
    Job,
    MinorVersion,
    PostprocessStatus,
    RunnerReport,
    Unit,
)
from perun.workload.singleton_generator import SingletonGenerator
from perun import profile
import perun.workload as workloads

if TYPE_CHECKING:
    import types

    from perun.profile.factory import Profile


def construct_job_matrix(
    cmd: list[str],
    workload: list[str],
    collector: list[str],
    postprocessor: list[str],
    **kwargs: Any,
) -> tuple[dict[str, dict[str, list[Job]]], int]:
    """Constructs the job matrix represented as dictionary.

    Reads the local of the current PCS and constructs the matrix of jobs
    that will be run. Each job consists of command that will be run,
    collector used to collect the data and list of postprocessors to
    alter the output profiles. Inside the dictionary jobs are distributed
    by binaries, then workloads and finally Jobs.

    Returns the job matrix as dictionary of form:
    {
      'cmd1': {
        'workload1': [ Job1, Job2 , ...],
        'workload2': [ Job1, Job2 , ...]
      },
      'cmd2': {
        'workload1': [ Job1, Job2 , ...],
        'workload2': [ Job1, Job2 , ...]
      }
    }

    :param cmd: binary that will be run
    :param workload: list of workloads
    :param collector: list of collectors
    :param postprocessor: list of postprocessors
    :param kwargs: additional parameters issued from the command line
    :return: dict of jobs in form of {cmds: {workloads: {Job}}}, number of jobs
    """

    def construct_unit(unit: str, unit_type: str, **ukwargs: Any) -> Unit:
        """Helper function for constructing the {'name', 'params'} objects for collectors and posts.

        :param unit: name of the unit (collector/postprocessor)
        :param unit_type: name of the unit type (collector or postprocessor)
        :param ukwargs: dictionary of additional parameters
        :return: dictionary of the form {'name', 'params'}
        """
        # Get the dictionaries for from string and from file params obtained from commandline
        unit_param_dict = ukwargs.get(unit_type + "_params", {}).get(unit, {})

        # Construct the object with name and parameters
        return Unit(unit, unit_param_dict)

    # Convert the bare lists of collectors and postprocessors to {'name', 'params'} objects
    collector_pairs = list(map(lambda c: construct_unit(c, "collector", **kwargs), collector))
    posts = list(map(lambda p: construct_unit(p, "postprocessor", **kwargs), postprocessor))

    # Construct the actual job matrix
    matrix = {
        str(b): {
            str(w): [Job(c, posts, Executable(b, w)) for c in collector_pairs] for w in workload
        }
        for b in cmd
    }

    # Count overall number of the jobs:
    number_of_jobs = 0
    for cmd_values in matrix.values():
        for workload_values in cmd_values.values():
            for job in workload_values:
                number_of_jobs += 1 + len(job.postprocessors)

    return matrix, number_of_jobs


def load_job_info_from_config() -> dict[str, Any]:
    """
    :return: dictionary with cmds, args, workloads, collectors and postprocessors
    """
    local_config = pcs.local_config().data

    if "collectors" not in local_config.keys():
        log.error(
            "missing 'collectors' region in the local.yml\n\n"
            "Run `perun config edit` and fix the job matrix in order to collect the data."
            "For more information about job matrix see :doc:`jobs`."
        )
    collectors = local_config["collectors"]
    postprocessors = local_config.get("postprocessors", [])

    if "cmds" not in local_config.keys():
        log.error(
            "missing 'cmds' region in the local.yml\n\n"
            "Run `perun config edit` and fix the job matrix in order to collect the data."
            "For more information about job matrix see :doc:`jobs`."
        )

    info = {
        "cmd": local_config["cmds"],
        "workload": local_config.get("workloads", [""]),
        "postprocessor": [post.get("name", "") for post in postprocessors],
        "collector": [collect.get("name", "") for collect in collectors],
        "collector_params": {
            collect.get("name", ""): collect.get("params", {}) for collect in collectors
        },
        "postprocessor_params": {
            post.get("name", ""): post.get("params", {}) for post in postprocessors
        },
    }

    return info


@overload
def create_empty_pass(
    return_code: CollectStatus,
) -> Callable[[Any], tuple[CollectStatus, str, dict[str, Any]]]:
    """Typing signature for creating empty pass returning CollectStatus"""
    pass


@overload
def create_empty_pass(
    return_code: PostprocessStatus,
) -> Callable[[Any], tuple[PostprocessStatus, str, dict[str, Any]]]:
    """Typing signature for creating empty pass returning PostProcessStatus"""
    pass


def create_empty_pass(
    return_code: CollectStatus | PostprocessStatus,
) -> Callable[..., tuple[CollectStatus | PostprocessStatus, str, dict[str, Any]]]:
    """Returns a function which will do nothing

    This is used to handle collectors and postprocessors that do not have before or after phases.

    :param return_code: either CollectStatus.OK or PostprocessorStatus.OK
    :return: function that does nothing
    """

    def empty_pass(
        **kwargs: Any,
    ) -> tuple[CollectStatus | PostprocessStatus, str, dict[str, Any]]:
        """Empty collection or postprocessing phase, doing nothing

        :param kwargs: arguments of the phase
        :return: return code, empty return message, non-modified arguments
        """
        return return_code, "", kwargs

    return empty_pass


def run_phase_function(report: RunnerReport, phase: str) -> None:
    """Runs the concrete phase function of the runner (collector or postprocessor)

    If the runner does not provide the function for phase then empty pass is created and
    nothing is returned. If any exception occurs, or if the phase return non-zero status,
    then the overall report ends with Error.

    :param report: collective report about the run of the phase
    :param phase: name of the phase/function that is run
    """
    phase_function: Callable[..., tuple[CollectStatus | PostprocessStatus, str, dict[str, Any]]] = (
        getattr(report.runner, phase, create_empty_pass(report.ok_status))
    )
    runner_verb = report.runner_type[:-2]
    report.phase = phase
    try:
        phase_result = phase_function(**report.kwargs)
        report.update_from(*phase_result)
    # We safely catch all the exceptions
    except Exception as exc:
        report.status = report.error_status
        report.exception = exc
        report.message = (
            f"error while {phase}{('_' + runner_verb) * (phase != runner_verb)} phase: {exc}"
        )


def check_integrity_of_runner(
    runner: types.ModuleType, runner_type: str, report: RunnerReport
) -> None:
    """Checks that the runner has basic requirements of collectors and postprocessor.

    This function warns user that some expected conventions were not fulfilled. In particular,
    this checks that the runners return the dictionary with 'profile' keyword, i.e. it does
    something with profile. Second it checks that the runner has corresponding collect or
    postprocess functions (though theoretically one can have only before and after phases)

    :param runner: module of the runner (postprocessor or collector)
    :param runner_type: string name of the runner (the run function is derived from this)
    :param report: report of the collection phase
    """
    runner_name = runner.__name__.split(".")[-2]
    if "profile" not in report.kwargs.keys() and report.is_ok():
        log.warn(f"{runner_name} {runner_type} does not return any profile")

    runner_verb = runner_type[:-2]
    if not getattr(runner, runner_verb, None):
        log.warn(f"{runner_name} is missing {runner_verb}() function")


def runner_teardown_handler(status_report: RunnerReport, **kwargs: Any) -> None:
    """The teardown callback used in the signal handler.

    :param status_report: the collection report object
    :param kwargs: additional parameters as supplied by the HandledSignals CM
    """
    exc = kwargs["exc_val"]
    if isinstance(exc, SignalReceivedException):
        log.warn(f"Received signal: {exc.signum}, safe termination in process")
        status_report.status = status_report.error_status
        status_report.exception = exc
        status_report.message = f"received signal during teardown() phase: {exc.signum} ({exc})"
    run_phase_function(status_report, "teardown")


def runner_signal_handler(signum: int, frame: types.FrameType | None) -> None:
    """Custom signal handler that blocks all the handled signals until the __exit__ sentinel of
    the CM is reached.

    :param signum: a representation of the encountered signal
    :param frame: a frame / stack trace object
    """
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    signal.signal(signal.SIGQUIT, signal.SIG_IGN)
    raise SignalReceivedException(signum, frame)


def run_all_phases_for(
    runner: types.ModuleType, runner_type: str, runner_params: dict[str, Any]
) -> tuple[RunnerReport, dict[str, Any]]:
    """Run all the phases (before, runner_type, after) for given params.

    Runs three of the phases before, runner_type and after for the given runner params
    with runner (collector or postprocessor). During each phase, either error occurs,
    with given error message or updated params, that are used in next phase. This
    way the phases can pass the information.

    Returns the computed profile

    :param runner: module that is going to be run
    :param runner_type: string type of the runner (either collector or postprocessor)
    :param runner_params: dictionary of arguments for runner
    :return: report about the run phase adn profile
    """
    import perun.collect.trace.optimizations.optimization as optimizations

    runner_verb = runner_type[:-2]
    # Create immutable list of resource that should hold even in case of problems
    runner_params["opened_resources"] = []

    report = RunnerReport(runner, runner_type, runner_params)

    with HandledSignals(
        signal.SIGINT,
        signal.SIGTERM,
        signal.SIGQUIT,
        handler=runner_signal_handler,
        callback=runner_teardown_handler,
        callback_args=[report],
    ):
        for phase in ["before", runner_verb, "after"]:
            run_phase_function(report, phase)

            if not report.is_ok():
                break

            # Run the optimizations
            optimizations.optimize(runner_type, phase, **report.kwargs)

    check_integrity_of_runner(runner, runner_type, report)

    return report, report.kwargs.get("profile", {})


@log.print_elapsed_time
def run_collector(collector: Unit, job: Job) -> tuple[CollectStatus, dict[str, Any]]:
    """Run the job of collector of the given name.

    Tries to look up the module containing the collector specified by the
    collector name, and then runs it with the parameters and returns collected profile.

    :param collector: object representing the collector
    :param job: additional information about the running job
    :return: status of the collection, generated profile
    """
    try:
        collector_module = common_kit.get_module(f"perun.collect.{collector.name}.run")
    except ImportError:
        log.error_msg(f"{collector.name} collector does not exist")
        return CollectStatus.ERROR, {}

    # First init the collector by running the before phases (if it has)
    job_params = common_kit.merge_dictionaries(job._asdict(), collector.params)
    collection_report, prof = run_all_phases_for(collector_module, "collector", job_params)

    if not collection_report.is_ok():
        log.minor_fail(f"Collecting from {log.cmd_style(job.executable.cmd)}")
        log.error_msg(
            f"while collecting by {collector.name}: {collection_report.message}",
            raised_exception=collection_report.exception,
        )
    else:
        log.minor_success(
            f"Collecting by {log.highlight(collector.name)} from {log.cmd_style(str(job.executable))}",
        )

    return cast(CollectStatus, collection_report.status), prof


def run_collector_from_cli_context(
    ctx: click.Context, collector_name: str, collector_params: dict[str, Any]
) -> None:
    """Runs the collector according to the given cli context.

    This is used as a wrapper for calls from various collector modules. This was extracted,
    to minimize the needed input of new potential collectors.

    :param ctx: click context containing arguments obtained by 'perun collect' command
    :param collector_name: name of the collector that will be run
    :param collector_params: dictionary with collector params
    """
    cmd, workload = ctx.obj["cmd"], ctx.obj["workload"]
    minor_versions = ctx.obj["minor_version_list"]
    collector_params.update(ctx.obj["params"])
    run_params = {
        "collector_params": {collector_name: collector_params},
        "profile_path": ctx.obj["profile_path"],
        "profile_label": ctx.obj["profile_label"],
    }
    collect_status = run_single_job(
        cmd, workload, [collector_name], [], minor_versions, **run_params
    )
    if collect_status != CollectStatus.OK:
        log.error("collection of profiles was unsuccessful")


@log.print_elapsed_time
def run_postprocessor(
    postprocessor: Unit, job: Job, prof: dict[str, Any]
) -> tuple[PostprocessStatus, dict[str, Any]]:
    """Run the job of postprocess of the given name.

    Tries to look up the module containing the postprocessor specified by the
    postprocessor name, and then runs it with the parameters and returns processed
    profile.

    :param postprocessor: dictionary representing the postprocessor
    :param job: additional information about the running job
    :param prof: dictionary with profile
    :return: status of the collection, postprocessed profile
    """
    try:
        postprocessor_module = common_kit.get_module(f"perun.postprocess.{postprocessor.name}.run")
    except ImportError:
        log.error_msg(f"{postprocessor.name} postprocessor does not exist")
        return PostprocessStatus.ERROR, {}

    # First init the collector by running the before phases (if it has)
    job_params = common_kit.merge_dictionaries(
        job._asdict(), {"profile": prof}, postprocessor.params
    )
    postprocess_report, prof = run_all_phases_for(postprocessor_module, "postprocessor", job_params)

    if not postprocess_report.is_ok() or not prof:
        log.minor_fail(f"Postprocessing by {postprocessor.name}")
        log.error_msg(f"while postprocessing by {postprocessor.name}: {postprocess_report.message}")
    else:
        log.minor_success(f"Postprocessing by {postprocessor.name}")

    return cast(PostprocessStatus, postprocess_report.status), prof


def run_postprocessor_on_profile(
    prof: Profile,
    postprocessor_name: str,
    postprocessor_params: dict[str, Any],
    skip_store: bool = False,
) -> tuple[PostprocessStatus, Profile]:
    """Run the job of the postprocessor according to the given profile.

    First extracts the information from the profile in order to construct the job,
    then runs the given postprocessor that is appended to the list of postprocessors
    of the profile, and the postprocessed profile is stored in the pending jobs.

    :param prof: dictionary with profile information
    :param postprocessor_name: name of the postprocessor that we are using
    :param postprocessor_params: parameters for the postprocessor
    :param skip_store: if set to true, then the profile will not be stored
    :return: status how the postprocessing went and the postprocessed
        profile
    """
    profile_job = profile.extract_job_from_profile(prof)
    postprocessor_unit = Unit(postprocessor_name, postprocessor_params)
    profile_job.postprocessors.append(postprocessor_unit)

    p_status, processed_profile = run_postprocessor(postprocessor_unit, profile_job, prof)
    if p_status == PostprocessStatus.OK and prof and not skip_store:
        profile.save_profile(
            profile.finalize_profile_for_job(prof, profile_job, prof.get("header", {}).get("label"))
        )
    return p_status, processed_profile


def run_prephase_commands(phase: str) -> None:
    """Runs the phase before the actual collection of the methods

    This command first retrieves the phase from the configuration, and runs
    safely all the commands specified in the list.

    The phase is specified in :doc:`config` by keys specified in section
    :cunit:`execute`.

    :param phase: name of the phase commands
    """
    phase_key = ".".join(["execute", phase]) if not phase.startswith("execute") else phase
    cmds = pcs.local_config().safe_get(phase_key, [])
    if cmds:
        log.major_info("Prerun")
        try:
            before = time.time()
            external_commands.run_safely_list_of_commands(cmds)
            elapsed = time.time() - before
            log.minor_status("Elapsed time", status=f"{elapsed:0.2f}s")
        except subprocess.CalledProcessError as exception:
            error_command = str(exception.cmd)
            error_code = exception.returncode
            error_output = exception.output
            log.error(
                f"error during {phase} phase while running '{error_command}';"
                f" exited with: {error_code} ({error_output})"
            )


def generate_jobs_on_current_working_dir(
    job_matrix: dict[str, dict[str, list[Job]]], number_of_jobs: int
) -> Iterable[tuple[CollectStatus, Profile, Job]]:
    """Runs the batch of jobs on current state of the VCS.

    This function expects no changes not commited in the repo, it excepts correct version
    checked out and just runs the matrix.

    :param job_matrix: dictionary with jobs that will be run
    :param number_of_jobs: number of jobs that will be run
    :return: status, generated profile, and associated job
    """
    workload_generators_specs: dict[str, GeneratorSpec] = workloads.load_generator_specifications()

    log.print_job_progress.current_job = 1
    collective_status = CollectStatus.OK

    log.major_info("Running Jobs")
    log.increase_indent()
    job_counter = 1
    for job_cmd, workloads_per_cmd in log.progress(job_matrix.items(), "Running Jobs"):
        for workload, jobs_per_workload in workloads_per_cmd.items():
            # Prepare the specification
            generator_spec = workload_generators_specs.get(
                workload, GeneratorSpec(SingletonGenerator, {"value": workload})
            )
            generator, params = generator_spec.constructor, generator_spec.params
            for job in jobs_per_workload:
                log.major_info(f"Job {job_counter} Overview")
                log.minor_status("Command", status=log.cmd_style(job_cmd))
                log.minor_status("Workload", status=log.highlight(workload))
                log.minor_status("Collector", status=log.highlight(job.collector.name))
                if job.postprocessors:
                    log.minor_status(
                        "Postprocessors",
                        status=log.highlight(", ".join(post.name for post in job.postprocessors)),
                    )

                for c_status, prof in generator(job, **params).generate(run_collector):
                    # Run the collector and check if the profile was successfully collected
                    # In case, the status was not OK, then we skip the postprocessing
                    if c_status != CollectStatus.OK or not prof:
                        collective_status = CollectStatus.ERROR
                        continue

                    # Temporary nasty hack
                    prof = profile.finalize_profile_for_job(prof, job)

                    for postprocessor in job.postprocessors:
                        log.print_job_progress(number_of_jobs)
                        # Run postprocess and check if the profile was successfully postprocessed
                        p_status, prof = run_postprocessor(postprocessor, job, prof)
                        if p_status != PostprocessStatus.OK or not prof:
                            collective_status = CollectStatus.ERROR
                            break
                    else:
                        # Store the computed profile inside the job directory
                        yield collective_status, prof, job
                job_counter += 1

    log.decrease_indent()


def generate_jobs(
    minor_version_list: list[MinorVersion],
    job_matrix: dict[str, dict[str, list[Job]]],
    number_of_jobs: int,
) -> Iterable[tuple[CollectStatus, Profile, Job]]:
    """
    :param minor_version_list: list of MinorVersion info
    :param job_matrix: dictionary with jobs that will be run
    :param number_of_jobs: number of jobs that will be run
    """
    with vcs_kit.CleanState():
        for minor_version in minor_version_list:
            pcs.vcs().checkout(minor_version.checksum)
            run_prephase_commands("pre_run")
            yield from generate_jobs_on_current_working_dir(job_matrix, number_of_jobs)


def generate_jobs_with_history(
    minor_version_list: list[MinorVersion],
    job_matrix: dict[str, dict[str, list[Job]]],
    number_of_jobs: int,
) -> Iterable[tuple[CollectStatus, Profile, Job]]:
    """
    :param minor_version_list: list of MinorVersion info
    :param job_matrix: dictionary with jobs that will be run
    :param number_of_jobs: number of jobs that will be run
    """
    with log.History(minor_version_list[0].checksum) as history:
        with vcs_kit.CleanState():
            for minor_version in minor_version_list:
                history.progress_to_next_minor_version(minor_version)
                log.newline()
                history.finish_minor_version(minor_version, [])
                pcs.vcs().checkout(minor_version.checksum)
                run_prephase_commands("pre_run")
                yield from generate_jobs_on_current_working_dir(job_matrix, number_of_jobs)
                log.newline()
                history.flush(with_border=True)


def generate_profiles_for(
    cmd: list[str],
    workload: list[str],
    collector: list[str],
    postprocessor: list[str],
    minor_version_list: list[MinorVersion],
    **kwargs: Any,
) -> Iterable[tuple[CollectStatus, Profile, Job]]:
    """Helper generator, that takes job specification and continuously generates profiles

    This is mainly used for fuzzing, which requires to handle the profiles without any storage,
    since the generated profiles are not further used.

    :param cmd: list of commands that will be run
    :param workload: list of workloads
    :param collector: list of collectors
    :param postprocessor: list of postprocessors
    :param minor_version_list: list of MinorVersion info
    :param kwargs: dictionary of additional params for postprocessor and collector
    """
    job_matrix, number_of_jobs = construct_job_matrix(
        cmd, workload, collector, postprocessor, **kwargs
    )
    yield from generate_jobs(minor_version_list, job_matrix, number_of_jobs)


def run_single_job(
    cmd: list[str],
    workload: list[str],
    collector: list[str],
    postprocessor: list[str],
    minor_version_list: list[MinorVersion],
    with_history: bool = False,
    **kwargs: Any,
) -> CollectStatus:
    """
    :param cmd: list of commands that will be run
    :param workload: list of workloads
    :param collector: list of collectors
    :param postprocessor: list of postprocessors
    :param minor_version_list: list of MinorVersion info
    :param with_history: if set to true, then we will print the history object
    :param kwargs: dictionary of additional params for postprocessor and collector
    :return: CollectStatus.OK if all jobs were successfully collected, CollectStatus.ERROR if any
        of collections or postprocessing failed
    """
    log.major_info("Running From Single Job")
    job_matrix, number_of_jobs = construct_job_matrix(
        cmd, workload, collector, postprocessor, **kwargs
    )
    generator_function = generate_jobs_with_history if with_history else generate_jobs
    status = CollectStatus.OK
    finished_jobs = 0
    for status, prof, job in generator_function(minor_version_list, job_matrix, number_of_jobs):
        profile.save_profile(
            profile.finalize_profile_for_job(prof, job, kwargs.get("profile_label")),
            kwargs.get("profile_path"),
        )
        finished_jobs += 1
    return status if finished_jobs > 0 else CollectStatus.ERROR


def run_matrix_job(
    minor_version_list: list[MinorVersion], with_history: bool = False
) -> CollectStatus:
    """
    :param minor_version_list: list of MinorVersion info
    :param with_history: if set to true, then we will print the history object
    :return: CollectStatus.OK if all jobs were successfully collected, CollectStatus.ERROR if any
        of collections or postprocessing failed
    """
    log.major_info("Running Matrix Job")
    job_matrix, number_of_jobs = construct_job_matrix(**load_job_info_from_config())
    generator_function = generate_jobs_with_history if with_history else generate_jobs
    status = CollectStatus.OK
    finished_jobs = 0
    for status, prof, job in generator_function(minor_version_list, job_matrix, number_of_jobs):
        profile.save_profile(profile.finalize_profile_for_job(prof, job))
        finished_jobs += 1
    return status if finished_jobs > 0 else CollectStatus.ERROR
