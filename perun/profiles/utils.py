"""Utility functions for all profile types and conversions."""

from __future__ import annotations


def hide_uid_generics(uid: str) -> str:
    """Hides the generics in the uid

    This transforms std::<std::<type>> into std::<*>

    :param uid: uid with generics
    :return: uid without generics
    """
    nesting = 0
    chars = []
    for c in uid:
        if c == "<":
            nesting += 1
        elif c == ">":
            nesting -= 1
        if nesting == 0 or (c == "<" and nesting == 1):
            chars.append(c)
    return "".join(chars)
