"""Set of helper functions for working with command line.

Contains functions for click api, for processing parameters from command line, validating keys,
and returning default values.
"""

from __future__ import annotations

# Standard Imports
from collections import defaultdict
from importlib import metadata
from typing import Optional, Callable, Any, TYPE_CHECKING
import functools
import json
import os
import platform
import re
import sys
import time
import traceback

# Third-Party Imports
import click
import jinja2

# Perun Imports
import perun
from perun import profile as profile
from perun.logic import commands, store, stats, config, pcs
from perun.utils import exceptions, streams, timestamps, log, metrics
from perun.utils.common import common_kit
from perun.utils.exceptions import (
    VersionControlSystemException,
    TagOutOfRangeException,
    StatsFileNotFoundException,
    NotPerunRepositoryException,
)
from perun.utils.structs import collect_structs

if TYPE_CHECKING:
    from perun.utils.structs.common_structs import MinorVersion


def print_version(_: click.Context, __: click.Option, value: bool) -> None:
    """Prints current version of Perun and ends"""
    if value:
        log.write(f"Perun {perun.__version__}")
        exit(0)


def process_target_dir(value: str) -> str:
    """Helper function for processing target dir and creating subdirs

    :param value: passed value
    :retrun: valid path with created directories
    """
    common_kit.touch_dir(value)
    return value


def process_bokeh_axis_title(
    ctx: click.Context, param: click.Option, value: Optional[str]
) -> Optional[str]:
    """Processes default value for axes.

    If the value supplied from CLI is non-None, it is returned as it is. Otherwise, we try to
    create some optimal axis name. We do this according to the already processed parameters and
    we either use 'per_key' or 'of_key'.

    :param ctx: called context of the process
    :param param: called option (either x or y-axis)
    :param value: given value for the option param
    :return: either value (if it is non-None) or default legend for given axis
    """
    if not value and param.human_readable_name.startswith("x"):
        if "per_key" in ctx.params.keys():
            return ctx.params["per_key"]
        elif "through_key" in ctx.params.keys():
            return ctx.params["through_key"]
    elif not value and param.human_readable_name.startswith("y"):
        return ctx.params["of_key"]
    return value


def process_resource_key_param(
    ctx: click.Context, param: click.Option, value: Optional[str]
) -> Optional[str]:
    """Processes value for the key param (according to the profile)

    Checks the global context for stored profile, and obtains all the keys, which serves
    as a validation list for the given values for the parameters. For X axis, snapshots are
    an additional valid parameter.

    :param ctx: called context of the process
    :param param: called option that takes a valid key from profile as a parameter
    :param value: given value for the option param
    :return: value or raises bad parameter
    :raises click.BadParameter: if the value is invalid for the profile
    """
    if param.human_readable_name in ("per_key", "through_key") and value == "snapshots":
        return value
    # Validate the keys, if it is one of the set
    assert (
        hasattr(ctx, "parent") and ctx.parent is not None
    ), "The function expects `ctx` has parent"
    valid_keys = set(ctx.parent.params.get("profile", profile.Profile()).all_resource_fields())
    if value not in valid_keys:
        valid_keys_str = ", ".join(f"'{vk}'" for vk in valid_keys)
        raise click.BadParameter(f"'{value}' is not one of {valid_keys_str}.")
    return value


def process_continuous_key(
    ctx: click.Context, _: click.Option, value: Optional[str]
) -> Optional[str]:
    """Helper function for processing the continuous key for the param.

    Continuous keys are used in the continuous graphs (do'h!) on the x-axis, i.e. they have to be
    numeric. We check all keys in the resources.

    :param ctx: called context of the process
    :param _: called parameter
    :param value: given value for the option param
    :return: value or raises bad parameter
    :raises click.BadParameter: if the value is invalid for the profile
    """
    if value != "snapshots" and ctx.parent is not None:
        # If the requested value is not 'snapshots', then get all the numerical keys
        valid_numeric_keys = set(
            profile.all_numerical_resource_fields_of(
                ctx.parent.params.get("profile", profile.Profile())
            )
        )
        # Check if the value is valid numeric key
        if value not in valid_numeric_keys:
            valid_choices = ", ".join(f"'{vnk}'" for vnk in valid_numeric_keys | {"snapshots"})
            raise click.BadParameter(f"'{value}' is not one of {valid_choices}.")
    return value


