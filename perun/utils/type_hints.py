"""Type annotation helpers."""

from __future__ import annotations

# Standard Imports
import tempfile
from typing import TypeAlias

# Third-Party Imports

# Perun Imports

# The tempfile.NamedTemporaryFile context manager does not have a public type hint.
# Hence, we use the private tempfile object and alias it to avoid redundant warnings.
TempTextIO: TypeAlias = "tempfile._TemporaryFileWrapper[str]"
