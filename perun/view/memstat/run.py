"""Simple queries over the profiles."""

import click
import perun.view.memstat.queries as qrs
import perun.view.memstat.pretty_output as pretty
from perun.utils.helpers import pass_profile
from perun.utils.exceptions import IncorrectProfileFormatException

__author__ = 'Radim Podola'

SUPPORTED_MODES = ("list", "top", "most", "sum", "func")


@click.command()
@click.argument('mode', nargs=1, type=str)
@click.option('--limit-to', '-t', default=10,
              help="Defines a count of the records that will be printed.")
@click.option('--from-time', type=float,
              help="Defines timestamp in the timeline of printed records.")
@click.option('--to-time', type=float,
              help="Defines timestamp in the timeline of printed records.")
@click.option('--function',
              help="Defines name of the function to search for.")
@click.option('--all-occurrences', '-a', 'check_trace', is_flag=True, default=False,
              help="Defines that all the allocations including function are"
                   " printed out (even with partial participation in the call"
                   " trace)")
@pass_profile
def memstat(profile, mode, **kwargs):
    """
    Memstat is a set of simple queries over memory profiles, with collected allocation info.

    \b
                    #1 `'`'`'`'``'`
                      \u2514 -'```-``-``-
                        \u2514 ```'`'```-``'`'

    \b
                    #2 ''``'`'`-'`""-'''
                      \u2514 ''`'`'`'`'`'

    Memstat contains several predefined functions for aggregated basic information about allocations
    within the profile---list of allocations, tops, sums, etc.---and serves as a base for future
    extension.
    """
    if mode == "func" and not kwargs['function']:
        raise click.BadParameter("missing specified function for list. Use --function=<f>.")

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
