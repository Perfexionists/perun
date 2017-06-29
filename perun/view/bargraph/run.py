"""Bar's graphs interpretation of the profiles."""

import click
import bokeh.core.enums as enums
import bokeh.plotting as plotting
import bokeh.layouts as layouts

import perun.core.logic.query as query
import perun.utils.log as log
import perun.view.bargraph.factory as bar_graphs

from perun.utils.helpers import pass_profile

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
    else:
        return value


def process_axis_title(ctx, param, value):
    """Processes default value for axes.

    If the value supplied from CLI is non-None, it is returned as it is. Otherwise, we try to
    create some optimal axis name. We do this according to the already processed parameters and
    we either use 'per_key' or 'of_key'.

    Arguments:
        ctx(click.Context): called context of the process
        param(click.Option): called option (either x or y axis)
        value(object): given value for the the option param

    Returns:
        object: either value (if it is non-None) or default legend for given axis
    """
    if value:
        return value
    elif param.human_readable_name.startswith('x'):
        return ctx.params['per_key']
    elif param.human_readable_name.startswith('y'):
        return ctx.params['of_key']
    else:
        log.error("internal perun error")


def process_key_param(ctx, param, value):
    """

    Arguments:
        ctx(click.Context): called context of the process
        param(click.Option): called option that takes a valid key from profile as a parameter
        value(object): given value for the option param

    Returns:
        object: value or raises bad parameter

    Raises:
        click.BadParameter: if the value is invalid for the profile
    """
    if param.human_readable_name == 'per_key' and value == 'snapshots':
        return value

    # Validate the keys, if it is one of the set
    valid_keys = set(query.all_resource_fields_of(ctx.parent.params['profile']))
    if value not in valid_keys:
        error_msg_ending = ", snaphots" if param.human_readable_name == 'per_key' else ""
        raise click.BadParameter("invalid choice: {}. (choose from {})".format(
            value, ", ".join(str(vk) for vk in valid_keys) + error_msg_ending
        ))
    return value


@click.command()
# TODO: Add choice of pandas/bokeh functions
@click.argument('func', required=False, default='sum', metavar="<aggregation_function>",
                type=click.Choice(map(str, enums.Aggregation)))
# TODO: Add choice of keys of the profile
@click.option('--of', '-o', 'of_key', nargs=1, required=True, metavar="<of_resource_key>",
              is_eager=True, callback=process_key_param,
              help="Source of the data for the bars, i.e. what will be displayed on Y axis.")
@click.option('--per', '-p', 'per_key', default='snapshots', nargs=1, metavar="<per_resource_key>",
              is_eager=True, callback=process_key_param,
              help="Keys that will be displayed on X axis of the bar graph.")
@click.option('--by', '-b', 'by_key', default=None, nargs=1, metavar="<by_resource_key>",
              is_eager=True, callback=process_key_param,
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
@click.option('--x-axis-label', '-xl', metavar="<text>", default=None, callback=process_axis_title,
              help="Label on the X axis of the bar graph.")
@click.option('--y-axis-label', '-yl', metavar="<text>", default=None, callback=process_axis_title,
              help="Label on the Y axis of the bar graph.")
@click.option('--graph-title', '-gt', metavar="<text>", default=None, callback=process_title,
              help="Title of the graph.")
@click.option('--view-in-browser', '-v', default=False, is_flag=True,
              help="Will show the graph in browser.")
@pass_profile
def bargraph(profile, filename, view_in_browser, **kwargs):
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
    bar_graph = bar_graphs.create_from_params(profile, **kwargs)
    output = layouts.column([bar_graph], sizing_mode="stretch_both")
    plotting.output_file(filename)

    if view_in_browser:
        plotting.show(output)
    else:
        plotting.save(output, filename)
