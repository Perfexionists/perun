"""Bar's graphs interpretation of the profiles."""

import click

import perun.view.bars.factory as bars_factory
import perun.utils.log as log
import perun.utils.cli_helpers as cli_helpers
import perun.utils.bokeh_helpers as bokeh_helpers
import perun.utils.helpers as helpers

from perun.profile.factory import pass_profile
from perun.utils.exceptions import InvalidParameterException


__author__ = 'Radim Podola'
__coauthored__ = 'Tomas Fiedor'


def process_title(ctx, _, value):
    """Processes default value for the title.

    If the value supplied from CLI is non-None, it is returned as it is. Otherwise, we try to
    create some optimal name for the graph ourselves. We do this according to already processed
    parameters as follows:

      Func of 'of-key' per 'per-key' 'cummulated' by 'by-key'

    :param click.Context ctx: called context of the process
    :param object _: unused parameter
    :param object value: value that is being processed ad add to parameter
    :returns object: either value (if it is non-None) or default title of the graph
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
                type=click.Choice(helpers.AGGREGATIONS))
@click.option('--of', '-o', 'of_key', nargs=1, required=True, metavar="<of_resource_key>",
              is_eager=True, callback=cli_helpers.process_resource_key_param,
              help="Sets key that is source of the data for the bars,"
                   " i.e. what will be displayed on Y axis.")
@click.option('--per', '-p', 'per_key', default='snapshots', nargs=1, metavar="<per_resource_key>",
              is_eager=True, callback=cli_helpers.process_resource_key_param,
              help="Sets key that is source of values displayed on X axis of the bar graph.")
@click.option('--by', '-b', 'by_key', default=None, nargs=1, metavar="<by_resource_key>",
              is_eager=True, callback=cli_helpers.process_resource_key_param,
              help="Sets the key that will be used either for stacking or"
              " grouping of values")
@click.option('--stacked', '-s', 'cummulation_type', flag_value='stacked', default=True,
              is_eager=True,
              help="Will stack the values by <resource_key> specified by"
                   " option --by.")
@click.option('--grouped', '-g', 'cummulation_type', flag_value='grouped',
              is_eager=True,
              help="Will stack the values by <resource_key> specified by"
                   " option --by.")
# Bokeh graph specific
@click.option('--filename', '-f', default="bars.html", metavar="<html>",
              help="Sets the outputs for the graph to the file.")
@click.option('--x-axis-label', '-xl', metavar="<text>", default=None,
              callback=cli_helpers.process_bokeh_axis_title,
              help="Sets the custom label on the X axis of the bar graph.")
@click.option('--y-axis-label', '-yl', metavar="<text>", default=None,
              callback=cli_helpers.process_bokeh_axis_title,
              help="Sets the custom label on the Y axis of the bar graph.")
@click.option('--graph-title', '-gt', metavar="<text>", default=None, callback=process_title,
              help="Sets the custom title of the bars graph.")
@click.option('--view-in-browser', '-v', default=False, is_flag=True,
              help="The generated graph will be immediately opened in the"
              " browser (firefox will be used).")
@pass_profile
def bars(profile, filename, view_in_browser, **kwargs):
    """Customizable interpretation of resources using the bar format.

    .. _Bokeh: https://bokeh.pydata.org/en/latest/

    \b
      * **Limitations**: `none`.
      * **Interpretation style**: graphical
      * **Visualization backend**: Bokeh_

    `Bars` graph shows the aggregation (e.g. sum, count, etc.) of resources of
    given types (or keys). Each bar shows ``<func>`` of resources from ``<of>``
    key (e.g. sum of amounts, average of amounts, count of types, etc.) per
    each ``<per>`` key (e.g. per each snapshot, or per each type).  Moreover,
    the graphs can either be (i) stacked, where the different values of
    ``<by>`` key are shown above each other, or (ii) grouped, where the
    different values of ``<by>`` key are shown next to each other. Refer to
    :pkey:`resources` for examples of keys that can be used as ``<of>``,
    ``<key>``, ``<per>`` or ``<by>``.

    Bokeh_ library is the current interpretation backend, which generates HTML
    files, that can be opened directly in the browser. Resulting graphs can be
    further customized by adding custom labels for axes, custom graph title or
    different graph width.

    Example 1. The following will display the sum of sum of amounts of all
    resources of given for each subtype, stacked by uid (e.g. the locations in
    the program)::

        perun show 0@i bars sum --of 'amount' --per 'subtype' --stacked --by 'uid'

    The example output of the bars is as follows::

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

    Refer to :ref:`views-bars` for more thorough description and example of
    `bars` interpretation possibilities.
    """
    try:
        bokeh_helpers.process_profile_to_graphs(
            bars_factory, profile, filename, view_in_browser, **kwargs
        )
    except AttributeError as attr_error:
        import traceback
        traceback.print_tb(attr_error.__traceback__)
        log.error("while creating bar graph: {}".format(str(attr_error)))
    except InvalidParameterException as ip_error:
        log.error("while creating bar graph: {}".format(str(ip_error)))
