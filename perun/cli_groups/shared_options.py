"""Groups of options used by multiple CLI commands across different modules."""

from __future__ import annotations

# Standard Imports
import functools
from typing import Any, Callable

# Third-Party Imports
import click

# Perun Imports
from perun.logic import config
from perun.utils.common import cli_kit, common_kit
from perun.utils.structs.view_structs import DEFAULT_SQUASH_RE, FlameGraphSettings


def flamegraph_cli_options(command: Callable[..., Any]) -> Callable[..., Any]:
    """A set of common options for customizing generated flame graphs.

    :param command: a click command to extend with the options.
    :return: the click command augmented with the flame graph options.
    """

    @click.option(
        "--flamegraph-width",
        type=int,
        default=FlameGraphSettings.DefaultImageWidth,
        help="Specifies the width of the flamegraph images in pixels. This option is forwarded to "
        "the flamegraph.pl/.py script.",
    )
    @click.option(
        "--flamegraph-height",
        type=int,
        help="Specifies the height of each flamegraph frame in pixels. This option is forwarded to "
        "the flamegraph.pl/.py script.",
    )
    @click.option(
        "--flamegraph-minwidth",
        type=str,
        default=FlameGraphSettings.DefaultMinWidth,
        help="Filter out fast functions in flamegraphs. May be specified either in pixels (integer "
        "or float value) or as a percentage of time if suffixed with '%'. This option is "
        "forwarded to the flamegraph.pl/.py script.",
    )
    @click.option(
        "--flamegraph-fonttype",
        type=str,
        help="Specifies the font type to use in flamegraphs. This option is forwarded to the "
        "flamegraph.pl/.py script.",
    )
    @click.option(
        "--flamegraph-fontsize",
        type=int,
        help="Specifies the font size of text in flamegraphs. This option is forwarded to the "
        "flamegraph.pl/.py script.",
    )
    @click.option(
        "--flamegraph-bgcolors",
        type=str,
        help="Specifies the background colors for flamegraphs. This option is forwarded to the "
        "flamegraph.pl/.py script.",
    )
    @click.option(
        "--flamegraph-colors",
        type=str,
        help="Specifies the color theme for flamegraphs. This option is forwarded to the "
        "flamegraph.pl/.py script.",
    )
    @click.option(
        "--flamegraph-inverted",
        is_flag=True,
        default=False,
        help="Draws icicle graphs instead of flame graphs. This option is forwarded to the "
        "flamegraph.pl/.py script.",
    )
    @click.option(
        "--flamegraph-use-perl-scripts",
        is_flag=True,
        default=False,
        help="Use the canonical Perl scripts for generating flame graphs. Otherwise, our custom "
        "Python scripts will be used.",
    )
    @functools.wraps(command)
    def wrapper_flamegraph_options(*args, **kwargs):
        return command(*args, **kwargs)

    return wrapper_flamegraph_options


def profile_postprocess_cli_options(command: Callable[..., Any]) -> Callable[..., Any]:
    """A set of common options for postprocessing Perun/folded profiles for visualisations.

    :param command: a click command to extend with the options.
    :return: the click command augmented with the postprocessing options.
    """

    @click.option(
        "--squash/--no-squash",
        is_flag=True,
        default=True,
        help="Enables or disables squashing recursive function calls into a single stack frame "
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
    @functools.wraps(command)
    def wrapper_folded_postprocess_options(*args, **kwargs):
        return command(*args, **kwargs)

    return wrapper_folded_postprocess_options


def profile_aggregation_cli_option(command: Callable[..., Any]) -> Callable[..., Any]:
    """An aggregation option for input profiles.

    :param command: a click command to extend with the aggregation option.
    :return: the click command augmented with the aggregation option.
    """

    @click.option(
        "--aggregate-by",
        "-a",
        default=common_kit.Aggregations.default_name(),
        type=click.Choice(common_kit.Aggregations.supported()),
        callback=cli_kit.set_config_option_from_flag(config.runtime, "profile.aggregation"),
        help=f"Aggregates the resources in profiles by given statistical function "
        f"(default={common_kit.Aggregations.default_name()}).",
    )
    @functools.wraps(command)
    def wrapper_aggregation_option(*args, **kwargs):
        return command(*args, **kwargs)

    return wrapper_aggregation_option