def set_config_option_from_flag(
    dst_config_getter: Callable[[], config.Config],
    config_option: str,
    postprocess_function: Callable[[str], str] = lambda x: x,
) -> Callable[[click.Context, click.Option, Any], Any]:
    """Helper function for setting the config option from the CLI option handler

    Returns the option handler, that sets, if value is equal to true, the config option to the
    given option value. This is e.g. used to use the CLI to set various configurations temporarily
    from the command line option.

    :param dst_config_getter: destination config, where the option will be set
    :param config_option: name of the option that will be set in the runtime config
    :param postprocess_function: function which will postprocess the value
    :return: handler for the command line interface
    """

    def option_handler(_: click.Context, __: click.Option, value: Any) -> Any:
        """Wrapper handling function

        :param _: called context of the process
        :param __: called parameter
        :param value: given value of the option param
        :return:
        """
        if value:
            dst_config_getter().set(config_option, postprocess_function(value))
        return value

    return option_handler


def yaml_param_callback(
    _: click.Context, __: click.Option, value: list[tuple[str, str]]
) -> dict[str, Any]:
    """Callback function for parsing the yaml files to dictionary object

    :param _: context of the called command
    :param __: parameter that is being parsed and read from commandline
    :param value: value that is being read from the commandline
    :return: parsed yaml file
    """
    unit_to_params: dict[str, dict[Any, Any]] = defaultdict(dict)
    for unit, yaml_file in value:
        unit_to_params[unit].update(streams.safely_load_yaml(yaml_file))
    return unit_to_params


def single_yaml_param_callback(_: click.Context, __: click.Option, value: str) -> dict[str, Any]:
    """Callback function for parsing the yaml files to dictionary object, when called from 'collect'

    This does not require specification of the collector to which the params correspond and is
    meant as massaging of parameters for 'perun -p file collect ...' command.

    :param _: context of the called command
    :param __: parameter that is being parsed and read from commandline
    :param value: value that is being read from the commandline
    :return: parsed yaml file
    """
    unit_to_params = {}
    for yaml_file in value:
        # First check if this is a file
        unit_to_params.update(streams.safely_load_yaml(yaml_file))
    return unit_to_params


def minor_version_list_callback(
    ctx: click.Context, _: click.Option, value: str
) -> list[MinorVersion]:
    """Callback function for parsing the minor version list for running the automation

    :param ctx: context of the called command
    :param _: parameter that is being parsed and read from commandline
    :param value: value that is being read from the commandline
    :return: list of MinorVersion objects
    """
    minors: list[MinorVersion] = []
    for minor_version in value or []:
        massaged_version = pcs.vcs().massage_parameter(minor_version)
        # If we should crawl all the parents, we collect them
        if ctx.params.get("crawl_parents", False):
            minors.extend(pcs.vcs().walk_minor_versions(massaged_version))
        # Otherwise we retrieve the minor version info for the param
        else:
            minors.append(pcs.vcs().get_minor_version_info(massaged_version))
    return minors


def unsupported_option_callback(_: click.Option, param: click.Option, value: Any) -> None:
    """Processes the currently unsupported option or argument.

    :param _: called context of the parameter
    :param param: option or parameter we are processing
    :param value: value of the parameter we are trying to set
    """
    if value:
        err_msg = f"option '{param.human_readable_name}'"
        err_msg += "is unsupported/not implemented in this version of perun"
        err_msg += "\n\nPlease update your perun or wait patiently for the implementation"
        log.error(err_msg)


