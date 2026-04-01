"""Group of CLI commands used for difference visualization and analysis of profiles."""

from __future__ import annotations

# Standard Imports
import functools
import pathlib
from typing import Any, Callable, TYPE_CHECKING

# Third-Party Imports
import click

# Perun Imports
from perun.logic import config
from perun.utils.common import cli_kit
from perun.utils.structs.diff_structs import (
    HeaderDisplayStyle,
    Config,
    DEFAULT_AGGREGATE_FUNC,
    FG_DEFAULT_IMAGE_WIDTH,
    FG_DEFAULT_MIN_WIDTH,
    DEFAULT_MAX_FUNCTION_TRACES,
    DEFAULT_TOP_DIFFS,
    DEFAULT_FUNCTION_THRESHOLD,
    DEFAULT_TRACE_THRESHOLD,
    DEFAULT_SQUASH_RE,
)

if TYPE_CHECKING:
    from perun import profile


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
    # TODO: Add support for color theme in flamegraph diff as well.
    @click.option(
        "--default-theme",
        "-th",
        type=click.Choice(["light", "dark", "mono"], case_sensitive=False),
        help="Determines which theme will be set as the default theme.",
    )
    # TODO: add support for a chatbot in flamegraph diff as well.
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


def common_flamegraph_options(command: Callable[..., Any]) -> Callable[..., Any]:
    """A set of common options for customizing generated flame graphs.

    :param command: a click command to extend with the options.
    :return: the click command augmented with the flame graph options.
    """

    @click.option(
        "--flamegraph-width",
        type=int,
        default=FG_DEFAULT_IMAGE_WIDTH,
        help="Specifies the width of the flamegraph images in pixels. This option is forwarded to "
        "the flamegraph.pl script.",
    )
    @click.option(
        "--flamegraph-height",
        type=int,
        help="Specifies the height of each flamegraph frame in pixels. This option is forwarded to "
        "the flamegraph.pl script.",
    )
    # TODO: remove the default
    @click.option(
        "--flamegraph-minwidth",
        type=str,
        default=FG_DEFAULT_MIN_WIDTH,
        help="Filter out fast functions in flamegraphs. May be specified either in pixels (integer "
        "or float value) or as a percentage of time if suffixed with '%'. This option is "
        "forwarded to the flamegraph.pl script.",
    )
    @click.option(
        "--flamegraph-fonttype",
        type=str,
        help="Specifies the font type to use in flamegraphs. This option is forwarded to the "
        "flamegraph.pl script.",
    )
    @click.option(
        "--flamegraph-fontsize",
        type=int,
        help="Specifies the font size of text in flamegraphs. This option is forwarded to the "
        "flamegraph.pl script.",
    )
    @click.option(
        "--flamegraph-bgcolors",
        type=str,
        help="Specifies the background colors for flamegraphs. This option is forwarded to the "
        "flamegraph.pl script.",
    )
    @click.option(
        "--flamegraph-colors",
        type=str,
        help="Specifies the color theme for flamegraphs. This option is forwarded to the "
        "flamegraph.pl script.",
    )
    @click.option(
        "--flamegraph-inverted",
        is_flag=True,
        default=False,
        help="Draws icicle graphs instead of flame graphs. This option is forwarded to the "
        "flamegraph.pl script.",
    )
    @click.option(
        "--flamegraph-parallelize/--flamegraph-no-parallelize",
        is_flag=True,
        default=True,
        help="Generate flamegraph grids using multiple processes. Note that this may consume too"
        "much peak memory for very large perf profiles.",
    )
    @functools.wraps(command)
    def wrapper_common_flamegraph_options(*args, **kwargs):
        return command(*args, **kwargs)

    return wrapper_common_flamegraph_options


@click.group("showdiff")
@click.option(
    "--aggregate-by",
    "-a",
    default=DEFAULT_AGGREGATE_FUNC,
    type=click.Choice(["sum", "min", "max", "avg", "mean", "med", "median"]),
    callback=cli_kit.set_config_option_from_flag(config.runtime, "profile.aggregation"),
    help="Aggregates the resources in profiles by given statistical function (default=median).",
)
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


@showdiff_group.command()
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
def short(profile_list: tuple[profile.Profile, profile.Profile], *_: Any, **kwargs: Any) -> None:
    """Creates a difference table of profiles in the terminal.

    Supports only perun-native profiles.
    """
    # Lazy load the view_diff module and execute the command
    from perun import view_diff

    view_diff.compare_profiles(*profile_list, **kwargs)


# TODO: split into 'native' and 'folded' similarly to report
@showdiff_group.command()
@perun_profile_list_options
# TODO: unify with 'hide-generics'
@click.option(
    "--minimize",
    "-m",
    is_flag=True,
    help="Minimizes the traces, folds the recursive calls, hides the generic types.",
)
# TODO: unify with 'squash'
@click.option(
    "--no-squash-unknown",
    is_flag=True,
    default=False,
    help="Do not squash [unknown] frames in flamegraph into a single frame (default=False).",
)
@common_html_options
@common_flamegraph_options
def flamegraph(
    profile_list: tuple[profile.Profile, profile.Profile], *_: Any, **kwargs: Any
) -> None:
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
    # Lazy load the view_diff module and execute the command
    from perun import view_diff

    view_diff.generate_flamegraph_difference(*profile_list, **kwargs)


# TODO: we still keep most of the old report options until we refactor 'report native' and can
#  merge the old options with the new ones.
@showdiff_group.group("report")
# TODO: replace with new filtering parameters.
@click.option(
    "--filter-by-relative",
    "-fr",
    nargs=1,
    type=click.FLOAT,
    default=Config().DefaultRelativeThreshold,
    help="Filters records based on the relative increase wrt the target. It filters values that "
    f"are lesser or equal than [FLOAT] (default={Config().DefaultRelativeThreshold}).",
)
# TODO: replace with 'function-threshold'
@click.option(
    "--top-n",
    "-tn",
    nargs=1,
    type=click.INT,
    default=Config().DefaultTopN,
    help=f"Filters how many top traces will be recorded per uid (default={Config().DefaultTopN}). ",
)
# TODO: replace with 'hide-generics'
@click.option(
    "--minimize",
    "-m",
    is_flag=True,
    help="Minimizes the traces, folds the recursive calls, hides the generic types.",
)
# TODO: replace with new squash parameters
@click.option(
    "--no-squash-unknown",
    is_flag=True,
    default=False,
    help="Do not squash [unknown] frames in flamegraph into a single frame (default=False).",
)
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
    "--squash/--no-squash",
    is_flag=True,
    default=True,
    help="Enables or disables squashing recursive function calls into a single flamegraph frame "
    "(default=True)",
)
@click.option(
    "--squash-regex",
    type=str,
    default=DEFAULT_SQUASH_RE,
    help="A regex specifying function names to squash if squashing is enabled "
    f"(default={DEFAULT_SQUASH_RE})",
)
@click.option(
    "--hide-generics",
    is_flag=True,
    default=False,
    help="Hide generic types, e.g., template specifications, in function names (default=False).",
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
@common_flamegraph_options
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
def native(
    ctx: click.Context,
    profile_list: tuple[profile.Profile, profile.Profile],
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
    # Lazy load the view_diff module and execute the command
    from perun import view_diff

    kwargs.update(ctx.obj)
    view_diff.generate_report_from_native(*profile_list, **kwargs)


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
    # Lazy load the view_diff module and execute the command
    from perun import view_diff

    kwargs.update(ctx.obj)
    view_diff.generate_report_from_folded(baseline, target, **kwargs)
