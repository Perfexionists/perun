"""Group of CLI commands used for difference visualization and analysis of profiles."""

from __future__ import annotations

# Standard Imports
import functools
from typing import Any, Callable

# Third-Party Imports
import click

# Perun Imports
from perun.logic import config
from perun.utils.common import cli_kit
from perun.utils.structs.diff_structs import (
    HeaderDisplayStyle,
    Config,
    FG_DEFAULT_IMAGE_WIDTH,
    FG_DEFAULT_MIN_WIDTH,
)


def common_flamegraph_options(command: Callable[..., Any]) -> Callable[..., Any]:
    """A set of common options for customizing generated flame graphs.

    :param command: a click command to extend with the options.
    :return: the click command augmented with the flame graph options.
    """

    # TODO: generalize such that (possibly some) recursive functions may be squashed as well.
    @click.option(
        "--no-squash-unknown",
        is_flag=True,
        default=False,
        help="Do not squash [unknown] frames in flamegraph into a single frame.",
    )
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
    @functools.wraps(command)
    def wrapper_common_flamegraph_options(*args, **kwargs):
        return command(*args, **kwargs)

    return wrapper_common_flamegraph_options


@click.group("showdiff")
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
@click.option(
    "--aggregate-by",
    "-a",
    default="median",
    type=click.Choice(["sum", "min", "max", "avg", "mean", "med", "median"]),
    callback=cli_kit.set_config_option_from_flag(config.runtime, "profile.aggregation"),
    help="Aggregates the resources in profiles by given statistical function (default=median).",
)
@click.option(
    "--offline",
    "-o",
    callback=cli_kit.set_config_option_from_flag(config.runtime, "showdiff.offline"),
    is_flag=True,
    default=False,
    help="Creates self-contained outputs usable in offline environments (default=False).",
)
@click.option(
    "--display-style",
    "-d",
    type=click.Choice(HeaderDisplayStyle.supported()),
    default=HeaderDisplayStyle.default(),
    callback=cli_kit.set_config_option_from_flag(config.runtime, "showdiff.display_style"),
    help="Selects the display style of profile header. The 'full' option displays all provided "
    "headers, while the 'diff' option shows only headers with different values "
    f"(default={HeaderDisplayStyle.default()}).",
)
@click.pass_context
def showdiff_group(_: click.Context, **__: Any) -> None:
    """Interprets the difference of selected two profiles.

    Looks up the given profiles and interprets it using the selected
    visualization technique. Some of the techniques outputs either to
    terminal (using ``ncurses``) or generates HTML files, which can be
    browsable in the web browser (using ``bokeh`` library). Refer to concrete
    techniques for concrete options and limitations.

    The shown profiles will be looked up in the following steps:

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

        perun showdiff -m HEAD~1 0@i 1@i report
    """


@showdiff_group.command()
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
@click.pass_context
def short(ctx: click.Context, *_: Any, **kwargs: Any) -> None:
    """Creates a CLI difference table of profiles."""
    assert ctx.parent is not None and f"impossible happened: {ctx} has no parent"
    profile_list = ctx.parent.params["profile_list"]

    # Lazy load the view_diff module and execute the command
    from perun import view_diff

    view_diff.compare_profiles(profile_list[0], profile_list[1], **kwargs)


@showdiff_group.command()
@click.option("--output-file", "-o", help="Sets the output file (default=automatically generated).")
@click.option(
    "--minimize",
    "-m",
    is_flag=True,
    help="Minimizes the traces, folds the recursive calls, hides the generic types.",
)
@common_flamegraph_options
@click.pass_context
def flamegraph(ctx: click.Context, *_: Any, **kwargs: Any) -> None:
    """Creates a flame graph (alternatively icicle graph) difference grid of the supplied profiles
    accompanied by a set of automatic (and possibly user-defined as well) statistics.
    """
    assert ctx.parent is not None and f"impossible happened: {ctx} has no parent"
    profile_list = ctx.parent.params["profile_list"]

    # Lazy load the view_diff module and execute the command
    from perun import view_diff

    view_diff.generate_flamegraph_difference(profile_list[0], profile_list[1], **kwargs)


@showdiff_group.command()
@click.option("--output-file", "-o", help="Sets the output file (default=automatically generated).")
@click.option(
    "--filter-by-relative",
    "-fr",
    nargs=1,
    type=click.FLOAT,
    default=Config().DefaultRelativeThreshold,
    help="Filters records based on the relative increase wrt the target. It filters values that "
    f"are lesser or equal than [FLOAT] (default={Config().DefaultRelativeThreshold}).",
)
@click.option(
    "--top-n",
    "-tn",
    nargs=1,
    type=click.INT,
    default=Config().DefaultTopN,
    help=f"Filters how many top traces will be recorded per uid (default={Config().DefaultTopN}). ",
)
@click.option(
    "--minimize",
    "-m",
    is_flag=True,
    help="Minimizes the traces, folds the recursive calls, hides the generic types.",
)
@click.option(
    "--chatbot-url",
    "-c",
    type=str,
    metavar="<API URL>",
    help="Enables chatbot support for a report using the specified API URL.",
)
@common_flamegraph_options
@click.pass_context
def report(ctx: click.Context, *_: Any, **kwargs: Any) -> None:
    """Creates a comprehensive interactive difference report of two profiles that combines multiple
    visualizations and data tables.
    """
    assert ctx.parent is not None and f"impossible happened: {ctx} has no parent"
    profile_list = ctx.parent.params["profile_list"]

    # Lazy load the view_diff module and execute the command
    from perun import view_diff

    view_diff.generate_report(profile_list[0], profile_list[1], **kwargs)