def config_key_validation_callback(_: click.Context, param: click.Option, value: str) -> str:
    """Validates whether the value of the key is in correct format---strings delimited by dot.

    :param _: called context of the command line
    :param param: called option (key in this case)
    :param value: assigned value to the <key> argument
    :return: value for the <key> argument
    """
    if not config.is_valid_key(str(value)):
        err_msg = (
            f"<key> argument '{value}' for {str(param.param_type_name)} config operation is in"
            " invalid format. "
        )
        err_msg += "Valid key should be represented as sections delimited by dot (.), "
        err_msg += "e.g. general.paging is valid key."
        raise click.BadParameter(err_msg)
    return value


def vcs_path_callback(_: click.Context, __: click.Option, value: Any) -> Any:
    """Parses the vcs path during the init

    :param ctx: context of the called command
    :param param: parameter that is being parsed
    :param value: value that is being read from the commandline
    :return: tuple of flags or parameters
    """
    return common_kit.locate_dir_on(".", ".git") if not value else value


def vcs_parameter_callback(ctx: click.Context, param: click.Option, value: Any) -> Any:
    """Parses flags and parameters for version control system during the init

    Collects all flags (as flag: True) and parameters (as key value pairs) inside the
    ctx.params['vcs_params'] dictionary, which is then send to the initialization of vcs.

    :param ctx: context of the called command
    :param param: parameter that is being parsed
    :param value: value that is being read from the commandline
    :return: tuple of flags or parameters
    """
    if "vcs_params" not in ctx.params.keys():
        ctx.params["vcs_params"] = {}
    for vcs_param in value:
        if isinstance(param.name, str) and param.name.endswith("param"):
            ctx.params["vcs_params"][vcs_param[0]] = vcs_param[1]
        else:
            ctx.params["vcs_params"][vcs_param] = True
    return value


def lookup_nth_pending_filename(position: int) -> str:
    """Looks up the nth pending file from the sorted list of pending files

    :param position: position of the pending we will look up
    :return: pending profile at given position
    """
    pending = commands.get_untracked_profiles()
    profile.sort_profiles(pending)
    if 0 <= position < len(pending):
        return pending[position].realpath
    else:
        raise click.BadParameter(
            f"invalid tag '{position}@p' (choose from interval <0@p, {len(pending) - 1}@p>)"
        )


def apply_func_for_range(
    range_match: re.Match[str], function_for_tag: Callable[[int], Any], tag: str
) -> None:
    """Applies the function for tags either from index or pending according to the range i-j

    :param range_match: match of the range
    :param function_for_tag: function that removes tag from index or pending
    :param tag: tag that is removed (either p or i)
    """
    from_range, to_range = int(range_match.group(1)), int(range_match.group(2))
    for i in range(from_range, to_range + 1):
        try:
            function_for_tag(i)
        except click.BadParameter:
            log.warn(f"skipping nonexisting tag {i}{tag}")


def lookup_added_profile_callback(_: click.Context, __: click.Option, value: str) -> set[str]:
    """Callback function for looking up the profile which will be added/registered

    Profile can either be represented as a pending tag (e.g. 0@p), as a pending tag range
    (e.g. 0@p-5@p) or as a path to a file.

    :param _: context of the called command
    :param __: parameter that is being parsed and read from commandline
    :param value: value that is being read from the commandline
    :return: filename of the profile
    """
    massaged_values = set()
    for single_value in value:
        pending_match = store.PENDING_TAG_REGEX.match(single_value)
        range_match = store.PENDING_TAG_RANGE_REGEX.match(single_value)
        if pending_match:
            massaged_values.add(lookup_nth_pending_filename(int(pending_match.group(1))))
        elif range_match:
            apply_func_for_range(
                range_match,
                lambda j: massaged_values.add(lookup_nth_pending_filename(j)),
                "p",
            )
        else:
            massaged_values.add(lookup_profile_in_filesystem(single_value))
    return massaged_values


