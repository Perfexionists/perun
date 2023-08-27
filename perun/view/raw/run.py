"""Raw printing of the profiles, i.e. without any formatting.

Raw printing is the simplest printing of the given profiles, i.e. without any
formatting and visualization techniques at all.
"""

import click
import perun.utils.log as log

from perun.utils.helpers import RAW_ITEM_COLOUR, RAW_KEY_COLOUR
from perun.profile.factory import pass_profile


RAW_INDENT = 4


def show(profile, **_):
    """
    :param dict profile: dictionary profile
    :param dict _: additional keyword for the non coloured show
    :returns str: string representation of the profile
    """

    # Construct the header
    header = profile['header']
    for header_item in ['type', 'cmd', 'args', 'workload']:
        if header_item in header.keys():
            print("{}: {}".format(
                log.in_color(header_item, RAW_KEY_COLOUR),
                log.in_color(header[header_item], RAW_ITEM_COLOUR)
            ))

    print('')

    # Construct the collector info
    if 'collector_info' in profile.keys():
        print(log.in_color('collector:', RAW_KEY_COLOUR))
        collector_info = profile['collector_info']
        for collector_item in ['name', 'params']:
            if collector_item in collector_info.keys():
                print(RAW_INDENT*1*' ' + "- {}: {}".format(
                    log.in_color(collector_item, RAW_KEY_COLOUR),
                    log.in_color(
                        collector_info[collector_item] or 'none', RAW_ITEM_COLOUR
                    )
                ))



@click.command()
@click.option('--one-line', '-o', is_flag=True,
              help="Shows the aggregated one-liner raw profile.")
@pass_profile
def raw(profile, **kwargs):
    """Raw display of the profile, without formating, as JSON object."""
    show(profile, **kwargs)
