"""Group of CLI commands used for difference visualization and analysis of profiles."""

from __future__ import annotations

# Standard Imports
import functools
import pathlib
from typing import Any, Callable, TYPE_CHECKING

# Third-Party Imports
import click

# Perun Imports
from perun.cli_groups import shared_options
from perun.logic import config
from perun.utils.common import cli_kit
from perun.utils.structs.diff_structs import (
    DEFAULT_FUNCTION_THRESHOLD,
    DEFAULT_MAX_FUNCTION_TRACES,
    DEFAULT_TOP_DIFFS,
    DEFAULT_TRACE_THRESHOLD,
    HeaderDisplayStyle,
)
from perun.view_diff import flamegraph, short
from perun.view_diff.report import native, folded

if TYPE_CHECKING:
    from perun.profiles.native import Profile


def perun_profile_list_options(command: Callable[..., Any]) -> Callable[..., Any]:
    """CLI argument and option that load Perun profiles.

    :param command: a click command to extend with the Perun profile loading.
    :return: the augmented click command.
    """

    @click.argument(
        "profile_list",
        required=True,
        nargs=2,
        metavar="<profile>",
        callback=cli_kit.lookup_list_of_profiles_callback,
    )
    @click.option(
        "--minor",
        "-m",
        nargs=1,
        default=None,
        is_eager=True,
        callback=cli_kit.lookup_minor_version_callback,
        help="Finds the profiles in the index of minor version [HASH]",
    )
    @functools.wraps(command)
    def wrapper_from_perun_profiles(*args, **kwargs):
        return command(*args, **kwargs)

    return wrapper_from_perun_profiles


def common_html_options(command: Callable[..., Any]) -> Callable[..., Any]:
    """A set of common options for showdiff commands that generate an HTML file.

    :param command: a click command to extend with the options.
    :return: the click command augmented with the HTML options.
    """

    @click.option(
        "--output-path",
        "-o",
        help="Sets the output file path (default=automatically generated name in the current "
        "working directory).",
    )
    @click.option(
        "--offline",
        callback=cli_kit.set_config_option_from_flag(config.runtime, "showdiff.offline"),
        is_flag=True,
        default=False,
        help="Creates a self-contained output usable in offline environments (default=False).",
    )
    @click.option(
        "--default-theme",
        "-th",
        type=click.Choice(["light", "dark", "mono"], case_sensitive=False),
        help="Determines which theme will be set as the default theme.",
    )
    @click.option(
        "--chatbot-url",
        "-c",
        type=str,
        metavar="<API URL>",
        help="Enables chatbot support for a report using the specified API URL.",
    )
    @click.option(
        "--chatbot-prompt-context",
        "-p",
        type=str,
        multiple=True,
        help="Adds an additional context to the chatbot conversation on top of the default initial "
        "context. Multiple contexts may be specified, each either as a string or a file with the "
        "'.prompt' suffix.",
    )
    @functools.wraps(command)
    def wrapper_common_flamegraph_options(*args, **kwargs):
        return command(*args, **kwargs)

    return wrapper_common_flamegraph_options


def flamegraph_diff_cli_options(command: Callable[..., Any]) -> Callable[..., Any]:
    """A set of options for generating diff flame graphs.

    :param command: a click command to extend with the options.
    :return: the click command augmented with the flame graph options.
    """

    @click.option(
        "--flamegraph-normalize/--flamegraph-no-normalize",
        is_flag=True,
        default=True,
        help="Normalize the baseline sample counts when creating differential flame graphs using "
        "the formula '(baseline_count * target_sum / baseline_sum)'. This colors the flame graph "
        "frames with hues that respect the change in the total consumptions between two profiles. "
        "This option is forwarded to the difffolded.pl/.py script.",
    )
    @click.option(
        "--flamegraph-parallelize/--flamegraph-no-parallelize",
        is_flag=True,
        default=True,
        help="Generate flamegraph grids using multiple processes. Note that this may consume too"
        "much peak memory for very large perf profiles.",
    )
    @functools.wraps(command)
    def wrapper_flamegraph_diff_options(*args, **kwargs):
        return command(*args, **kwargs)

    return wrapper_flamegraph_diff_options