def lookup_removed_profile_callback(ctx: click.Context, _: click.Option, value: str) -> set[str]:
    """Callback function for looking up the profile which will be removed

    Profile can either be represented as an index tag (e.g. 0@i), as an index tag range (e.g.
    0@i-5@i) or as a path in the index

    :param ctx: context of the called command
    :param _: parameter that is being parsed and read from commandline
    :param value: value that is being read from the commandline
    :return: filename of the profile to be removed
    """

    def add_to_removed_from_index(index: int) -> None:
        """Helper function for adding stuff to massaged values

        :param index: index we are looking up and registering to massaged values
        """
        try:
            index_filename = profile.get_nth_profile_of(index, ctx.params["minor"])
            start = index_filename.rfind("objects") + len("objects")
            # Remove the .perun/objects/... prefix and merge the directory and file to sha
            ctx.params["from_index_generator"].add("".join(index_filename[start:].split("/")))
        except TagOutOfRangeException as exc:
            # Invalid tag value, rethrow as click error
            raise click.BadParameter(str(exc))

    def add_to_removed_from_pending(pending: int) -> None:
        """Helper function for adding pending to massaged values.

        :param pending: index of the pending profile
        """
        pending_profile = lookup_nth_pending_filename(pending)
        ctx.params["from_jobs_generator"].add(pending_profile)

    ctx.params.setdefault("from_index_generator", set())
    ctx.params.setdefault("from_jobs_generator", set())

    massaged_values = set()
    for single_value in value:
        with exceptions.SuppressedExceptions(NotPerunRepositoryException):
            index_match = store.INDEX_TAG_REGEX.match(single_value)
            index_range_match = store.INDEX_TAG_RANGE_REGEX.match(single_value)
            pending_match = store.PENDING_TAG_REGEX.match(single_value)
            pending_range_match = store.PENDING_TAG_RANGE_REGEX.match(single_value)
            if index_match:
                add_to_removed_from_index(int(index_match.group(1)))
            elif index_range_match:
                apply_func_for_range(index_range_match, add_to_removed_from_index, "i")
            elif pending_match:
                add_to_removed_from_pending(int(pending_match.group(1)))
            elif pending_range_match:
                apply_func_for_range(pending_range_match, add_to_removed_from_pending, "p")
            # We check if this is actually something from pending, then we will remove it
            elif os.path.exists(single_value) and os.path.samefile(
                os.path.split(single_value)[0], pcs.get_job_directory()
            ):
                ctx.params["from_jobs_generator"].add(single_value)
            # other profiles that are specified by the path are removed from index only
            else:
                ctx.params["from_index_generator"].add(single_value)
    massaged_values.update(ctx.params["from_index_generator"])
    massaged_values.update(ctx.params["from_jobs_generator"])
    return massaged_values


def lookup_profile_in_filesystem(profile_name: str) -> str:
    """Helper function for looking up the profile in the filesystem

    First we check if the file is an absolute path, otherwise we look up within the pending profile,
    i.e. in the .perun/jobs directory. If we still have not found the profile, we then iteratively
    explore the subfolders starting from current directory and look for a potential match.

    :param profile_name: value that is being read from the commandline
    :return: full path to profile
    """
    # 1) if it exists return the value
    if os.path.exists(profile_name):
        return profile_name

    log.minor_fail(f"file '{profile_name}'", "does not exist")
    log.minor_info("Checking pending jobs")
    # 2) if it does not exist check pending
    job_dir = pcs.get_job_directory()
    job_path = os.path.join(job_dir, profile_name)
    if os.path.exists(job_path):
        return job_path

    log.minor_fail(f"file '{profile_name}'", "not found in pending jobs")
    # 3) if still not found, check recursively all candidates for match and ask for confirmation
    searched_regex = re.compile(profile_name)
    for root, _, files in os.walk(os.getcwd()):
        for file in files:
            full_path = os.path.join(root, file)
            if file.endswith(".perf") and searched_regex.search(full_path):
                rel_path = os.path.relpath(full_path, os.getcwd())
                if common_kit.perun_confirm(f"did you perhaps mean '{rel_path}'?"):
                    return full_path

    return profile_name


