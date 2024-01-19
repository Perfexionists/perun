"""Utils contains helper modules, that are not directly dependent on pcs.

Utils contains various helper modules and functions, that can be used in arbitrary projects, and
are not specific for perun pcs, like e.g. helper decorators, logs, etc.
"""
from __future__ import annotations

# Standard Imports
from typing import (
    Iterable,
    Optional,
    Any,
    TYPE_CHECKING,
)
import os
import shutil
import subprocess

# Third-Party Imports
import magic

# Perun Imports

if TYPE_CHECKING:
    from perun.utils.structs import CollectStatus, PostprocessStatus


def get_build_directories(root: str = ".", template: Optional[list[str]] = None) -> Iterable[str]:
    """Search for build directories in project tree. The build directories can be specified as an
    argument or default templates are used.

    :param str root: directory tree root
    :param list template: list of directory names to search for
    :return: generator object of build directories
    """
    if template is None:
        template = ["build", "_build", "__build"]
    # Find all build directories in directory tree
    root = os.path.join(root, "")
    for current, subdirs, _ in os.walk(root):
        # current directory without root section
        # (to prevent nesting detection if root contains template directory)
        relative = current[len(root) :]
        # Do not traverse hidden directories
        subdirs[:] = [d for d in subdirs if not d[0] == "."]
        for build_dir in template:
            # find directories conforming to the templates without nested ones
            if build_dir in subdirs and not _is_nested(relative, template):
                yield current + build_dir


def _is_nested(path: str, templates: Iterable[str]) -> bool:
    """Check if any element from template is contained within the path - resolve nested template
    directories

    :param str path: path to be resolved
    :param list templates: list of directory names to search for
    :return: bool value representing result
    """
    for template in templates:
        if template in path:
            return True
    return False


def get_directory_elf_executables(
    root: str = ".", only_not_stripped: bool = False
) -> Iterable[str]:
    """Get all ELF executable (stripped or not) from directory tree recursively.

    :param str root: directory tree root
    :param bool only_not_stripped: flag indicating whether collect only binaries not stripped
    :return: generator object of executable binaries as file paths
    """
    root = os.path.join(root, "")
    for current, subdirs, files in os.walk(root):
        # Ignore hidden directories and files
        subdirs[:] = [d for d in subdirs if not d[0] == "."]
        files = [f for f in files if f[0] != "."]
        for file in files:
            # Check if file is executable binary
            filepath = os.path.join(current, file)
            if is_executable_elf(filepath, only_not_stripped):
                yield filepath


def is_executable_elf(file: str, only_not_stripped: bool = False) -> bool:
    """Check if file is executable ELF binary.

    :param str file: the file path
    :param bool only_not_stripped: flag indicating whether also check stripped binaries or not
    :return: bool value representing check result
    """
    # Determine file magic code, we are looking out for ELF files
    f_magic = magic.from_file(file)
    is_elf = f_magic.startswith("ELF") and ("executable" in f_magic or "shared object" in f_magic)
    if is_elf and only_not_stripped:
        return "not stripped" in f_magic
    return is_elf


def get_project_elf_executables(root: str = ".", only_not_stripped: bool = False) -> list[str]:
    """Get all ELF executable files stripped or not from project specified by root
    The function searches for executable files in build directories - if there are any, otherwise
    the whole project directory tree is traversed.

    :param str root: directory tree root
    :param bool only_not_stripped: flag indicating whether collect only binaries not stripped
    :return: list of project executable binaries as file paths
    """
    # Get possible binaries in build directories
    root = os.path.join(root, "")
    build = list(get_build_directories(root))

    # No build directories, find all binaries instead
    if not build:
        build = [root]

    # Gather binaries
    binaries = []
    for build_dir in build:
        binaries += list(get_directory_elf_executables(build_dir, only_not_stripped))

    return binaries