@click.group("showdiff")
@shared_options.profile_aggregation_cli_option
def showdiff_group(**_: Any) -> None:
    """Interprets the difference of baseline and target profiles.

    Looks up the given profiles and interprets them using the selected visualization technique.
    Some of the techniques output either to terminal (using ``ncurses``) or generate HTML files,
    which can be opened in the web browser. Refer to concrete techniques for concrete options and
    limitations.

    There are in general two different categories of supported profiles: Perun-native profiles
    and external profiles. Refer to concrete commands for details on their difference visualizations
    and supported profile formats.
    """


@showdiff_group.command("short")
@perun_profile_list_options
@click.option(
    "-n", "--top-n", type=click.INT, help="Prints top [INT] records (default=10).", default=10
)
@click.option(
    "-f",
    "--filter",
    "filters",
    nargs=2,
    multiple=True,
    help="Filters the result to concrete column and concrete value.",
)
@click.option(
    "-g",
    "--group-by",
    default="origin",
    type=click.STRING,
    help="Names the each profile by its particular option (default=origin).",
)
def short_diff(profile_list: tuple[Profile, Profile], *_: Any, **kwargs: Any) -> None:
    """Creates a difference table of profiles in the terminal.

    Supports only perun-native profiles.
    """
    short.compare_profiles(*profile_list, **kwargs)


@showdiff_group.command("flamegraph")
@perun_profile_list_options
@common_html_options
@shared_options.flamegraph_cli_options
@flamegraph_diff_cli_options
@shared_options.profile_postprocess_cli_options
def flamegraph_diff(profile_list: tuple[Profile, Profile], *_: Any, **kwargs: Any) -> None:
    """Creates a flame graph (or icicle graph) difference grid from perun-native profiles.

    The grid consists of baseline, target, baseline-target diff, and target-baseline diff flame
    graphs. The grid is further accompanied by a set of automatically-derived,and possibly
    user-defined as well, statistics.

    Perun-native profiles will be looked up in the following steps:

        1. If [PROFILE] is in form ``i@i`` (i.e, an `index tag`), then `ith`
           record registered in the minor version <hash> index will be shown.

        2. If [PROFILE] is in form ``i@p`` (i.e., an `pending tag`), then
           `ith` profile stored in ``.perun/jobs`` will be shown.

        3. [PROFILE] is looked-up within the minor version <hash> index for a
           match. In case the <profile> is registered there, it will be shown.

        4. [PROFILE] is looked-up within the ``.perun/jobs`` directory. In case
           there is a match, the found profile will be shown.

        5. Otherwise, the directory is walked for any match. Each found match
           is asked for confirmation by user.

    Tags consider the sorted order as specified by the options
    :ckey:`format.sort_profiles_by` and :ckey:`format.sort_profiles_order`.

    Example 1. The following command will show the flamegraph grid of first two profiles
    registered at index of ``HEAD~1`` commit::

        perun showdiff flamegraph -m HEAD~1 0@i 1@i

    Supports only perun-native profiles.
    """
    flamegraph.generate_flamegraph_difference(*profile_list, **kwargs)


@showdiff_group.group("report")
@click.option(
    "--function-threshold",
    "-ft",
    type=click.FLOAT,
    default=DEFAULT_FUNCTION_THRESHOLD,
    help="Exclude functions that consume (inclusively) less than X% of the total resources in both "
    f"baseline and target (default={DEFAULT_FUNCTION_THRESHOLD}%).",
)
@click.option(
    "--traces-threshold",
    "-rt",
    type=click.FLOAT,
    default=DEFAULT_TRACE_THRESHOLD,
    help="Exclude traces that consume (inclusively) less than X% of the total resources in both "
    f"baseline and target (default={DEFAULT_TRACE_THRESHOLD}%).",
)
@click.option(
    "--max-function-traces",
    type=click.INT,
    default=DEFAULT_MAX_FUNCTION_TRACES,
    help=f"Limit the number of most expensive traces stored per function "
    f"(default={DEFAULT_MAX_FUNCTION_TRACES}).",
)
@click.option(
    "--top-diffs",
    type=click.INT,
    default=DEFAULT_TOP_DIFFS,
    help=f"Limit the number of overall most expensive traces and functions displayed in the "
    f"Overview (default={DEFAULT_TOP_DIFFS}).",
)
@click.option(
    "--display-style",
    "-d",
    type=click.Choice(HeaderDisplayStyle.supported()),
    default=HeaderDisplayStyle.default(),
    callback=cli_kit.set_config_option_from_flag(config.runtime, "showdiff.display_style"),
    help="The 'full' option displays all Environment headers, while the 'diff' option shows "
    f"only headers with different values (default={HeaderDisplayStyle.default()}).",
)
@click.option(
    "--link",
    "-l",
    nargs=2,
    metavar="<URL, NAME>",
    multiple=True,
    help="Attaches the URL address and its display name to the links section in the report.",
)
@common_html_options
@shared_options.flamegraph_cli_options
@flamegraph_diff_cli_options
@shared_options.profile_postprocess_cli_options
@click.pass_context
def report_group(ctx: click.Context, **kwargs: Any) -> None:
    """Creates a comprehensive interactive difference report of two profiles.

    The report combines multiple visualizations and tabular views of the data.

    Supports both perun-native and some external profiles.
    """
    ctx.obj = kwargs


