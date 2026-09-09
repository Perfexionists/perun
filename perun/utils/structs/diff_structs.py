"""Showdiff helper structures and constants."""

from __future__ import annotations

# Standard Imports
import enum

# Third-Party Imports

# Perun Imports


DEFAULT_MAX_FUNCTION_TRACES: int = 10
DEFAULT_TOP_DIFFS: int = 50
DEFAULT_FUNCTION_THRESHOLD: float = 0.1
DEFAULT_TRACE_THRESHOLD: float = 0.001


class HeaderDisplayStyle(enum.Enum):
    """Supported styles of displaying profile specification and metadata."""

    FULL = "full"
    DIFF = "diff"

    @staticmethod
    def supported() -> list[str]:
        """Obtain the collection of supported display styles.

        :return: the collection of valid display styles
        """
        return [style.value for style in HeaderDisplayStyle]

    @staticmethod
    def default() -> str:
        """Provide the default display style.

        :return: the default display style
        """
        return HeaderDisplayStyle.FULL.value
