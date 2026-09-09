"""A collection of functions for parsing folded profiles."""

from __future__ import annotations

# Standard Imports
from collections.abc import Iterable, Iterator
from typing import Callable, TextIO

# Third-Party Imports

# Perun Imports


def parse_resources_from_stream(
    folded_stream: TextIO | Iterable[str], resources: list[dict[str, str | int]]
) -> None:
    """Parses a stream of folded perf events into a list of resources.

    Each resource is identified by its trace (uid), which consists of semicolon-delimited stack
    frames, and the consumed resources.

    :param folded_stream: a stream of folded perf events
    :param resources: the output list of resources
    """
    # Optimize dot operator access.
    str_rsplit = str.rsplit
    # Mypy cannot infer the type variable of the list.append method on its own.
    list_append: Callable[[list[dict[str, str | int]], dict[str, str | int]], None] = list.append

    for line in folded_stream:
        try:
            stack, count_str = str_rsplit(line, maxsplit=1)
            # resources.append({"amount": int(count_str), "uid": stack})
            list_append(resources, {"amount": int(count_str), "uid": stack})
        except ValueError:
            # Ignore invalid rows.
            pass


def parse_events_from_stream(folded_stream: TextIO) -> Iterator[tuple[str, int]]:
    """Parses a file containing folded profile into a stream of folded records.

    :param folded_stream: a file containing folded perf events.

    :return: a stream of folded records.
    """
    # Optimize dot operator access.
    str_rsplit = str.rsplit

    for record in folded_stream:
        try:
            # Parse the line, obtain the performance value and the trace.
            trace, count = str_rsplit(record, " ", maxsplit=1)
            yield trace, int(count)
        except ValueError:
            pass