def lookup_minor_version_callback(_: click.Context, __: click.Option, value: str) -> str:
    """Callback for looking up the minor version, if it was not stated

    :param _: context of the called command
    :param __: parameter that is being parsed and read from commandline
    :param value: value that is being read from the commandline
    :return: massaged minor version
    """
    if value:
        try:
            return pcs.vcs().massage_parameter(value)
        except VersionControlSystemException as exception:
            raise click.BadParameter(str(exception))
    return value


def lookup_list_of_profiles_callback(
    ctx: click.Context, arg: click.Argument, value: tuple[str]
) -> list[profile.Profile]:
    """Callback for lookup up list of profiles anywhere

    :param ctx: context of the CLI
    :param arg: passed argument
    :param value: list of profiles
    :return: list of profiles
    """
    profiles = []
    aggregation_function = config.lookup_key_recursively("profile.aggregation", default="median")
    for prof in value:
        loaded_profile = lookup_any_profile_callback(ctx, arg, prof)
        loaded_profile.apply(aggregation_function)
        profiles.append(loaded_profile)
    return profiles


def lookup_any_profile_callback(
    _: click.Context, __: click.Argument, value: str
) -> profile.Profile:
    """Callback for looking up any profile, i.e. anywhere (in index, in pending, etc.)

    :param _: context
    :param __: param
    :param value: value of the profile parameter
    """
    # TODO: only temporary??? The fuck is temporary here???
    profile_path = os.path.join(pcs.get_job_directory(), value)
    if metrics.is_enabled() and os.path.exists(profile_path):
        metrics.add_metric("profile size", os.stat(profile_path).st_size)
    parts = value.split("^")
    rev = None
    if len(parts) > 1:
        rev, value = parts[0], parts[1]
        rev = pcs.vcs().massage_parameter(rev)
    # 0) First check if the value is tag or not
    index_tag_match = store.INDEX_TAG_REGEX.match(value)
    if index_tag_match:
        try:
            index_profile = profile.get_nth_profile_of(int(index_tag_match.group(1)), rev)
            return store.load_profile_from_file(index_profile, is_raw_profile=False)
        except TagOutOfRangeException as exc:
            raise click.BadParameter(str(exc))

    pending_tag_match = store.PENDING_TAG_REGEX.match(value)
    if pending_tag_match:
        pending_profile = lookup_nth_pending_filename(int(pending_tag_match.group(1)))
        # We know it should exist, so we can load it unsafe without check for existence
        return store.load_profile_from_file(pending_profile, is_raw_profile=True, unsafe_load=True)

    # 1) Check the index, if this is registered
    profile_from_index = commands.load_profile_from_args(value, rev)
    if profile_from_index:
        return profile_from_index

    log.minor_fail(f"file '{value}'", "not found in index")
    log.minor_info("Checking filesystem.")
    # 2) Else lookup filenames and load the profile
    abs_path = lookup_profile_in_filesystem(value)
    if not os.path.exists(abs_path):
        log.error(f"could not lookup the profile '{abs_path}'")

    # We checked for existence of the path above, we omit the check
    return store.load_profile_from_file(abs_path, is_raw_profile=True, unsafe_load=True)


