"""Bar's graphs interpretation of the profiles."""

import click
import bokeh.plotting as plotting

import perun.view.bargraph.factory as bar_graphs

from perun.utils.helpers import pass_profile

__author__ = 'Radim Podola'
__coauthored__ = 'Tomas Fiedor'


@click.command()
# TODO: Add choice of pandas/bokeh functions
@click.argument('func', required=False, default='sum', metavar="<aggregation_function>")
# TODO: Add choice of keys of the profile
@click.option('--of', '-o', 'of_key', nargs=1, required=True, metavar="<of_resource_key>",
              help="Source of the data for the bars, i.e. what will be displayed on Y axis.")
@click.option('--per', '-p', 'per_key', default='snapshots', nargs=1, metavar="<per_resource_key>",
              help="Keys that will be displayed on X axis of the bar graph.")
@click.option('--by', '-b', 'by_key', default=None, nargs=1, metavar="<by_resource_key>",
              help="Will stack the bars according to the given key.")
@click.option('--stacked', '-s', 'cummulation_type', flag_value='stacked', default=True,
              help="If set to true, then values will be stacked up by <resource_key> specified by"
                   " option --by.")
@click.option('--grouped', '-g', 'cummulation_type', flag_value='grouped',
              help="If set to true, then values will be grouped up by <resource_key> specified by"
                   " option --by.")
# Bokeh graph specific
@click.option('--filename', '-f', default="bars.html", metavar="<html>",
              help="Outputs the graph to the file specified by filename.")
@click.option('--graph-width', '-w', default=1200,
              help="Changes the width of the generated Graph.")
@click.option('--x-axis-label', '-xl', metavar="<text>", default='TODO:',
              help="Label on the X axis of the bar graph.")
@click.option('--y-axis-label', '-yl', metavar="<text>", default='TODO:',
              help="Label on the Y axis of the bar graph.")
@click.option('--graph-title', '-gt', metavar="<text>", default='TODO:',
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
    plotting.output_file(filename)

    if view_in_browser:
        plotting.show(bar_graph)
    else:
        plotting.save(bar_graph, filename)
