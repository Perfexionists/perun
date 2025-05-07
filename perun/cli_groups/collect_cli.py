# Standard Imports
from typing import Any

# Third-Party Imports
import click

# Perun Imports
from perun.utils.structs import collect_structs
from perun.utils.common import cli_kit
from perun import profile
from perun.logic import commands, config as perun_config


@click.group()
@click.option(
    "--profile-dir",
    "-pd",
    nargs=1,
    type=click.Path(),
    help=(
        "Specifies the output directory in which the collected profile will be saved. "
        "The default directory is '.perun/jobs'. "
        "The directory will be created if it does not exist."
    ),
)
@click.option(
    "--profile-name",
    "-pn",
    nargs=1,
    type=str,
    help=(
        "Specifies the name of the collected profile, e.g., 'profile.perf', that will be stored in "
        "the output directory. The default name is generated according to the "
        ":ckey:`format.output_profile_template` configuration parameter."
    ),
)
@click.option(
    "--profile-label",
    "-pl",
    nargs=1,
    type=str,
    default="",
    help="An optional custom label to associate with the collected profile(s).",
)
@click.option(
    "--save-to-index",
    "-s",
    is_flag=True,
    default=False,
    callback=cli_kit.set_config_option_from_flag(
        perun_config.runtime, "profiles.register_after_run"
    ),
    help="Registers the imported profile in index instead of saving it in pending.",
)
@click.option(
    "--overwrite-profiles",
    is_flag=True,
    default=False,
    callback=cli_kit.set_config_option_from_flag(perun_config.runtime, "profiles.overwrite", str),
    help="If a profile with the same name already exists it will be overwritten instead of"
    "renaming this profile to contain a copy number suffix, e.g., custom_name(1).perf.",
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
    "-cp",
    is_flag=True,
    default=False,
    is_eager=True,
    help=(
        "If set to true, then for each specified minor versions, profiles for parents"
        " will be collected as well"
    ),
)
@click.option(
    "--cmd",
    "-c",
    nargs=1,
    required=False,
    multiple=True,
    default=[""],
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
    help="Inputs for <cmd>. E.g. ``./subdir`` is possible workload for ``ls`` command.",
)
@click.option(
    "--params",
    "-p",
    nargs=1,
    required=False,
    multiple=True,
    callback=cli_kit.single_yaml_param_callback,
    help="Additional parameters for called collector read from file in YAML format.",
)
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
    "--optimization-pipeline",
    "-op",
    type=click.Choice(collect_structs.Pipeline.supported()),
    default=collect_structs.Pipeline.default(),
    callback=cli_kit.set_optimization,
    help="Pre-configured combinations of collection optimization methods.",
)
@click.option(
    "--optimization-on",
    "-on",
    type=click.Choice(collect_structs.Optimizations.supported()),
    multiple=True,
    callback=cli_kit.set_optimization,
    help="Enable the specified collection optimization method.",
)
@click.option(
    "--optimization-off",
    "-off",
    type=click.Choice(collect_structs.Optimizations.supported()),
    multiple=True,
    callback=cli_kit.set_optimization,
    help="Disable the specified collection optimization method.",
)
@click.option(
    "--optimization-args",
    "-oa",
    type=(click.Choice(collect_structs.Parameters.supported()), str),
    multiple=True,
    callback=cli_kit.set_optimization_param,
    help="Set parameter values for various optimizations.",
)
@click.option(
    "--optimization-cache-off",
    is_flag=True,
    callback=cli_kit.set_optimization_cache,
    help="Ignore cached optimization data (e.g., cached call graph).",
)
@click.option(
    "--optimization-reset-cache",
    is_flag=True,
    default=False,
    callback=cli_kit.reset_optimization_cache,
    help="Remove the cached optimization resources and data.",
)
@click.option(
    "--use-cg-type",
    "-cg",
    type=(click.Choice(collect_structs.CallGraphTypes.supported())),
    default=collect_structs.CallGraphTypes.default(),
    callback=cli_kit.set_call_graph_type,
)
@click.pass_context
def collect(ctx: click.Context, **kwargs: Any) -> None:
    """Generates performance profile using selected collector.

    Runs the single collector unit (registered in Perun) on given profiled
    command (optionally with given arguments and workloads) and generates
    performance profile. The generated profile is then stored in
    ``.perun/jobs/`` directory as a file, by default with filename in form of::

        bin-collector-workload-timestamp.perf

    Generated profiles will not be postprocessed in any way. Consult ``perun
    postprocessby --help`` in order to postprocess the resulting profile.

    The configuration of collector can be specified in external YAML file given
    by the ``-p``/``--params`` argument.

    For a thorough list and description of supported collectors refer to
    :ref:`collectors-list`. For a more subtle running of profiling jobs and
    more complex configuration consult either ``perun run matrix --help`` or
    ``perun run job --help``.
    """
    commands.try_init()
    kwargs["profile_path"] = profile.ProfilePath(
        kwargs.get("profile_name"), kwargs.get("profile_dir")
    )
    ctx.obj = kwargs
