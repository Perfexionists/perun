"""Group of CLI commands, that are not directly part of the Perun

This contains various scripts for generation of the modules, for management of temporary and
stats directories, etc.
"""
from __future__ import annotations

# Standard Imports
from typing import Any

# Third-Party Imports
import click

# Perun Imports
from perun.logic import commands, stats, temp
from perun.utils import log as perun_log
from perun.utils.common import cli_kit, script_kit as scripts
from perun.utils.exceptions import ExternalEditorErrorException


@click.group("utils")
def utils_group() -> None:
    """Contains set of developer commands, wrappers over helper scripts and other functions that are
    not the part of the main perun suite.
    """
    pass


@utils_group.command()
@click.argument(
    "template_type",
    metavar="<template>",
    required=True,
    type=click.Choice(["collect", "postprocess", "view", "check"]),
)
@click.argument("unit_name", metavar="<unit>")
@click.option(
    "--no-before-phase",
    "-nb",
    default=False,
    is_flag=True,
    help="If set to true, the unit will not have before() function defined.",
)
@click.option(
    "--no-after-phase",
    "-na",
    default=False,
    is_flag=True,
    help="If set to true, the unit will not have after() function defined.",
)
@click.option(
    "--no-edit",
    "-ne",
    default=False,
    is_flag=True,
    help=(
        "Will open the newly created files in the editor specified by "
        ":ckey:`general.editor` configuration key."
    ),
)
@click.option(
    "--supported-type",
    "-st",
    "supported_types",
    nargs=1,
    multiple=True,
    help="Sets the supported types of the unit (i.e. profile types).",
)
def create(template_type: str, **kwargs: Any) -> None:
    """According to the given <template> constructs a new modules in Perun for <unit>.

    Currently, this supports creating new modules for the tool suite (namely ``collect``,
    ``postprocess``, ``view``) or new algorithms for checking degradation (check). The command uses
    templates stored in `../perun/templates` directory and uses _jinja as a template handler. The
    templates can be parametrized by the following by options (if not specified 'none' is used).

    Unless ``--no-edit`` is set, after the successful creation of the files, an external editor,
    which is specified by :ckey:`general.editor` configuration key.

    .. _jinja: https://jinja.palletsprojects.com/en/latest/
    """
    try:
        scripts.create_unit_from_template(template_type, **kwargs)
    except ExternalEditorErrorException as editor_exception:
        perun_log.error(f"while invoking external editor: {editor_exception}")


@utils_group.group("temp")
def temp_group() -> None:
    """Provides a set of operations for maintaining the temporary directory (.perun/tmp/) of perun."""
    pass


@temp_group.command("list")
@click.argument("root", type=click.Path(), required=False, default=".")
@click.option(
    "--no-total-size",
    "-t",
    flag_value=True,
    default=False,
    help="Do not show the total size of all the temporary files combined.",
)
@click.option(
    "--no-file-size",
    "-f",
    flag_value=True,
    default=False,
    help="Do not show the size of each temporary file.",
)
@click.option(
    "--no-protection-level",
    "-p",
    flag_value=True,
    default=False,
    help="Do not show the protection level of the temporary files.",
)
@click.option(
    "--sort-by",
    "-s",
    type=click.Choice(temp.SORT_ATTR),
    default=temp.SORT_ATTR[0],
    help="Sorts the temporary files on the output.",
)
@click.option(
    "--filter-protection",
    "-fp",
    type=click.Choice(temp.PROTECTION_LEVEL),
    default=temp.PROTECTION_LEVEL[0],
    help="List only temporary files with the given protection level.",
)
def temp_list(root: str, **kwargs: Any) -> None:
    """Lists the temporary files of the '.perun/tmp/' directory. It is possible to list only
    files in specific subdirectory by supplying the ROOT path.

    The path can be either absolute or relative - the base of the relative path is the tmp/
    directory.
    """
    commands.print_temp_files(root, **kwargs)


@temp_group.command("delete")
@click.argument("path", type=click.Path(), required=True)
@click.option(
    "--warn",
    "-w",
    flag_value=True,
    default=False,
    help=(
        "Warn the user (and abort the deletion with no files deleted) if protected files"
        " are present."
    ),
)
@click.option(
    "--force",
    "-f",
    flag_value=True,
    default=False,
    help="If set, protected files are deleted regardless of --warn value.",
)
@click.option(
    "--keep-directories",
    "-k",
    flag_value=True,
    default=False,
    help="If path refers to directory, empty tmp/ directories and subdirectories will be kept.",
)
def temp_delete(path: str, warn: bool, force: bool, **kwargs: Any) -> None:
    """Deletes the temporary file or directory.

    Use the command 'perun utils temp delete .' to safely delete all unprotected files in the
    '.perun/tmp/' directory.

    The command 'perun utils temp delete -f .' can be used to clear the whole '.perun/tmp/'
    directory including protected files. Protected files are usually more important and should not
    be deleted without a good reason (such as tmp/ corruption, too many uncleared files etc.)

    However, deleting temp files (protected or not) should not be done when other perun processes
    are running as it may cause them to crash due to a missing file.
    """
    commands.delete_temps(path, not warn, force, **kwargs)


@temp_group.command("sync")
def temp_sync() -> None:
    """Synchronizes the '.perun/tmp/' directory contents with the internal tracking file. This is
    useful when some files or directories were deleted manually and the resulting inconsistency is
    causing troubles - however, this should be a very rare condition.

    Invoking the 'temp list' command should also synchronize the internal state automatically.
    """
    commands.sync_temps()


@utils_group.group("stats")
def stats_group() -> None:
    """Provides a set of operations for manipulating the stats directory (.perun/stats/) of perun."""
    pass


