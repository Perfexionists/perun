"""Group of CLI commands used for importing profiles"""

from __future__ import annotations

# Standard Imports
from typing import Any

# Third-Party Imports
import click

# Perun Imports
from perun.logic import commands, config
from perun import profile as profile
from perun.utils.common import cli_kit


@click.group("import")
@click.option(
    "--machine-info",
    "-i",
    type=click.Path(),
    default="",
    help="Imports machine info from file in JSON format (by default, machine info is loaded from "
    "the current host). You can use `utils/generate_machine_info.sh` script to generate the "
    "machine info file.",
)
@click.option(
    "--import-dir",
    "-d",
    type=click.Path(resolve_path=True, readable=True),
    callback=cli_kit.set_config_option_from_flag(config.runtime, "import.dir"),
    help="Specifies the directory from which to import profiles and other files (e.g., stats, "
    "machine info, ...) that are provided as relative paths (default = ./).",
)
@click.option(
    "--minor-version",
    "-m",
    nargs=1,
    default=None,
    is_eager=True,
    help="Specifies the head minor version, for which the profiles will be imported.",
)
@click.option(
    "--stats-headers",
    "-t",
    nargs=1,
    default=None,
    metavar="[STAT_HEADER+]",
    help="Describes the stats headers associated with imported profiles specified directly in CLI. "
    "A stats header has the form of 'NAME[|COMPARISON_TYPE[|UNIT[|AGGREGATE_BY[|DESCRIPTION]]]]'.",
)
@click.option(
    "--metadata",
    "-md",
    multiple=True,
    metavar="['KEY|VALUE|[DESCRIPTION]'] or [FILE.json]",
    help="Describes a single metadata entry associated with the imported profiles as a "
    "'key|value[|description]' string, or a JSON file that may contain multiple metadata entries "
    "that will have its keys flattened. The --metadata option may be specified multiple times.",
)
@click.option(
    "--cmd",
    "-c",
    nargs=1,
    default="",
    help="Command that was being profiled. Either corresponds to some script, binary or command, "
    "e.g. ``./mybin`` or ``perun``.",
)
@click.option(
    "--workload",
    "-w",
    nargs=1,
    default="",
    help="Inputs for <cmd>. E.g. ``./subdir`` is possible workload for ``ls`` command.",
)
@click.option(
    "--save-to-index",
    "-s",
    is_flag=True,
    default=False,
    callback=cli_kit.set_config_option_from_flag(config.runtime, "profiles.register_after_run"),
    help="Registers the imported profile in index instead of saving it in pending.",
)
@click.option(
    "--overwrite-profiles",
    is_flag=True,
    default=False,
    callback=cli_kit.set_config_option_from_flag(config.runtime, "profiles.overwrite"),
    help="If a profile with the same name already exists it will be overwritten instead of"
    "renaming this profile to contain a copy number suffix, e.g., custom_name(1).perf.",
)
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
    help="An optional custom label to associate with the imported profile.",
)
@click.pass_context
def import_group(ctx: click.Context, **kwargs: Any) -> None:
    """Imports Perun profiles from different formats.

    If the --import-dir parameter is specified, relative file paths will be prefixed with the
    import directory path (with the default value being the current working directory).
    Absolute file paths ignore the import directory.
    """
    commands.try_init()
    kwargs["profile_path"] = profile.ProfilePath(
        kwargs.get("profile_name"), kwargs.get("profile_dir")
    )
    ctx.obj = kwargs


@import_group.group("perf")
@click.option(
    "--warmup",
    "-w",
    default=0,
    help="Sets [INT] warm up iterations of ith profiled command.",
)
@click.pass_context
def perf_group(ctx: click.Context, **kwargs: Any) -> None:
    """Imports Perun profiles from perf results

    This supports either profiles collected in:

     1. Binary format: e.g., `collected.data` files, that are results of `perf record`

     2. Text format: result of `perf script` that parses the binary into user-friendly and
        parsing-friendly text format
    """
    ctx.obj.update(kwargs)


@perf_group.command("record")
@click.argument("import_entries", nargs=-1, required=True)
@click.pass_context
@click.option(
    "--with-sudo",
    "-s",
    is_flag=True,
    help="Runs the conversion of the data in sudo mode.",
    default=False,
)
def from_binary(ctx: click.Context, import_entries: list[str], **kwargs: Any) -> None:
    """Imports Perun profiles from binary generated by `perf record` command.

    Multiple import entries may be specified; an import entry is either a profile entry

      'profile_path[,<exit code>[,<stat value>]+]'

    where each stat value corresponds to a stats header specified in the --stats-headers option,
    or a CSV file entry

      'file.csv'

    where the CSV file is in the format

      Profile,Exit_code[,stat-header1]+
      profile_path[,<exit code>[,<stat value>]+]
      ...

    that combines the --stats-headers option and profile entries.
    """
    kwargs.update(ctx.obj)
    profile.import_perf_from_record(import_entries, **kwargs)


@perf_group.command("script")
@click.argument("import_entries", type=str, nargs=-1, required=True)
@click.pass_context
def from_text(ctx: click.Context, import_entries: list[str], **kwargs: Any) -> None:
    """Import Perun profiles from output generated by `perf script` command.

    Multiple import entries may be specified; an import entry is either a profile entry

      'profile_path[,<exit code>[,<stat value>]+]'

    where each stat value corresponds to a stats header specified in the --stats-headers option,
    or a CSV file entry

      'file.csv'

    where the CSV file is in the format

      Profile,Exit_code[,stat-header1]+
      profile_path[,<exit code>[,<stat value>]+]
      ...

    that combines the --stats-headers option and profile entries.
    """
    kwargs.update(ctx.obj)
    profile.import_perf_from_script(import_entries, **kwargs)


@perf_group.command("stack")
@click.argument("import_entries", type=str, nargs=-1, required=True)
@click.pass_context
def from_stacks(ctx: click.Context, import_entries: list[str], **kwargs: Any) -> None:
    """Import Perun profiles from output generated by `perf script | stackcollapse-perf.pl`
    command.

    Multiple import entries may be specified; an import entry is either a profile entry

      'profile_path[,<exit code>[,<stat value>]+]'

    where each stat value corresponds to a stats header specified in the --stats-headers option,
    or a CSV file entry

      'file_path.csv'

    where the CSV file is in the format

      Profile,Exit_code[,stat-header1]+
      profile_path[,<exit code>[,<stat value>]+]
      ...

    that combines the --stats-headers option and profile entries.
    """
    kwargs.update(ctx.obj)
    profile.import_perf_from_stack(import_entries, **kwargs)


@import_group.group("elk")
@click.pass_context
def elk_group(ctx: click.Context, **kwargs: Any) -> None:
    """Imports Perun profiles from elk results

    By ELK we mean Elasticsearch Stack (Elasticsearch, Logstash, Kibana)

    We assume the data are already flattened and are in form of:

        [{key: value, ...}, ...]

    The command supports profiles collected in:

      1. JSON format: files extracted from ELK or stored using format compatible with ELK.
    """
    ctx.obj.update(kwargs)


@elk_group.command("json")
@click.argument("import_entries", nargs=-1, required=True)
@click.pass_context
def from_json(ctx: click.Context, import_entries: list[str], **kwargs: Any) -> None:
    """Imports Perun profiles from JSON compatible with elk infrastructure.

    Each import entry may specify a JSON path 'file_path.json'.
    """
    kwargs.update(ctx.obj)
    profile.import_elk_from_json(import_entries, **kwargs)
