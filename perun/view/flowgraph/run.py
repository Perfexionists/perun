"""Flow graphs visualization of the profiles."""

import bokeh.core.enums as enums
import click

import perun.utils.bokeh_helpers as bokeh_helpers
import perun.utils.cli_helpers as cli_helpers
import perun.core.profile.converters as converters
import perun.view.flowgraph.bokeh_flow_graph as bokeh_graphs
import perun.view.flowgraph.ncurses_flow_graph as curses_graphs

from perun.utils.helpers import pass_profile

__author__ = 'Radim Podola'
__coauthored__ = 'Tomas Fiedor'


def process_title(ctx, _, value):
    """Processes the default value for the flow graph title.

    If the value supplied from CLI is non-None, it is returned as it is. Otherwise, we try to
    create some optimal name for the graph ourselves. We do this according to already processed
    parameters as follows:

      Func of 'of-key' through 'through-key' for each 'by-key' (stacked)

    Arguments:
        ctx(click.Context): called context of the process
        value(object): value that is being processed ad add to parameter

    Returns:
        object: either value (if it is non-None) or default title of the graph
    """
    if not value:
        # Construct default title of the graph
        return "{} of '{}' through '{}' for each {} {}".format(
            ctx.params['func'].capitalize(), ctx.params['of_key'], ctx.params['through_key'],
            ctx.params['by_key'], ctx.params['stacked']*"(stacked)"
        )
    else:
        return value


@click.command()
@click.argument('func', required=False, default='sum', metavar="<aggregation_function>",
                type=click.Choice(map(str, enums.Aggregation)))
@click.option('--of', '-o', 'of_key', nargs=1, required=True, metavar="<of_resource_key>",
              is_eager=True, callback=cli_helpers.process_resource_key_param,
              help="Source of the data for the graphs, i.e. what will be displayed on Y axis.")
@click.option('--through', '-t', 'through_key', nargs=1, required=False, metavar="<through_key>",
              is_eager=True, callback=cli_helpers.process_resource_key_param, default='snapshots',
              help="Independent variable on the X axis, values will be grouped by this key.")
@click.option('--by', '-b', 'by_key', nargs=1, required=True, metavar="<by_resource_key>",
              is_eager=True, callback=cli_helpers.process_resource_key_param,
              help="For each of the value of the <by_resource_key> a graph will be output")
@click.option('--stacked', '-s', is_flag=True, default=False,
              help="Will stack the values according to the <by_resource_key> showing the overall.")
@click.option('--accumulate/--no-accumulate', default=True,
              help="Will accumulate the values for all previous values on x axis.")
# Other options and arguments
@click.option('--use-terminal', '-t', is_flag=True, default=False,
              help="Shows flow graph in the terminal (using ncurses).")
@click.option('--filename', '-f', default="flow.html", metavar="<html>",
              help="Outputs the graph to file specified by filename.")
@click.option('--x-axis-label', '-xl', metavar="<text>", default=None,
              callback=cli_helpers.process_bokeh_axis_title,
              help="Label on the X axis of the bar graph.")
@click.option('--y-axis-label', '-yl', metavar="<text>", default=None,
              callback=cli_helpers.process_bokeh_axis_title,
              help="Label on the Y axis of the bar graph.")
@click.option('--graph-title', '-gt', metavar="<text>", default=None, callback=process_title,
              help="Title of the graph.")
@click.option('--view-in-browser', '-v', default=False, is_flag=True,
              help="Will show the graph in browser.")
@pass_profile
# Fixme: Consider breaking this to two
def flowgraph(profile, use_terminal, filename, view_in_browser, **kwargs):
    """
    Display of the resources in flow format.

    \b
                            <graph_title>
                    `
                    -                      ______     ````````
                    `                _____/           ` # \\  `
                    -               /          __     ` @  }->  <by>
                    `          ____/      ____/       ` & /  `
    <func>(<of>)    -      ___/       ___/            ````````
                    `  ___/    ______/       ____
                    -/  ______/        _____/
                    `__/______________/
                    +````||````||````||````||````

                              <through>

    Flow graphs shows the dependency of the values through the other independent variable.
    For each group of resources identified by <by> key, a graph of dependency of <of> values
    aggregated by <func> depending on the <through> key is depicted. Moreover, the values
    can either be accumulated (this way when displaying the value of 'n' on x axis, we accumulate
    the sum of all values for all m < n) or stacked, where the graphs are output on each other
    and then one can see the overall trend through all the groups and proportions between
    each of the group.

    Graphs are displayed using the Bokeh library and can be further customized by adding custom
    labels for axis, custom graph title and different graph width. Each graph can be loaded from
    the template according to the template file.
    """
    if use_terminal:
        heap_map = converters.create_heap_map(profile)
        curses_graphs.flow_graph(heap_map)
    else:
        flow_graph = bokeh_graphs.create_from_params(profile, **kwargs)
        bokeh_helpers.save_graphs_in_column([flow_graph], filename, view_in_browser)