def check_stats_minor_callback(_: click.Context, param: click.Argument, value: str) -> str:
    """Callback for checking existence of the minor version value in the VCS and also checking
    that a corresponding version directory exists in the stats.

    The only exception is a 'in_minor' parameter which can also refer to all the available
    minor versions by having a value of '.'.

    :param _: context
    :param param: the parameter name
    :param value: the supplied minor version value

    :return: the original value, which has been however checked
    """
    if param.name == "in_minor" and value == ".":
        return value
    elif value:
        # Check the minor version existence and that it has a directory in the 'stats'
        # There are 2 possible failures - the minor version or the directory don't exist
        try:
            exists, _ = stats.find_minor_stats_directory(value)
            if not exists:
                raise click.BadParameter(
                    f"The requested minor version '{value}' does not exist in the stats directory."
                )
        except VersionControlSystemException as exc:
            raise click.BadParameter(str(exc))
        # The minor version value is valid
    return value


def lookup_stats_file_callback(ctx: click.Context, _: click.Argument, value: str) -> Any:
    """Callback for looking up the stats file in the stats directory. The stats file is searched
    for in the specific minor version - if provided in 'in_minor' parameter - otherwise no lookup
    is performed.

    :param ctx: context
    :param _: param
    :param value: the file name

    :return: either the looked up path of the file or the original value if no lookup was performed
    """
    # Resolve the 'in_minor' to HEAD if not specified
    in_minor = pcs.vcs().get_minor_head() if not ctx.params["in_minor"] else ctx.params["in_minor"]
    # Check the existence only for files with specific 'in_minor'
    if in_minor != ".":
        try:
            return stats.get_stats_file_path(value, in_minor, True)
        except StatsFileNotFoundException:
            raise click.BadParameter(
                f"The requested file '{value}' does not exist in the stats directory for minor"
                f" version '{in_minor}'."
            )
    return value


def resources_key_options(
    func: Callable[..., Any],
) -> Callable[[click.Context, click.Option, Any], Any]:
    """
    This method creates Click decorator for common options for  all non-parametric
    postprocessor: `regressogram`, `moving average` and `kernel-regression`.


    :param func: the function in which the decorator of common options is currently applied
    :return: returns sequence of the single options for the current function (f) as decorators
    """
    options = [
        click.option(
            "--per-key",
            "-per",
            "per_key",
            default="structure-unit-size",
            nargs=1,
            metavar="<per_resource_key>",
            callback=process_resource_key_param,
            help="Sets the key that will be used as a source variable (x-coordinates).",
        ),
        click.option(
            "--of-key",
            "-of",
            "of_key",
            nargs=1,
            metavar="<of_resource_key>",
            default="amount",
            callback=process_resource_key_param,
            help="Sets key for which we are finding the model (y-coordinates).",
        ),
    ]
    return functools.reduce(lambda x, option: option(x), options, func)


CLI_DUMP_TEMPLATE = None
CLI_DUMP_TEMPLATE_STRING = """Environment Info
----------------

  * Perun {{ env.perun }}
  * Python:  {{ env.python.version }}
  * Installed Python packages:

  // for pkg in env.python.packages
    * {{ pkg }}
  // endfor
  * OS: {{ env.os.type }}, {{ env.os.distro }} ({{ env.os.arch }})

Command Line Commands
---------------------

  .. code-block:: bash

    $ {{ command }}

Standard and Error Output
-------------------------

  * Raised exception and trace:

  .. code-block:: bash

    {{ exception }}
{{ trace}}

{% if output %}
  * Captured stdout:

  .. code-block::

{{ output }}
{% endif %}

{% if error %}
  * Captured stderr:

  .. code-block::

{{ error }}
{% endif %}

Context
-------
{% if config.runtime %}
 * Runtime Config

 .. code-block:: yaml

{{ config.runtime }}
{% endif %}

{% if config.local %}
 * Local Config

 .. code-block:: yaml

{{ config.local }}
{% endif %}

{% if config.global %}
 * Global Config

 .. code-block:: yaml

{{ config.global }}
{% endif %}

{% if context %}
 * Manipulated profiles

  // for profile in context

 .. code-block:: json

{{ profile }}

  // endfor
{% endif %}
"""


