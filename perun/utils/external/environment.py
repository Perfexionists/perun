"""Helper functions for working with environment.

Currently, this only handles getting version of Python.
"""

from __future__ import annotations

# Standard Imports
from subprocess import CalledProcessError
from typing import Optional, Callable, Protocol, Any
import operator
from pathlib import Path
import platform
import re
import sys

# Third-Party Imports
import psutil

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

    :param required_version: the found interpreter must satisfy the supplied version
    :param fallback: the fallback python interpreter version to use if no interpreter is found
                         or its version is not matching the required version

    :return: the absolute path to the currently running python3 interpreter,
                 if not found, returns fallback interpreter instead
    """

    def _parse_version(
        python_version: str,
    ) -> tuple[list[int], Callable[[Comparable, Comparable], bool]]:
        """Parse the python version represented as a string into the 3 digit version number and
        additional postfixes, such as characters or '+' and '-'.

        :param python_version: the version as a string (e.g., '3.6.5+')
        :return: list of version digits and function used to compare two
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


def get_kernel() -> str:
    """Returns the identification of the kernel

    If `uname -r` cannot be called, then "Unknown" is returned

    :return: identification of the kernel
    """
    try:
        out, _ = commands.run_safely_external_command("uname -r")
        return out.decode("utf-8").strip()
    except CalledProcessError:
        return "Unknown"


def get_machine_specification() -> dict[str, Any]:
    """Returns dictionary with machine specification

    :return: machine specification as dictionary
    """
    system = platform.uname()
    try:
        cpu_freq = psutil.cpu_freq().current
    except RuntimeError:
        # There are issues with CPU freq on some Apple Silicon VMs
        # https://github.com/giampaolo/psutil/pull/2222#issuecomment-2000755602
        cpu_freq = 0.0
    machine_info: dict[str, Any] = {
        "architecture": system.machine,
        "system": system.system,
        "release": system.release,
        "host": system.node,
        "cpu": {
            "physical": psutil.cpu_count(logical=False),
            "total": psutil.cpu_count(logical=True),
            "frequency": f"{cpu_freq:.2f}Mhz",
        },
        "memory": {
            "total_ram": log.format_file_size(psutil.virtual_memory().total).strip(),
            "swap": log.format_file_size(psutil.swap_memory().total).strip(),
        },
    }

    if Path("/proc/cmdline").exists():
        with open("/proc/cmdline", "r", encoding="utf-8") as cmdline_handle:
            machine_info["boot_info"] = " ".join(cmdline_handle.read().split("\n")).strip()
    if Path("/proc/meminfo").exists():
        with open("/proc/meminfo", "r", encoding="utf-8") as meminfo_handle:
            machine_info["mem_details"] = {
                key: value.strip()
                for (key, value) in [
                    line.split(":") for line in meminfo_handle.read().split("\n") if line
                ]
            }
    if Path("/proc/cpuinfo").exists():
        with open("/proc/cpuinfo", "r", encoding="utf-8") as cpuinfo_handle:
            machine_info["cpu_details"] = [
                {
                    key.strip(): value.strip()
                    for (key, value) in [line.split(":") for line in cpu_line.split("\n") if line]
                }
                for cpu_line in cpuinfo_handle.read().split("\n\n")
                if cpu_line
            ]
    # Gather CPU vulnerabilities
    vulnerabilities_dir = Path("/sys/devices/system/cpu/vulnerabilities/")
    if vulnerabilities_dir.exists():
        machine_info["cpu_vulnerabilities"] = {}
        for vuln in sorted(list(vulnerabilities_dir.iterdir())):
            with open(vuln, "r", encoding="utf-8") as vuln_handle:
                vuln_name = vuln.name.replace("_", " ").capitalize()
                machine_info["cpu_vulnerabilities"][vuln_name] = vuln_handle.read()
    return machine_info
