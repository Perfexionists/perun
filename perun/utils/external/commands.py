"""Helper functions for working with commands.

This contains functions for getting outputs from commands or running commands or external executables.
"""
from __future__ import annotations

# Standard Imports
from typing import Optional, IO
import subprocess

# Third-Party Imports

# Perun Imports


def get_stdout_from_external_command(command: list[str], stdin: Optional[IO[bytes]] = None) -> str:
    """Runs external command with parameters, checks its output and provides its output.

    :param list command: list of arguments for command
    :param handle stdin: the command input as a file handle
    :return: string representation of output of command
    """
    output = subprocess.check_output(
        [c for c in command if c != ""], stderr=subprocess.STDOUT, stdin=stdin
    )
    return output.decode("utf-8")