@report_group.command("native")
@perun_profile_list_options
@click.pass_context
def report_native(
    ctx: click.Context,
    profile_list: tuple[Profile, Profile],
    *_: Any,
    **kwargs: Any,
) -> None:
    """Creates an HTML difference report from perun-native baseline and target profiles.

    The difference reports contains comparison of the environment, profile metadata, profile stats,
    and performance data using flamegraphs and tables.

    Perun-native profiles will be looked up in the following steps:

        1. If [PROFILE] is in form ``i@i`` (i.e, an `index tag`), then `ith`
           record registered in the minor version <hash> index will be shown.

        2. If [PROFILE] is in form ``i@p`` (i.e., an `pending tag`), then
           `ith` profile stored in ``.perun/jobs`` will be shown.

        3. [PROFILE] is looked-up within the minor version <hash> index for a
           match. In case the <profile> is registered there, it will be shown.

        4. [PROFILE] is looked-up within the ``.perun/jobs`` directory. In case
           there is a match, the found profile will be shown.

        5. Otherwise, the directory is walked for any match. Each found match
           is asked for confirmation by user.

    Tags consider the sorted order as specified by the options
    :ckey:`format.sort_profiles_by` and :ckey:`format.sort_profiles_order`.

    Example 1. The following command will show the difference first two profiles
    registered at index of ``HEAD~1`` commit::

        perun showdiff report native -m HEAD~1 0@i 1@i
    """
    kwargs.update(ctx.obj)
    native.generate_report_from_native_profiles(*profile_list, **kwargs)


