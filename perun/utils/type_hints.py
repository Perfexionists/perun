"""Type annotation helpers."""

from __future__ import annotations

# Standard Imports
from typing import TYPE_CHECKING

# Third-Party Imports

# Perun Imports

if TYPE_CHECKING:
    import tempfile

    # The tempfile.NamedTemporaryFile context manager does not have a public type hint.
    # Hence, we use the private tempfile object and alias it to avoid redundant warnings.
    TempTextIO = tempfile._TemporaryFileWrapper[str]
