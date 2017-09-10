"""Scatter plot representation of the profile"""

import click

import perun.utils.log as log
import perun.utils.cli_helpers as cli_helpers
import perun.utils.bokeh_helpers as bokeh_helpers

from perun.utils.helpers import pass_profile


def process_title(ctx, _, value):
    pass


@click.command()
@click.option('--of', '-o', 'of_key', default='amount', nargs=1,
              show_default=True, type=str,
              is_eager=True, callback=cli_helpers.process_resource_key_param,
              help="Data source for the scatter plot, i.e. what will be displayed on Y axis.")
@click.option('--per', '-p', 'per_key', default='structure-unit-size', nargs=1,
              show_default=True, type=str,
              is_eager=True, callback=cli_helpers.process_resource_key_param,
              help="Keys that will be displayed on X axis of the scatter plot.")
@click.option('--for-uid', '-Fu', 'for_uid', multiple=True, metavar="<for_resource_uid>",
              help=("Plot only specific resources identified by the uid keys. "
                    "If not specified, all uid keys will be plotted."))
@click.option('--except-uid', '-Xu', 'except_uid', multiple=True, metavar="<except_resource_uid>",
              help=("Plot all resources except those identified by the uid keys. "
                    "If used together with '--for_uid', then '--for_uid' is applied first in "
                    "construction of the resulting filter."))
@click.option('--with-models', '-w', 'with_models', is_flag=True, default=False, is_eager=True,
              help="Also plot regression models if profile contains them.")
@click.option('--for-model', '-Fm', 'for_model', multiple=True, type=(str, str, str),
              help=("Plot only specific models identified by the <method model uid> list. "
                    "Value '*' serves as a wildcard. "))
@click.option('--except-model', '-Xm', 'except_model', multiple=True, type=(str, str, str),
              help=("Plot all models except those specified by the <method model uid> list. "
                    "Value '*' serves as a wildcard. Similarly to uid filter, the '--for-model' "
                    "has precedence in filter construction."))
# Bokeh graph specific
@click.option('--filename', '-f', default="scatter_plot.html", metavar="<html>",
              help="Outputs the graph to the file specified by filename.")
@click.option('--x-axis-label', '-xl', metavar="<text>", default=None,
              callback=cli_helpers.process_bokeh_axis_title,
              help="Label on the X axis of the scatter plot.")
@click.option('--y-axis-label', '-yl', metavar="<text>", default=None,
              callback=cli_helpers.process_bokeh_axis_title,
              help="Label on the Y axis of the scatter plot.")
@click.option('--graph-title', '-gt', metavar="<text>", default=None, callback=process_title,
              help="Title of the scatter plot.")
@click.option('--view-in-browser', '-v', default=False, is_flag=True,
              help="Will show the graph in browser.")
@pass_profile
def scatter_plot(profile, filename, view_in_browser, **kwargs):
    pass
