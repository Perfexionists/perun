"""Raw printing of the profiles, i.e. without any formatting.

Raw printing is the simplest printing of the given profiles, i.e. without any
formatting and visualization techniques at all.
"""
from __future__ import annotations

import click

from typing import Any

import perun.profile.factory as profile_factory
import perun.utils.log as log

from perun.utils.helpers import RAW_ITEM_COLOUR, RAW_KEY_COLOUR


def show(profile: profile_factory.Profile, **kwargs: Any) -> None:
    """
    :param dict profile: dictionary profile
    :param dict kwargs: additional keyword for the non-coloured show
    :returns str: string representation of the profile
    """
    raw_indent = kwargs.get("indent", 4)

    # Construct the header
    header = profile["header"]
    for header_item in ["type", "cmd", "args", "workload"]:
        if header_item in header.keys():
            log.info(
                f"{log.in_color(header_item, RAW_KEY_COLOUR)}: {log.in_color(header[header_item], RAW_ITEM_COLOUR)}"
            )

    log.info("")

    # Construct the collector info
    if "collector_info" in profile.keys():
        log.info(log.in_color("collector:", RAW_KEY_COLOUR))
        collector_info = profile["collector_info"]
        for collector_item in ["name", "params"]:
            if collector_item in collector_info.keys():
                log.info(
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
@profile_factory.pass_profile
def raw(profile: profile_factory.Profile, **kwargs: Any) -> None:
    """Raw display of the profile, without formatting, as JSON object."""
    show(profile, **kwargs)
