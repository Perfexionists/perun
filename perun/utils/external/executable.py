"""Helper functions for working with executable.

Currently, this only handles finding executables.
"""
from __future__ import annotations

# Standard Imports
from typing import Optional
import os
import shutil

# Third-Party Imports

# Perun Imports


def find_executable(cmd: Optional[str]) -> Optional[str]:
    """Check if the supplied cmd is executable and find its real path
    (i.e. absolute path with resolved symlinks)

    :param str cmd: the command to check

    :return str: resolved command path
    """
    # Ignore invalid paths
    if cmd is None:
        return None

    # shutil.which checks:
    # 1) files with relative / absolute paths specified
    # 2) files accessible through the user PATH environment variable
    # 3) that the file is indeed accessible and executable
    cmd = shutil.which(cmd)
    if cmd is None:
        return None
    # However, we still want to resolve the real path of the file
    return os.path.realpath(cmd)
