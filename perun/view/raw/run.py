"""Raw printing of the profiles, i.e. without any formatting.

Raw printing is the simplest printing of the given profiles, i.e. without any
formatting and visualization techniques at all.
"""

import click
import termcolor

from perun.utils.helpers import RAW_ATTRS, RAW_ITEM_COLOUR, RAW_KEY_COLOUR, pass_profile

__author__ = 'Tomas Fiedor'


def process_object(item, colour, coloured):
    """
    :param str item: item we are processing by the show
    :param str colour: colour used to colour the object
    :param bool coloured: whether the item should be coloured or not
    :returns str: coloured or uncoloured item
    """
    if coloured:
        return termcolor.colored(item, colour, attrs=RAW_ATTRS)
    else:
        return item


def show(profile, coloured=False, **_):
    """
    :param dict profile: dictionary profile
    :param bool coloured: true if the output should be in colours
    :param dict _: additional keyword for the non coloured show
    :returns str: string representation of the profile
    """
    RAW_INDENT = 4

    # Construct the header
    header = profile['header']
    for header_item in ['type', 'cmd', 'params', 'workload']:
        if header_item in header.keys():
            print("{}: {}".format(
                process_object(header_item, RAW_KEY_COLOUR, coloured),
                process_object(header[header_item], RAW_ITEM_COLOUR, coloured)
            ))

    print('')

    # Construct the collector info
    if 'collector' in profile.keys():
        print(process_object('collector:', RAW_KEY_COLOUR, coloured))
        collector_info = profile['collector']
        for collector_item in ['name', 'params']:
            if collector_item in collector_info.keys():
                print(RAW_INDENT*1*' ' + "- {}: {}".format(
                    process_object(collector_item, RAW_KEY_COLOUR, coloured),
                    process_object(
                        collector_info[collector_item] or 'none', RAW_ITEM_COLOUR, coloured
                    )
                ))


def show_coloured(profile, **kwargs):
    """
    :param dict profile: dictionary profile
    :param dict kwargs: additional parameters for the coloured show
    :returns str: string representation of the profile with colours
    """
    show(profile, True)


@click.command()
@click.option('--coloured', '-c', is_flag=True, default=False,
              help="Colours the showed raw profile.")
@click.option('--one-line', '-o', is_flag=True,
              help="Shows the aggregated one-liner raw profile.")
@pass_profile
def raw(profile, **kwargs):
    """Raw display of the profile, without formating, as JSON object."""
    if kwargs.get('coloured', False):
        show_coloured(profile, **kwargs)
    else:
        show(profile, **kwargs)