def generate_cli_dump(
    reported_error: str,
    catched_exception: Exception,
    stdout: log.Logger,
    stderr: log.Logger,
) -> None:
    """Generates the dump of the current snapshot of the CLI

    In particular this yields the dump template with the following information:

        1. Version of the Perun
        2. Called command and its parameters
        3. Caught exception
        4. Traceback of the exception
        5. Whole profile (if used)

    :param reported_error: string representation of the catched exception / error
    :param catched_exception: exception that led to the dump
    :param stdout: logged stdout
    :param stderr: logged stderr
    """
    stdout.flush()
    stderr.flush()

    global CLI_DUMP_TEMPLATE
    if not CLI_DUMP_TEMPLATE:
        env = jinja2.Environment(
            trim_blocks=True,
            line_statement_prefix="//",
        )
        CLI_DUMP_TEMPLATE = env.from_string(CLI_DUMP_TEMPLATE_STRING)
    version_delimiter = re.compile(r"[=><;~! ]")

    def split_requirement(requirement: str) -> str:
        """Helper function for splitting requirement and its required version"""
        split = re.split(version_delimiter, requirement)
        return split[0] if len(split) > 0 else ""

    reqs = {split_requirement(req) for req in metadata.requires("perun-toolsuite") or []}

    dump_directory = pcs.get_safe_path(os.getcwd())
    dump_timestamp = timestamps.timestamp_to_str(time.time()).replace(" ", "-").replace(":", "-")
    dump_file = os.path.join(dump_directory, f"dump-{dump_timestamp}.rst")

    stdout.log.seek(0)
    stderr.log.seek(0)

    ctx = {
        "\n".join(
            [
                " " * 4 + line
                for line in json.dumps(p.serialize(), indent=2, sort_keys=True).split("\n")
            ]
        )
        for p in config.runtime().safe_get("context.profiles", [])
        if "origin" in p.keys()
    }
    config.runtime().set("context.profiles", [])

    output = CLI_DUMP_TEMPLATE.render(
        {
            "env": {
                "perun": perun.__version__,
                "os": {
                    "type": os.environ.get("OSTYPE", "???"),
                    "distro": platform.platform(()),  # type: ignore
                    "arch": os.environ.get("HOSTTYPE", "???"),
                    "shell": os.environ.get("SHELL", "???"),
                },
                "python": {
                    "version": sys.version.replace("\n", ""),
                    "packages": [
                        f"{req.name} ({req.version})"
                        for req in metadata.distributions()
                        if hasattr(req, "name") and req.name in reqs and req.name != ""
                    ],
                },
            },
            "command": " ".join(["perun"] + sys.argv[1:]),
            "output": common_kit.escape_ansi(
                "".join([" " * 4 + line for line in stdout.log.readlines()])
            ),
            "error": common_kit.escape_ansi(
                "".join([" " * 4 + line for line in stderr.log.readlines()])
            ),
            "exception": reported_error,
            "trace": "\n".join(
                [
                    " " * 4 + t
                    for t in "".join(traceback.format_tb(catched_exception.__traceback__)).split(
                        "\n"
                    )
                ]
            ),
            "config": {
                "runtime": streams.yaml_to_string(config.runtime().data),
                "local": (
                    ""
                    if ".perun" not in dump_directory
                    else streams.yaml_to_string(config.local(dump_directory).data)
                ),
                "global": streams.yaml_to_string(config.shared().data),
            },
            "context": ctx,
        }
    )

    with open(dump_file, "w") as dump_handle:
        dump_handle.write(output)
    log.minor_status("Saved dump", status=f"{log.path_style(dump_file)}")