@stats_group.command("list-files")
@click.option(
    "--top",
    "-N",
    type=int,
    default=stats.DEFAULT_STATS_LIST_TOP,
    show_default=True,
    help=(
        "Show only stat files from top N minor versions. Show all results if set to 0. "
        "The minor version to start at can be changed using --from-minor."
    ),
)
@click.option(
    "--from-minor",
    "-m",
    default=None,
    metavar="<hash>",
    is_eager=True,
    callback=cli_kit.lookup_minor_version_callback,
    help="Show stat files starting from a certain minor version (default is HEAD).",
)
@click.option(
    "--no-minor",
    "-i",
    flag_value=True,
    default=False,
    help="Do not show the minor version headers in the output.",
)
@click.option(
    "--no-file-size",
    "-f",
    flag_value=True,
    default=False,
    help="Do not show the size of each stat file.",
)
@click.option(
    "--no-total-size",
    "-t",
    flag_value=True,
    default=False,
    help="Do not show the total size of all the stat files combined.",
)
@click.option(
    "--sort-by-size",
    "-s",
    flag_value=True,
    default=False,
    help="Sort the files by size instead of the minor versions order.",
)
def stats_list_files(**kwargs: Any) -> None:
    """Show stat files stored in the stats directory (.perun/stats/). This command shows only a
    limited number of the most recent files by default. This can be, however, changed by the
    --top and --from-minor options.

    The default output format is 'file size | minor version | file name'.
    """
    commands.list_stat_objects("files", **kwargs)


@stats_group.command("list-versions")
@click.option(
    "--top",
    "-N",
    type=int,
    default=stats.DEFAULT_STATS_LIST_TOP,
    show_default=True,
    help=(
        "Show only top N minor versions. Show all versions if set to 0. "
        "The minor version to start at can be changed using --from-minor."
    ),
)
@click.option(
    "--from-minor",
    "-m",
    default=None,
    metavar="<hash>",
    is_eager=True,
    callback=cli_kit.lookup_minor_version_callback,
    help="Show minor versions starting from a certain minor version (default is HEAD).",
)
@click.option(
    "--no-dir-size",
    "-d",
    flag_value=True,
    default=False,
    help="Do not show the size of the version directory.",
)
@click.option(
    "--no-file-count",
    "-f",
    flag_value=True,
    default=False,
    help="Do not show the number of files in each version directory.",
)
@click.option(
    "--no-total-size",
    "-t",
    flag_value=True,
    default=False,
    help="Do not show the total size of all the versions combined.",
)
@click.option(
    "--sort-by-size",
    "-s",
    flag_value=True,
    default=False,
    help="Sort the versions by size instead of their VCS order.",
)
def stats_list_versions(**kwargs: Any) -> None:
    """Show minor versions stored as directories in the stats directory (.perun/stats/).
    This command shows only a limited number of the most recent versions by default. This can be,
    however, changed by the --top and --from-minor options.

    The default output format is 'directory size | minor version | file count'.
    """
    commands.list_stat_objects("versions", **kwargs)


@stats_group.group("delete")
def stats_delete_group() -> None:
    """Allows the deletion of stat files, minor versions or the whole stats directory."""
    pass


@stats_delete_group.command("file")
@click.argument("name", type=click.Path(), callback=cli_kit.lookup_stats_file_callback)
@click.option(
    "--in-minor",
    "-m",
    default=None,
    metavar="<hash>",
    is_eager=True,
    callback=cli_kit.check_stats_minor_callback,
    help=(
        "Delete the stats file in the specified minor version (HEAD if not specified) "
        'or across all the minor versions if set to ".".'
    ),
)
@click.option(
    "--keep-directory",
    "-k",
    flag_value=True,
    default=False,
    help="Possibly empty directory of minor version will be kept in the file system.",
)
def stats_delete_file(**kwargs: Any) -> None:
    """Deletes a stat file in either specific minor version or across all the minor versions in the
    stats directory.
    """
    commands.delete_stats_file(**kwargs)


@stats_delete_group.command("minor")
@click.argument("version", callback=cli_kit.check_stats_minor_callback)
@click.option(
    "--keep-directory",
    "-k",
    flag_value=True,
    default=False,
    help="Resulting empty directory of minor version will be kept in the file system.",
)
def stats_delete_minor(version: str, **kwargs: Any) -> None:
    """Deletes the specified minor version directory in stats with all its content."""
    commands.delete_stats_minor(version, **kwargs)


@stats_delete_group.command(".")
@click.option(
    "--keep-directory",
    "-k",
    flag_value=True,
    default=False,
    help="Resulting empty directories of minor versions will be kept in the file system.",
)
def stats_delete_all(**kwargs: Any) -> None:
    """Deletes the whole content of the `stats` directory."""
    commands.delete_stats_all(**kwargs)


@stats_group.command("clean")
@click.option(
    "--keep-custom",
    "-c",
    flag_value=True,
    default=False,
    help="The custom stats directories will not be removed.",
)
@click.option(
    "--keep-empty",
    "-e",
    flag_value=True,
    default=False,
    help="The empty version directories will not be removed.",
)
def stats_clean(**kwargs: Any) -> None:
    """Cleans the stats directory by synchronizing the internal state, deleting distinguishable
    custom files and directories (i.e. not all the custom-made or manually created files /
    directories can be identified as custom, e.g. when they comply the correct format etc.)
    and by removing the empty minor version directories.
    """
    commands.clean_stats(**kwargs)


@stats_group.command("sync")
def stats_sync() -> None:
    """Synchronizes the actual contents of the stats directory with the internal 'index' file.
    The synchronization should be needed only rarely - mainly in cases when the stats directory
    has been manually tampered with and some files or directories were created or deleted by a user.
    """
    commands.sync_stats()
