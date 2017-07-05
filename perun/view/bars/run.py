"""Bar's graphs interpretation of the profiles."""

import bokeh.core.enums as enums
import click

import perun.view.bars.factory as bars_factory
import perun.utils.log as log
import perun.utils.cli_helpers as cli_helpers
import perun.utils.bokeh_helpers as bokeh_helpers

from perun.utils.helpers import pass_profile
from perun.utils.exceptions import InvalidParameterException

__author__ = 'Radim Podola'
__coauthored__ = 'Tomas Fiedor'


def process_title(ctx, _, value):
    """Processes default value for the title.

    If the value supplied from CLI is non-None, it is returned as it is. Otherwise, we try to
    create some optimal name for the graph ourselves. We do this according to already processed
    parameters as follows:

      Func of 'of-key' per 'per-key' 'cummulated' by 'by-key'

    Arguments:
        ctx(click.Context): called context of the process
        value(object): value that is being processed ad add to parameter

    Returns:
        object: either value (if it is non-None) or default title of the graph
    """
    if not value:
        # Construct default title of the graph
        return "{} of '{}' per '{}' {} by {}".format(
            ctx.params['func'].capitalize(), ctx.params['of_key'], ctx.params['per_key'],
            ctx.params['cummulation_type'], ctx.params['by_key']
        )
    return value


@click.command()
@click.argument('func', required=False, default='sum', metavar="<aggregation_function>",
                type=click.Choice(list(map(str, enums.Aggregation))))
@click.option('--of', '-o', 'of_key', nargs=1, required=True, metavar="<of_resource_key>",
              is_eager=True, callback=cli_helpers.process_resource_key_param,
              help="Source of the data for the bars, i.e. what will be displayed on Y axis.")
@click.option('--per', '-p', 'per_key', default='snapshots', nargs=1, metavar="<per_resource_key>",
              is_eager=True, callback=cli_helpers.process_resource_key_param,
              help="Keys that will be displayed on X axis of the bar graph.")
@click.option('--by', '-b', 'by_key', default=None, nargs=1, metavar="<by_resource_key>",
              is_eager=True, callback=cli_helpers.process_resource_key_param,
              help="Will stack the bars according to the given key.")
@click.option('--stacked', '-s', 'cummulation_type', flag_value='stacked', default=True,
              is_eager=True,
              help="If set to true, then values will be stacked up by <resource_key> specified by"
                   " option --by.")
@click.option('--grouped', '-g', 'cummulation_type', flag_value='grouped',
              is_eager=True,
              help="If set to true, then values will be grouped up by <resource_key> specified by"
                   " option --by.")
# Bokeh graph specific
@click.option('--filename', '-f', default="bars.html", metavar="<html>",
              help="Outputs the graph to the file specified by filename.")
@click.option('--x-axis-label', '-xl', metavar="<text>", default=None,
              callback=cli_helpers.process_bokeh_axis_title,
              help="Label on the X axis of the bar graph.")
@click.option('--y-axis-label', '-yl', metavar="<text>", default=None,
              callback=cli_helpers.process_bokeh_axis_title,
              help="Label on the Y axis of the bar graph.")
@click.option('--graph-title', '-gt', metavar="<text>", default=None, callback=process_title,
              help="Title of the bars graph.")
@click.option('--view-in-browser', '-v', default=False, is_flag=True,
              help="Will show the graph in browser.")
@pass_profile
def bars(profile, filename, view_in_browser, **kwargs):
    """
    Display of the resources in bar format.

    \b
                            <graph_title>
                    `
                    -         .::.                ````````
                    `         :&&:                ` # \\  `
                    -   .::.  ::::        .::.    ` @  }->  <by>
                    `   :##:  :##:        :&&:    ` & /  `
    <func>(<of>)    -   :##:  :##:  .::.  :&&:    ````````
                    `   ::::  :##:  :&&:  ::::
                    -   :@@:  ::::  ::::  :##:
                    `   :@@:  :@@:  :##:  :##:
                    +````||````||````||````||````

                                <per>

    Bar graphs shows aggregation of resources according to the given criteria. Each bar
    displays <func> of resources from <of> key (e.g. sum of amounts, average of amounts, etc.)
    per each <per> key (e.g. per each snapshot). Moreover, the graphs can either be (i) stacked,
    where the different values of <by> key are shown above each other, or (ii) grouped, where the
    different values of <by> key are shown next to each other.

    Graphs are displayed using the Bokeh library and can be further customized by adding custom
    labels for axis, custom graph title and different graph width. Each graph can be loaded from
    the template according to the template file.
    """
    try:
        bokeh_helpers.process_profile_to_graphs(
            bars_factory, profile, filename, view_in_browser, **kwargs
        )
    except AttributeError as attr_error:
        log.error("while creating graph: {}".format(str(attr_error)))
    except InvalidParameterException as ip_error:
        log.error(str(ip_error))