def set_optimization(_: click.Context, param: click.Argument, value: str) -> str:
    """Callback for enabling or disabling optimization pipelines or methods.

    :param _: click context
    :param param: the click parameter
    :param value: value of the parameter
    :return: the value
    """
    from perun.collect.trace.optimizations.optimization import Optimization

    # Set the optimization pipeline
    if param.human_readable_name == "optimization_pipeline":
        Optimization.set_pipeline(value)
    # Enable certain optimization method
    elif param.human_readable_name == "optimization_on":
        for method in value:
            Optimization.enable_optimization(method)
    # Disable certain optimization method
    elif param.human_readable_name == "optimization_off":
        for method in value:
            Optimization.disable_optimization(method)
    return value


def set_optimization_param(_: click.Context, __: click.Argument, value: str) -> str:
    """Set parameter value for optimizations

    :param _: click context
    :param __: the click parameter
    :param value: value of the parameter
    :return: the value
    """
    # TODO: to be fixed when lazy-loader is used in the entire codebase
    from perun.collect.trace.optimizations.optimization import Optimization

    for param in value:
        # Process all parameters as 'parameter: value' tuples
        opt_name, opt_value = param[0], param[1]
        if Optimization.params.add_cli_parameter(opt_name, opt_value) is None:
            raise click.BadParameter(
                f"Invalid value '{opt_value}' for optimization parameter '{opt_name}'"
            )
    return value


def set_optimization_cache(_: click.Context, __: click.Option, value: str) -> None:
    """Enable or disable the usage of optimization and collection cache.

    :param _: click context
    :param __: the click parameter
    :param value: value of the parameter
    """
    from perun.collect.trace.optimizations.optimization import Optimization

    Optimization.resource_cache = not value


def reset_optimization_cache(_: click.Context, __: click.Option, value: str) -> None:
    """Remove the cache entries for the optimization, thus forcing them to recompute the cached
    data.

    :param _: click context
    :param __: the click parameter
    :param value: value of the parameter
    """
    from perun.collect.trace.optimizations.optimization import Optimization

    Optimization.reset_cache = value


def set_call_graph_type(_: click.Context, __: click.Argument, value: str) -> None:
    """Set the selected Call Graph type to be used for optimizations.

    :param _: click context
    :param __: the click parameter
    :param value: value of the parameter
    """
    from perun.collect.trace.optimizations.optimization import Optimization

    Optimization.call_graph_type = collect_structs.CallGraphTypes(value)


def configure_metrics(_: click.Context, __: click.Option, value: tuple[str, str]) -> None:
    """Set the temp file and ID for the collected metrics.

    :param _: click context
    :param __: the click parameter
    :param value: value of the parameter
    """
    if value[0] and value[1]:
        metrics.Metrics.configure(value[0], value[1])


def get_supported_module_names(package: str) -> list[str]:
    """Obtains list of supported modules supported by the package.

    Contains the hard-coded dictionary of packages and their supported values. This simply does
    a key lookup and returns the list of supported values.

    This was originally dynamic collection of all the modules through beautiful module iteration,
    which was shown to be completely uselessly slower than this hardcoded table. Since I assume, that
    new modules will be registered very rarely, I think it is ok to have it implemented like this.

    Note: This is used in CLI, and as of Click 7.0 all subcommands have underscores (_)
    replaced by (-). While this is useful in CLI, Perun needs the underscore,
    so use Unit.sanitize_module_name to replace the dash back.

    :param package: name of the package for which we want to obtain the supported modules
                        one of ('vcs', 'collect', 'postprocess')
    :return: list of names of supported modules for the given package
    """
    if package not in ("vcs", "collect", "postprocess", "view"):
        log.error(f"trying to call get_supported_module_names with incorrect package '{package}'")
    return {
        "vcs": ["git", "svs"],
        "collect": ["trace", "memory", "time", "complexity", "bounds", "kperf"],
        "postprocess": [
            "clusterizer",
            "normalizer",
            "regression-analysis",
            "regressogram",
            "moving-average",
            "kernel-regression",
        ],
        "view": ["bars", "flamegraph", "flow", "heapmap", "raw", "scatter", "tableof"],
    }[package]
