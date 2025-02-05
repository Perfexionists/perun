"""SVS is a dummy Single Version System, which tracks the results as a single version, nothing more

Contains concrete implementation of the functions needed by Perun to work without any version control system,
like GIT, SVN, or other.
"""

from __future__ import annotations

# Standard Imports
from typing import Any, Iterator
import getpass
import os
import socket
import sys
import time


# Third-Party Imports

# Perun Imports
from perun.utils.structs.common_structs import MajorVersion, MinorVersion
from perun.vcs.abstract_repository import AbstractRepository

SINGLE_VERSION_BRANCH: str = "master"
SINGLE_VERSION_TAG: str = "HEAD"


def get_time_of_creation(path: str) -> str:
    """Returns the time of the creation of the path

    :param path: path we are analysing the time of creation
    :return: time of creation of the path
    """
    return time.ctime(
        os.path.getctime(path) if sys.platform.startswith("win") else os.stat(path).st_ctime
    )


class SvsRepository(AbstractRepository):
    """Single Version Repository is simple singleton version control system.

    It has following properties:
      1. It has single branch
      2. It has single version

    No changes are made, no changes are tracked, only a singleton state is maintained.
    """

    def __init__(self, vcs_path: str) -> None:
        """Inits the SVS by remembering its path"""
        super().__init__()
        self.vcs_path: str = vcs_path

    def get_minor_head(self) -> str:
        """Returns always single version tag --- the same version

        :return: minor head, the single version that is tracked in SVS
        """
        return SINGLE_VERSION_TAG

    def init(self, _: dict[str, Any]) -> bool:
        """Svs is always initialized

        :param _: params for initialization
        :return: always true, since nothing is initialied
        """
        return True

    def walk_minor_versions(self, _: str) -> Iterator[MinorVersion]:
        """Yield single version

        :param _: head minor version, we are starting the walk
        :return: iterator of single minor version
        """
        yield self.get_minor_version_info(SINGLE_VERSION_TAG)

    def walk_major_versions(self) -> Iterator[MajorVersion]:
        """Yields single branch with single version

        :return: iterator of single major version
        """
        yield MajorVersion(SINGLE_VERSION_BRANCH, SINGLE_VERSION_TAG)

    def get_minor_version_info(self, minor_version: str) -> MinorVersion:
        """Returns valid minor version info only for a SINGLE_VERSION TAG

        We return:
          1. The current user
          2. His email as user@hostname
          3. Time of creation of perun instance
          4. The single tag and simple description

        :param minor_version: minor version we are analysing
        :return: information about single version.
        """
        assert minor_version == SINGLE_VERSION_TAG, f"unknown version `{minor_version}`"
        return MinorVersion(
            get_time_of_creation(self.vcs_path),
            getpass.getuser(),
            f"{getpass.getuser()}@{socket.gethostname()}",
            SINGLE_VERSION_TAG,
            "Singleton version",
            [],
        )

    def minor_versions_diff(self, baseline_minor_version: str, target_minor_version: str) -> str:
        """There is no diff, as there is single version

        :param baseline_minor_version: baseline version
        :param target_minor_version: target version
        :return: empty diff
        """
        assert (
            baseline_minor_version == target_minor_version
        ), f"{baseline_minor_version} or {target_minor_version} is unsupported"
        assert (
            baseline_minor_version == SINGLE_VERSION_TAG
        ), f"{baseline_minor_version} is unsupported"
        return ""

    def get_head_major_version(self) -> str:
        """Returns single branch

        :return: single branch
        """
        return SINGLE_VERSION_BRANCH

    def get_default_major_version(self) -> str:
        """For SVS, the default major version is the same as the HEAD major version.

        :return: default major version
        """
        return SINGLE_VERSION_BRANCH

    def check_minor_version_validity(self, minor_version: str) -> None:
        """Only SINGLE_VERSION_TAG is valid minor version in SVS

        :param minor_version: minor version for which we are checking the validity
        """
        assert minor_version == SINGLE_VERSION_TAG, f"invalid minor version {minor_version}"

    def massage_parameter(self, parameter: str, _: str | None = None) -> str:
        """No massaging in SVS

        :param param: massaged parameter
        :param _: type of the massaged parameter
        :return: the same string
        """
        return parameter

    def is_dirty(self) -> bool:
        """Nothing is really tracked, so it is never dirty

        :return: false since the SVS is never dirty
        """
        return False

    def save_state(self) -> tuple[bool, str]:
        """Nothing was stashed, and we are still on the same version

        :return: nothing was stashed, and we are still on the same version
        """
        return False, SINGLE_VERSION_TAG

    def restore_state(self, _: bool, __: str) -> None:
        """Nothing to restore

        :param _: whether something was stashed
        :param __: to which version should we check out
        """

    def checkout(self, _: str) -> None:
        """There is single version, so nothing is checked out

        :param _: version we are checking out to
        """
