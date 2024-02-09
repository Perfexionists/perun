"""Helper functions for working with environment.

Currently, this only handles getting version of Python.
"""
from __future__ import annotations

# Standard Imports
from typing import Optional, Callable, Protocol, Any
import operator
import re
import sys

# Third-Party Imports

# Perun Imports
from perun.utils import log
from perun.utils.external import commands

# Parse the obtained python version identifier into groups of digits and postfixes
# We assume 3 blocks of version specification, where each block consists of:
#  - initial dot (except the first block)
#  - digit(s) specifying the version component
#  - additional postfixes, such as characters or +, -
# e.g., 3.11a, 3.1.2b, 3.6.8+
PYTHON_VERSION = re.compile(r"^(?:(\d*)([^0-9.]*))?(?:\.(\d+)([^0-9.]*))?(?:\.(\d+)([^0-9.]*))?")


class Comparable(Protocol):
    def __le__(self, other: Any) -> bool:
        """"""

    def __lt__(self, other: Any) -> bool:
        """"""

    def __ge__(self, other: Any) -> bool:
        """"""

    def __gt__(self, other: Any) -> bool:
        """"""


def get_current_interpreter(
    required_version: Optional[str] = None, fallback: str = "python3"
) -> str:
    """Obtains the currently running python interpreter path. Typical use-case for this utility
    is running 'sudo python' as a subprocess which unfortunately ignores any active virtualenv,
    thus possibly running the command in an incompatible python version with missing packages etc.

    If a specific interpreter version is required, then the found interpreter must satisfy the
    version, otherwise default (fallback) python3 interpreter is provided.
    The supported formats for version specification are:
     - exact:                '3', '3.5', '3.6.11', etc.
     - minimum (inclusive):  '3.6+', '3.7.2+', etc.
     - maximum (inclusive):  '3.5-', '3-', etc.

    :param str required_version: the found interpreter must satisfy the supplied version
    :param str fallback: the fallback python interpreter version to use if no interpreter is found
                         or its version is not matching the required version

    :return str: the absolute path to the currently running python3 interpreter,
                 if not found, returns fallback interpreter instead
    """

    def _parse_version(
        python_version: str,
    ) -> tuple[list[int], Callable[[Comparable, Comparable], bool]]:
        """Parse the python version represented as a string into the 3 digit version number and
        additional postfixes, such as characters or '+' and '-'.

        :param str python_version: the version as a string (e.g., '3.6.5+')
        :return tuple (list, func): list of version digits and function used to compare two
                                    versions based on the +- specifier
        """
        if version_match := PYTHON_VERSION.match(python_version):
            version_parts = version_match.groups()
            version_digits = [int(digit) for digit in version_parts[::2] if digit]
            # Obtain the last valid postfix (i.e., accompanying last parsed digit)
            min_max = version_parts[(2 * len(version_digits)) - 1]
            # Check for interval specifiers, i.e., + or - and use them to infer the comparison operator
            cmp_op: Callable[[Comparable, Comparable], bool] = operator.ne
            for char in reversed(min_max):
                if char in ("+", "-"):
                    cmp_op = operator.lt if char == "+" else operator.gt
                    break
            # Add default version digits if missing, we expect 3 version digits
            while len(version_digits) != 3:
                version_digits.append(0)
            return version_digits, cmp_op
        log.error(f"Unparsable Python version {python_version}")
        return [], operator.eq

    interpreter = sys.executable
    # Ensure that the found interpreter satisfies the required version
    if interpreter and required_version is not None:
        # The format of --version should be 'Python x.y.z'
        version = commands.run_safely_external_command(f"{interpreter} --version")[0].decode(
            "utf-8"
        )
        version = version.split()[1]
        interpreter_version = _parse_version(version)[0]
        parsed_required_version, cmp_operator = _parse_version(required_version)
        # Compare the versions using the obtained operator
        for interpreter_v, required_v in zip(interpreter_version, parsed_required_version):
            if cmp_operator(interpreter_v, required_v):
                interpreter = fallback
                break
    # If no interpreter was found, use fallback
    return interpreter or fallback
