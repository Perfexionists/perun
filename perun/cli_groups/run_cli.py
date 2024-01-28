"""Group of CLI commands for running the Perun process."""
from __future__ import annotations

# Standard Imports
from typing import Any

# Third-Party Imports
import click

# Perun Imports
from perun.logic import config as perun_config, runner
from perun.utils import log as perun_log
from perun.utils.common import cli_kit
from perun.utils.structs import CollectStatus


@click.group()
@click.option(
    "--output-filename-template",
    "-ot",
    default=None,
    callback=cli_kit.set_config_option_from_flag(
        perun_config.runtime, "format.output_profile_template", str
    ),
    help=(
        "Specifies the template for automatic generation of output filename"
        " This way the file with collected data will have a resulting filename w.r.t "
        " to this parameter. Refer to :ckey:`format.output_profile_template` for more"
        " details about the format of the template."
    ),
)
@click.option(
    "--minor-version",
    "-m",
    "minor_version_list",
    nargs=1,
    multiple=True,
    callback=cli_kit.minor_version_list_callback,
    default=["HEAD"],
    help="Specifies the head minor version, for which the profiles will be collected.",
)
@click.option(
    "--crawl-parents",
    "-c",
    is_flag=True,
    default=False,
    is_eager=True,
    help=(
        "If set to true, then for each specified minor versions, profiles for parents"
        " will be collected as well"
    ),
)
@click.option(
    "--force-dirty",
    "-f",
    is_flag=True,
    default=False,
    callback=cli_kit.unsupported_option_callback,
    help="If set to true, then even if the repository is dirty, the changes will not be stashed",
)
@click.pass_context
def run(ctx: click.Context, **kwargs: Any) -> None:
    """Generates batch of profiles w.r.t. specification of list of jobs.

    Either runs the job matrix stored in local.yml configuration or lets the
    user construct the job run using the set of parameters.
    """
    ctx.obj = kwargs


@run.command()
@click.pass_context
@click.option(
    "--without-vcs-history",
    "-q",
    "quiet",
    is_flag=True,
    default=False,
    help="Will not print the VCS history tree during the collection of the data.",
)
def matrix(ctx: click.Context, quiet: bool, **kwargs: Any) -> None:
    """Runs the jobs matrix specified in the local.yml configuration.

    This commands loads the jobs configuration from local configuration, builds
    the `job matrix` and subsequently runs the jobs collecting list of
    profiles. Each profile is then stored in ``.perun/jobs`` directory and
    moreover is annotated using by setting :preg:`origin` key to current
    ``HEAD``. This serves as check to not assign such profiles to different
    minor versions.

    The job matrix is defined in the yaml format and consists of specification
    of binaries with corresponding arguments, workloads, supported collectors
    of profiling data and postprocessors that alter the collected profiles.

    Refer to :doc:`jobs` and :ref:`jobs-matrix` for more details how to specify
    the job matrix inside local configuration and to :doc:`config` how to work
    with Perun's configuration files.
    """
    kwargs.update({"minor_version_list": ctx.obj["minor_version_list"]})
    kwargs.update({"with_history": not quiet})
    if runner.run_matrix_job(**kwargs) != CollectStatus.OK:
        perun_log.error("job specification failed in one of the phases")


@run.command()
@click.option(
    "--cmd",
    "-b",
    nargs=1,
    required=True,
    multiple=True,
    help=(
        "Command that is being profiled. Either corresponds to some"
        " script, binary or command, e.g. ``./mybin`` or ``perun``."
    ),
)
@click.option(
    "--args",
    "-a",
    nargs=1,
    required=False,
    multiple=True,
    help="Additional parameters for <cmd>. E.g. ``status`` or ``-al`` is command parameter.",
)
@click.option(
    "--workload",
    "-w",
    nargs=1,
    required=False,
    multiple=True,
    default=[""],
    help="Inputs for <cmd>. E.g. ``./subdir`` is possible workloadfor ``ls`` command.",
)
@click.option(
    "--collector",
    "-c",
    nargs=1,
    required=True,
    multiple=True,
    type=click.Choice(cli_kit.get_supported_module_names("collect")),
    help="Profiler used for collection of profiling data for the given <cmd>",
)
@click.option(
    "--collector-params",
    "-cp",
    nargs=2,
    required=False,
    multiple=True,
    callback=cli_kit.yaml_param_callback,
    help="Additional parameters for the <collector> read from the file in YAML format",
)
@click.option(
    "--postprocessor",
    "-p",
    nargs=1,
    required=False,
    multiple=True,
    type=click.Choice(cli_kit.get_supported_module_names("postprocess")),
    help=(
        "After each collection of data will run <postprocessor> to "
        "postprocess the collected resources."
    ),
)
@click.option(
    "--postprocessor-params",
    "-pp",
    nargs=2,
    required=False,
    multiple=True,
    callback=cli_kit.yaml_param_callback,
    help="Additional parameters for the <postprocessor> read from the file in YAML format",
)
@click.pass_context
def job(ctx: click.Context, **kwargs: Any) -> None:
    """Run specified batch of perun jobs to generate profiles.

    This command correspond to running one isolated batch of profiling jobs,
    outside of regular profiling. Run ``perun run matrix``, after specifying
    job matrix in local configuration to automate regular profiling of your
    project. After the batch is generated, each profile is tagged with
    :preg:`origin` set to current ``HEAD``. This serves as check to not assign
    such profiles to different minor versions.

    By default, the profiles computed by this batch job are stored inside the
    ``.perun/jobs/`` directory as a files in form of::

        bin-collector-workload-timestamp.perf

    In order to store generated profiles run the following, with ``i@p``
    corresponding to `pending tag`, which can be obtained by running ``perun
    status``::

        perun add i@p

    .. code-block:: bash

        perun run job -c time -b ./mybin -w file.in -w file2.in -p regression-analysis

    This command profiles two commands ``./mybin file.in`` and ``./mybin
    file2.in`` and collects the profiling data using the
    :ref:`collectors-time`. The profiles are then modeled with the
    :ref:`postprocessors-regression-analysis`.

    .. code-block:: bash

        perun run job -c complexity -b ./mybin -w sll.cpp -cp complexity targetdir=./src

    This commands runs one job './mybin sll.cpp' using the
    :ref:`collectors-trace`, which uses custom binaries targeted at
    ``./src`` directory.

    .. code-block:: bash

        perun run job -c mcollect -b ./mybin -b ./otherbin -w input.txt -p regressogram -p regression-analysis

    This commands runs two jobs ``./mybin input.txt`` and ``./otherbin
    input.txt`` and collects the profiles using the :ref:`collectors-memory`.
    The profiles are then postprocessed, first using the
    :ref:`postprocessors-regressogram` and then with
    :ref:`postprocessors-regression-analysis`.

    Refer to :doc:`jobs` and :doc:`profile` for more details about automation
    and lifetimes of profiles. For list of available collectors and
    postprocessors refer to :ref:`collectors-list` and
    :ref:`postprocessors-list` respectively.
    """
    kwargs.update({"minor_version_list": ctx.obj["minor_version_list"]})
    kwargs.update({"with_history": True})
    if runner.run_single_job(**kwargs) != CollectStatus.OK:
        perun_log.error("job specification failed in one of the phases")