@report_group.command("folded")
@click.argument(
    "baseline",
    required=True,
    type=str,
    metavar="<BASELINE>",
)
@click.argument(
    "target",
    required=True,
    type=str,
    metavar="<TARGET>",
)
@click.option(
    "--baseline-dir",
    "-bd",
    type=click.Path(resolve_path=True, readable=True),
    default=pathlib.Path.cwd(),
    help="A directory where to look for baseline files (e.g., profiles, stats, machine info, ...) "
    "that are provided as relative paths. Absolute paths ignore this directory (default=./).",
)
@click.option(
    "--target-dir",
    "-td",
    type=click.Path(resolve_path=True, readable=True),
    default=pathlib.Path.cwd(),
    help="A directory where to look for target files (e.g., profiles, stats, machine info, ...) "
    "that are provided as relative paths. Absolute paths ignore this directory (default=./).",
)
@click.option(
    "--profiled-resource",
    type=str,
    default="samples",
    help="Specifies the resource type measured in the profile, e.g., 'samples' or 'CPU cycles' "
    "(default=samples).",
)
@click.option(
    "--baseline-machine-info",
    "-bi",
    type=click.Path(),
    default="",
    help="Path to a baseline machine info JSON file. Use the `utils/generate_machine_info.sh` "
    "script to generate the machine info file (default=generated from local machine).",
)
@click.option(
    "--target-machine-info",
    "-ti",
    type=click.Path(),
    default="",
    help="Path to a target machine info JSON file. Use the `utils/generate_machine_info.sh` "
    "script to generate the machine info file (default=generated from local machine).",
)
@click.option(
    "--baseline-stats-headers",
    "-bs",
    nargs=1,
    default=None,
    metavar="[STAT_HEADER+]",
    help="Specify the stats headers associated with the baseline profile. "
    "See the command help for more details on the stats header format.",
)
@click.option(
    "--target-stats-headers",
    "-ts",
    nargs=1,
    default=None,
    metavar="[STAT_HEADER+]",
    help="Specify the stats headers associated with the target profile. "
    "See the command help for more details on the stats header format.",
)
@click.option(
    "--baseline-metadata",
    "-bm",
    multiple=True,
    metavar="['KEY|VALUE|[DESCRIPTION]'] or [FILE.json]",
    help="Specify metadata entry (entries) associated with the baseline profile. Either a string "
    "'key|value[|description]' describing a single entry, or a JSON file with possibly multiple "
    "metadata entries. The option may be specified multiple times.",
)
@click.option(
    "--target-metadata",
    "-tm",
    multiple=True,
    metavar="['KEY|VALUE|[DESCRIPTION]'] or [FILE.json]",
    help="Specify metadata entry (entries) associated with the target profile. Either a string "
    "'key|value[|description]' describing a single entry, or a JSON file with possibly multiple "
    "metadata entries. The option may be specified multiple times.",
)
@click.option(
    "--baseline-label",
    "-bl",
    default="",
    help="An optional custom label to associate with the baseline profile (default='').",
)
@click.option(
    "--target-label",
    "-tl",
    default="",
    help="An optional custom label to associate with the target profile (default='').",
)
@click.option(
    "--baseline-collector-cmd",
    "-bcc",
    default="perf",
    help="The baseline collector command and its parameters, e.g., ``perf record`` (default=perf).",
)
@click.option(
    "--target-collector-cmd",
    "-tcc",
    default="perf",
    help="The target collector command and its parameters, e.g., ``perf record`` (default=perf).",
)
@click.option(
    "--baseline-cmd",
    "-bc",
    default="",
    help="The baseline profiled command and its parameters, e.g., ``./mybin`` or ``ls ./subdir`` "
    "(default='').",
)
@click.option(
    "--target-cmd",
    "-tc",
    default="",
    help="The target profiled command and its parameters, e.g., ``./mybin`` or ``ls ./subdir`` "
    "(default='').",
)
@click.pass_context
def report_folded(ctx: click.Context, baseline: str, target: str, **kwargs: Any) -> None:
    """Creates an HTML difference report from external folded profiles.

    The difference reports contains comparison of the environment, profile metadata, profile stats,
    and performance data using flamegraphs and tables.

    This report expects one or more baseline and target folded profiles with per-trace measurements,
    e.g., perf folded or eBPF folded profiles.

    The trace profiles may be specified as

        'profile_path[,<exit_code>[,<stat_value>]+]'

    where 'profile_path' is the path to the trace profile (possibly gzipped), 'exit_code' is the
    exit code of the profile collection, and 'stat_value's are values corresponding to the
    specified stats headers (see below). Both the exit code and stat values are optional.

    Alternatively, when there are multiple baseline or target profiles that should be aggregated,
    they may be specified as a CSV file

        'file_path.csv'

    where the CSV file must contain a header on its first row, and all other rows specify the
    profiles, i.e.,

        Profile,Exit_code[,stat-header1]+
        profile_path[,<exit code>[,<stat value>]+]

    Each profile may have the so-called stats associated with it. Stat headers may be specified
    either using a command line option, or directly in the CSV files. A stat header is specified as

        'name[|comparison_type[|unit[|aggregate_by[|description]]]]'

    where

     - the '|' symbol acts as a delimiter;

     - 'name' identifies the stat in the report (required);

     - 'comparison_type' is used to compare baseline and target values. May be one of
       'higher_is_better', 'lower_is_better', 'equality', or 'auto' (default='auto');

     - 'unit' specifies the stat units, e.g., MB or ms (default='#');

     - 'aggregate_by' specifies the aggregation function to use (default='median'); and

     - 'description' is shown as a tooltip for the stat (default=comparison_type).

    """
    kwargs.update(ctx.obj)
    folded.generate_report_from_folded_profiles(baseline, target, **kwargs)
