"""Helper functions for working with processes

Currently, this contains working with nonblocking subprocesses
"""
from __future__ import annotations

# Standard Imports
from typing import Any, Optional, Callable, Iterator
import contextlib
import subprocess
import shlex

# Third-Party Imports

# Perun Imports


@contextlib.contextmanager
def nonblocking_subprocess(
    command: str,
    subprocess_kwargs: dict[str, Any],
    termination: Optional[Callable[..., Any]] = None,
    termination_kwargs: Optional[dict[str, Any]] = None,
) -> Iterator[subprocess.Popen[bytes]]:
    """Runs a non-blocking process in the background using subprocess without shell.

    The process handle is available by using the context manager approach. It is possible to
    supply custom process termination function (and its arguments) that will be used instead of
    the subprocess.terminate().

    :param str command: the command to run in the background
    :param dict subprocess_kwargs: additional arguments for the subprocess Popen
    :param function termination: the custom termination function or None
    :param dict termination_kwargs: the arguments for the termination function
    """
    # Split process and arguments
    parsed_cmd = shlex.split(command)

    # Do not allow shell=True
    if "shell" in subprocess_kwargs:
        del subprocess_kwargs["shell"]

    # Start the process and do not block it (user can tho)
    with subprocess.Popen(parsed_cmd, shell=False, **subprocess_kwargs) as proc:
        try:
            yield proc
        except Exception:
            # Re-raise the encountered exception
            raise
        finally:
            # Don't terminate the process if it has already finished
            if proc.poll() is None:
                # Use the default termination if the termination handler is not set
                if termination is None:
                    proc.terminate()
                else:
                    # Otherwise use the supplied termination function
                    if termination_kwargs is None:
                        termination_kwargs = {}
                    termination(**termination_kwargs)
