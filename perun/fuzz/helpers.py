"""Collection of helper functions used in fuzzing"""
from __future__ import annotations

# Standard Imports
from typing import Any, AnyStr

# Third-Party Imports

# Perun Imports


def insert_at_split(
    lines: list[AnyStr], index: int, split_position: int, inserted_bytes: AnyStr
) -> None:
    """Inserts bytes or string at given position

    :param list lines: list of lines
    :param int index: index in the list where we are adding
    :param int split_position: position in the list[index] that we insert
    :param bytes inserted_bytes: inserted string or bytes
    """
    lines[index] = lines[index][:split_position] + inserted_bytes + lines[index][split_position:]


def remove_at_split(lines: list[Any], index: int, split_position: int) -> None:
    """Removes bytes at lines[index] at position @p split_position

    :param list lines:
    :param int index:
    :param int split_position:
    """
    lines[index] = lines[index][:split_position] + lines[index][split_position + 1 :]


def replace_at_split(
    lines: list[AnyStr], index: int, split_position: int, replaced_bytes: AnyStr
) -> None:
    """Replaces bytes at lines[index] at @p split_position with @p replaced_bytes

    :param list lines:
    :param int index:
    :param int split_position:
    :param chr replaced_bytes:
    """
    lines[index] = (
        lines[index][:split_position] + replaced_bytes + lines[index][split_position + 1 :]
    )
