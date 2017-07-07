"""Simple queries over the profiles."""

import click
import sys
import perun.utils.log as log
import perun.view.alloclist.queries as qrs
import perun.view.alloclist.pretty_output as pretty
from perun.utils.helpers import pass_profile
from perun.utils.exceptions import IncorrectProfileFormatException

__author__ = 'Radim Podola'

SUPPORTED_MODES = ("all", "top", "most", "sum", "func")


def validate_timestamp_parameter(ctx, param, value):
    """Validates the timestamp parameter, that it was stated with correct functions.

    If the parameter was called with mode for which it has no effect, the warning is issued.

    Arguments:
        ctx(click.Context): called click context
        param(click.Option): parameter (either --from-time or --to-time)
        value(object): value for the given parameter

    Returns:
        object: value of the validated parameter
    """
    mode = ctx.params['mode']
    param_name = param.human_readable_name
    param_cmd_name = param.human_readable_name.replace('_', '-')

    if param_cmd_name in " ".join(sys.argv) and mode != 'all':
        log.warn("value '{}' for parameter '{}' has no effect in '{}' mode".format(
            value, param_name, mode
        ))

    return value


def validate_limit_to_parameter(ctx, _, value):
    """Validates that the limit to is called in top/most/sum mode otherwise issues warning

    Arguments:
        ctx(click.Context): called click context
        _(click.Option): parameter (either --from-time or --to-time)
        value(object): value for the given parameter

    Returns:
        object: value of the validated parameter
    """
    mode = ctx.params['mode']

    if '--limit-to' in " ".join(sys.argv) and mode not in ('top', 'most', 'sum'):
        log.warn("--limit-to option has no effect in '{}' mode".format(mode))

    return value


def validate_func_parameter(ctx, _, value):
    """Validates that the func is called for func parameter (do'h!).

    Arguments:
        ctx(click.Context): called click context
        _(click.Option): parameter (either --from-time or --to-time)
        value(object): value for the given parameter

    Returns:
        object: value of the validated parameter
    """
    mode = ctx.params['mode']

    if '--function' in " ".join(sys.argv):
        if mode != 'func':
            log.warn("--function option has no effect in '{}' mode".format(mode))
    elif mode == 'func':
        print(sys.argv)
        raise click.BadParameter("missing specified function for list. Use --function=<f>.")

    return value


@click.command()
@click.argument('mode', nargs=1, type=str, is_eager=True)
@click.option('--limit-to', '-t', default=10, metavar="<int>", callback=validate_limit_to_parameter,
              help="Will limit the displayed list to <int> records.")
@click.option('--from-time', type=float, metavar="<timestamp>",
              callback=validate_timestamp_parameter,
              help="Will limit the displayed list starting from the <timestamp> (in seconds).")
@click.option('--to-time', type=float, metavar="<timestamp>",
              callback=validate_timestamp_parameter,
              help="Will limit the displayed list until the <timestamp> (in seconds).")
@click.option('--function', type=str, metavar="<func>", callback=validate_func_parameter,
              help="Specifies the name of the function for the 'func' mode.")
@click.option('--all-occurrences', '-a', 'check_trace', is_flag=True, default=False,
              help="Includes all of the occurrences of the function (even the partial participation"
                   "in the call traces) in the list of allocations.")
@pass_profile
def alloclist(profile, mode, **kwargs):
    """
    Memstat is a set of simple queries over memory profiles, with collected allocation info.

    \b
                    #1 malloc: 100B at 0x31341343
                      \u2514 malloc  in  /dir/subdir/file.c:32
                        \u2514 main  in /dir/subdir/file.c:12

    \b
                    #2 calloc: 12B at 0x31411341
                      \u2514 malloc in /dir/subdir/file.c:1

    Memstat contains several predefined functions for aggregated basic information about allocations
    within the profile---list of allocations, tops, sums, etc.---and serves as a base for future
    extension.

    \b
    Currently the following modes are supported:
        1. 'most'  lists records sorted by the frequency of allocations of memory they made
        2. 'sum'   lists records sorted by the overall amount of allocated memory they used
        3. 'func'  lists records limited to the specified functions
        4. 'all'   lists records in given time interval sorted by timestamp
        5. 'top'   lists records sorted by amount of allocated memory
    """
    inter_func = getattr(qrs, "get_%s" % mode)
    if inter_func:
        try:
            output = inter_func(profile, **kwargs)
        except Exception as exception:
            raise IncorrectProfileFormatException('', str(exception))
    else:
        raise click.BadParameter("could not find the function for mode {}".format(
            mode
        ))

    print(pretty.get_profile_info(profile))
    if output:
        print(output)
