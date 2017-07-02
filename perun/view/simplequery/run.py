"""Simple queries over the profiles."""

import click
import perun.view.simplequery.queries as qrs
import perun.view.simplequery.pretty_output as pretty
from perun.utils.helpers import pass_profile
from perun.utils.exceptions import IncorrectProfileFormatException

__author__ = 'Radim Podola'

SUPPORTED_MODES = ("list", "top", "most", "sum", "func")


@click.command(name='query')
@click.argument('mode', nargs=1, type=str)
@click.option('--top', '-t', default=10,
              help="Defines a count of the records that will be printed.")
@click.option('--from-time', type=float,
              help="Defines timestamp in the timeline of printed records.")
@click.option('--to-time', type=float,
              help="Defines timestamp in the timeline of printed records.")
@click.option('--function',
              help="Defines name of the function to search for.")
@click.option('--all', '-a', is_flag=True, default=False,
              help="Defines that all the allocations including function are"
                   " printed out (even with partial participation in the call"
                   " trace)")
@pass_profile
def simplequery(profile, mode, **kwargs):
    """Simple query over the profile.
       Argument MODE defines the operation with the profile.
    """
    if mode not in SUPPORTED_MODES:
        raise click.BadParameter("Mode is not supported. Supported modes are: "
                                 + str(SUPPORTED_MODES))
    if mode == "func" and not kwargs['function']:
        raise click.BadParameter("Function not defined")

    inter_func = getattr(qrs, "get_%s" % mode)
    if inter_func:
        try:
            output = inter_func(profile, **kwargs)
        except Exception as e:
            raise IncorrectProfileFormatException('', str(e))
    else:
        assert False

    print(pretty.get_profile_info(profile))
    if output:
        print(output)
