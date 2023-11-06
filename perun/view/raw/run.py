"""Raw printing of the profiles, i.e. without any formatting.

Raw printing is the simplest printing of the given profiles, i.e. without any
formatting and visualization techniques at all.
"""
from __future__ import annotations

import click
import perun.utils.log as log

from typing import Any

from perun.utils.helpers import RAW_ITEM_COLOUR, RAW_KEY_COLOUR
from perun.profile.factory import pass_profile, Profile


def show(profile: Profile, **kwargs: Any) -> None:
    """
    :param dict profile: dictionary profile
    :param dict _: additional keyword for the non coloured show
    :returns str: string representation of the profile
    """
    raw_indent = kwargs.get("indent", 4)

    # Construct the header
    header = profile["header"]
    for header_item in ["type", "cmd", "args", "workload"]:
        if header_item in header.keys():
            print(
                "{}: {}".format(
                    log.in_color(header_item, RAW_KEY_COLOUR),
                    log.in_color(header[header_item], RAW_ITEM_COLOUR),
                )
            )

    print("")

    # Construct the collector info
    if "collector_info" in profile.keys():
        print(log.in_color("collector:", RAW_KEY_COLOUR))
        collector_info = profile["collector_info"]
        for collector_item in ["name", "params"]:
            if collector_item in collector_info.keys():
                print(
                    int(raw_indent) * 1 * " "
                    + "- {}: {}".format(
                        log.in_color(collector_item, RAW_KEY_COLOUR),
                        log.in_color(collector_info[collector_item] or "none", RAW_ITEM_COLOUR),
                    )
                )


@click.command()
@click.option("--one-line", "-o", is_flag=True, help="Shows the aggregated one-liner raw profile.")
@click.option(
    "--indent",
    "-i",
    type=click.INT,
    metavar="<INT>",
    default=4,
    help="Sets indent to <INT>.",
)
@pass_profile
def raw(profile: Profile, **kwargs: Any) -> None:
    """Raw display of the profile, without formating, as JSON object."""
    show(profile, **kwargs)
