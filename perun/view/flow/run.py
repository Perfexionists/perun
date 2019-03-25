"""Flow graphs visualization of the profiles."""

import click

import demandimport
with demandimport.enabled():
    import bokeh.core.enums as enums

import perun.profile.convert as convert
import perun.utils.bokeh_helpers as bokeh_helpers
import perun.utils.cli_helpers as cli_helpers
import perun.utils.log as log
import perun.view.flow.bokeh_factory as flow_factory
import perun.view.flow.ncurses_factory as curses_graphs
from perun.utils.exceptions import InvalidParameterException
from perun.utils.helpers import pass_profile

__author__ = 'Radim Podola'
__coauthored__ = 'Tomas Fiedor'


def process_title(ctx, _, value):
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
    if not value:
        # Construct default title of the graph
        return "{} of '{}' through '{}' for each {} {}".format(
            ctx.params['func'].capitalize(), ctx.params['of_key'], ctx.params['through_key'],
            ctx.params['by_key'], ctx.params['stacked']*"(stacked)"
        )
    return value


@click.command()
@click.argument('func', required=False, default='sum', metavar="<aggregation_function>",
                type=click.Choice(list(map(str, enums.Aggregation))), is_eager=True)
@click.option('--of', '-o', 'of_key', nargs=1, required=True, metavar="<of_resource_key>",
              is_eager=True, callback=cli_helpers.process_resource_key_param,
              help="Sets key that is source of the data for the flow,"
              " i.e. what will be displayed on Y axis, e.g. the amount of"
              " resources.")
@click.option('--through', '-t', 'through_key', nargs=1, required=False, metavar="<through_key>",
              is_eager=True, callback=cli_helpers.process_continuous_key, default='snapshots',
              help="Sets key that is source of the data value, i.e. the"
              " independent variable, like e.g. snapshots or size of the"
              " structure.")
@click.option('--by', '-b', 'by_key', nargs=1, required=True, metavar="<by_resource_key>",
              is_eager=True, callback=cli_helpers.process_resource_key_param,
              help="For each <by_resource_key> one graph will be output, e.g."
              " for each subtype or for each location of resource.")
@click.option('--stacked', '-s', is_flag=True, default=False,
              help="Will stack the y axis values for different <by> keys"
              " on top of each other. Additionaly shows the sum of the values.")
@click.option('--accumulate/--no-accumulate', default=True,
              help="Will accumulate the values for all previous values of X axis.")
# Other options and arguments
@click.option('--use-terminal', '-ut', is_flag=True, default=False,
              help="Shows flow graph in the terminal using ncurses library.")
@click.option('--filename', '-f', default="flow.html", metavar="<html>",
              help="Sets the outputs for the graph to the file.")
@click.option('--x-axis-label', '-xl', metavar="<text>", default=None,
              callback=cli_helpers.process_bokeh_axis_title,
              help="Sets the custom label on the X axis of the flow graph.")
@click.option('--y-axis-label', '-yl', metavar="<text>", default=None,
              callback=cli_helpers.process_bokeh_axis_title,
              help="Sets the custom label on the Y axis of the flow graph.")
@click.option('--graph-title', '-gt', metavar="<text>", default=None, callback=process_title,
              help="Sets the custom title of the flow graph.")
@click.option('--view-in-browser', '-v', default=False, is_flag=True,
              help="The generated graph will be immediately opened in the"
              " browser (firefox will be used).")
@pass_profile
# Fixme: Consider breaking this to two
def flow(profile, use_terminal, filename, view_in_browser, **kwargs):
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
    on x axis, we accumulate the sum of all values for all m < n) or stacked,
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
            --acumulated --by 'uid'

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
    if use_terminal:
        heap_map = convert.to_heap_map_format(profile)
        curses_graphs.flow_graph(heap_map)
    else:
        try:
            bokeh_helpers.process_profile_to_graphs(
                flow_factory, profile, filename, view_in_browser, **kwargs
            )
        except AttributeError as attr_error:
            log.error("while creating flow graph: {}".format(str(attr_error)))
        except InvalidParameterException as ip_error:
            log.error("while creating flow graph: {}".format(str(ip_error)))
