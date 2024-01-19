"""Flow graphs visualization of the profiles."""
from __future__ import annotations

# Standard Imports
from typing import Any

# Third-Party Imports
import click

# Perun Imports
from perun.utils import log
from perun.utils.common import cli_kit, common_kit, view_kit
from perun.utils.exceptions import InvalidParameterException
import perun.profile.factory as profile_factory
import perun.view.flow.factory as flow_factory


def process_title(ctx: click.Context, _: click.Option, value: str) -> str:
    """Processes the default value for the flow graph title.

    If the value supplied from CLI is non-None, it is returned as it is. Otherwise, we try to
    create some optimal name for the graph ourselves. We do this according to already processed
    parameters as follows:

      Func of 'of-key' through 'through-key' for each 'by-key' (stacked)

    :param click.Context ctx: called context of the process
    :param object _: unused parameter
    :param object value: value that is being processed ad add to parameter
    :returns object: either value (if it is non-None) or default title of the graph
    """
    return value or (
        f"{ctx.params['func'].capitalize()} "
        f"of '{ctx.params['of_key']}' "
        f"through '{ctx.params['through_key']}' "
        f"for each {ctx.params['by_key']} "
        f"{ctx.params['stacked']*'(stacked)'}"
    )


@click.command()
@click.argument(
    "func",
    required=False,
    default="sum",
    metavar="<aggregation_function>",
    type=click.Choice(common_kit.AGGREGATIONS),
    is_eager=True,
)
@click.option(
    "--of",
    "-o",
    "of_key",
    nargs=1,
    required=True,
    metavar="<of_resource_key>",
    is_eager=True,
    callback=cli_kit.process_resource_key_param,
    help=(
        "Sets key that is source of the data for the flow,"
        " i.e. what will be displayed on Y axis, e.g. the amount of"
        " resources."
    ),
)
@click.option(
    "--through",
    "-t",
    "through_key",
    nargs=1,
    required=False,
    metavar="<through_key>",
    is_eager=True,
    callback=cli_kit.process_continuous_key,
    default="snapshots",
    help=(
        "Sets key that is source of the data value, i.e. the"
        " independent variable, like e.g. snapshots or size of the"
        " structure."
    ),
)
@click.option(
    "--by",
    "-b",
    "by_key",
    nargs=1,
    required=True,
    metavar="<by_resource_key>",
    is_eager=True,
    callback=cli_kit.process_resource_key_param,
    help=(
        "For each <by_resource_key> one graph will be output, e.g."
        " for each subtype or for each location of resource."
    ),
)
@click.option(
    "--stacked",
    "-s",
    is_flag=True,
    default=False,
    help=(
        "Will stack the y axis values for different <by> keys"
        " on top of each other. Additionally shows the sum of the values."
    ),
)
@click.option(
    "--accumulate/--no-accumulate",
    default=True,
    help="Will accumulate the values for all previous values of X axis.",
)
# Other options and arguments
@click.option(
    "--filename",
    "-f",
    default="flow.html",
    metavar="<html>",
    help="Sets the outputs for the graph to the file.",
)
@click.option(
    "--x-axis-label",
    "-xl",
    metavar="<text>",
    default=None,
    callback=cli_kit.process_bokeh_axis_title,
    help="Sets the custom label on the X axis of the flow graph.",
)
@click.option(
    "--y-axis-label",
    "-yl",
    metavar="<text>",
    default=None,
    callback=cli_kit.process_bokeh_axis_title,
    help="Sets the custom label on the Y axis of the flow graph.",
)
@click.option(
    "--graph-title",
    "-gt",
    metavar="<text>",
    default=None,
    callback=process_title,
    help="Sets the custom title of the flow graph.",
)
@click.option(
    "--view-in-browser",
    "-v",
    default=False,
    is_flag=True,
    help="The generated graph will be immediately opened in the browser (firefox will be used).",
)
@profile_factory.pass_profile
# Fixme: Consider breaking this to two
def flow(
    profile: profile_factory.Profile, filename: str, view_in_browser: bool, **kwargs: Any
) -> None:
    """Customizable interpretation of resources using the flow format.

    .. _Bokeh: https://bokeh.pydata.org/en/latest/

    \b
      * **Limitations**: `none`.
      * **Interpretation style**: graphical, textual
      * **Visualization backend**: Bokeh_, ncurses

    `Flow` graph shows the values resources depending on the independent
    variable as basic graph. For each group of resources identified by unique
    value of ``<by>`` key, one graph shows the dependency of ``<of>`` values
    aggregated by ``<func>`` depending on the ``<through>`` key. Moreover, the
    values can either be accumulated (this way when displaying the value of 'n'
    on x-axis, we accumulate the sum of all values for all m < n) or stacked,
    where the graphs are output on each other and then one can see the overall
    trend through all the groups and proportions between each of the group.

    Bokeh_ library is the current interpretation backend, which generates HTML
    files, that can be opened directly in the browser. Resulting graphs can be
    further customized by adding custom labels for axes, custom graph title or
    different graph width.

    Example 1. The following will show the average amount (in this case
    the function running time) of each function depending on the size of the
    structure over which the given function operated::

        perun show 0@i flow mean --of 'amount' --per 'structure-unit-size'
            --accumulated --by 'uid'

    The example output of the bars is as follows::

        \b
                                        <graph_title>
                                `
                                -                      ______    ````````
                                `                _____/          ` # \\  `
                                -               /          __    ` @  }->  <by>
                                `          ____/      ____/      ` & /  `
                <func>(<of>)    -      ___/       ___/           ````````
                                `  ___/    ______/       ____
                                -/  ______/        _____/
                                `__/______________/
                                +````||````||````||````||````

                                          <through>

    Refer to :ref:`views-flow` for more thorough description and example of
    `flow` interpretation possibilities.
    """
    try:
        view_kit.process_profile_to_graphs(
            flow_factory, profile, filename, view_in_browser, **kwargs
        )
    except (InvalidParameterException, AttributeError) as iap_error:
        log.error(f"while creating flow graph: {str(iap_error)}")
