"""Abstraction of version control systems"""

from __future__ import annotations

# Standard Imports
from abc import abstractmethod, ABC
from typing import Any, Iterator, TYPE_CHECKING, Optional

# Third-Party Imports

# Perun Imports
if TYPE_CHECKING:
    from perun.utils.structs.common_structs import MinorVersion, MajorVersion


class AbstractRepository(ABC):
    """Abstract Base Class for all repositories"""

    @abstractmethod
    def get_minor_head(self) -> str:
        """Returns the string representation of head of current major version, i.e.
        for git this returns the massaged HEAD reference.

        This function is called mainly during the outputs of ``perun log`` and
        ``perun status`` but also during the automatic generation of profiles
        (either by ``perun run`` or ``perun collect``), where the retrieved
        identification is used as :preg:`origin`.

        :returns: unique string representation of current head (usually in SHA)
        """

    @abstractmethod
    def init(self, vcs_init_params: dict[str, Any]) -> bool:
        """Calls the implementation of initialization of wrapped underlying version
        control system.

        The initialization should take care of both reinitialization of existing
        version control system instances and newly created instances. Init is
        called during the ``perun init`` command from command line interface.

        :param vcs_init_params: dictionary of keyword arguments passed to
            initialization method of the underlying vcs module
        :return: true if the underlying vcs was successfully initialized
        """

    @abstractmethod
    def walk_minor_versions(self, head_minor_version: str) -> Iterator[MinorVersion]:
        """Generator of minor versions for the given major version, which yields
        the ``MinorVersion`` named tuples containing the following information:
        ``date``, ``author``, ``email``, ``checksum`` (i.e. the hash representation
        of the minor version), ``commit_description`` and ``commit_parents`` (i.e.
        other minor versions).

        Minor versions are walked through this function during the ``perun log``
        command.

        :param head_minor_version: the root minor versions which is the root
            of the walk.
        :returns: iterable stream of minor version representation
        """

    @abstractmethod
    def walk_major_versions(self) -> Iterator[MajorVersion]:
        """Generator of major versions for the current wrapped repository.

        This function is currently unused, but will be needed in the future.

        :returns: iterable stream of major version representation
        """

    @abstractmethod
    def get_minor_version_info(self, minor_version: str) -> MinorVersion:
        """Yields the specification of concrete minor version in form of
        the ``MinorVersion`` named tuples containing the following information:
        ``date``, ``author``, ``email``, ``checksum`` (i.e. the hash representation
        of the minor version), ``commit_description`` and ``commit_parents`` (i.e.
        other minor versions).

        This function is a non-generator alternative of
        :func:`perun.vcs.walk_minor_versions` and is used during the ``perun
        status`` output to display the specifics of minor version.

        :param minor_version: the specification of minor version (in form of
            sha e.g.) for which we are retrieving the details
        :returns: minor version named tuple
        """

    @abstractmethod
    def minor_versions_diff(self, baseline_minor_version: str, target_minor_version: str) -> str:
        """Returns the git diff of two specified minor versions.

        Each minor version is in form of SHA

        :param baseline_minor_version: the specification of the first minor version
        :param target_minor_version: the specification of the second minor version
        """

    @abstractmethod
    def get_head_major_version(self) -> str:
        """Returns the string representation of current major version of the
        wrapped repository.

        Major version is displayed during the ``perun status`` output, which shows
        the current working major version of the project.

        :returns: string representation of the major version
        """

    @abstractmethod
    def get_default_major_version(self) -> str:
        """Returns the default major version string of the wrapped repository.

        :returns: string representation of the default major version
        """

    @abstractmethod
    def check_minor_version_validity(self, minor_version: str) -> None:
        """Checks whether the given minor version specification corresponds to the
        wrapped version control system, and is not in wrong format.

        Minor version validity is mostly checked during the lookup of the minor
        versions from the command line interface.

        :param minor_version: the specification of minor version (in form of
            sha e.g.) for which we are checking the validity
        :raises VersionControlSystemException: when the given minor version is
            invalid in the context of the wrapped version control system.
        """

    @abstractmethod
    def massage_parameter(self, parameter: str, parameter_type: Optional[str] = None) -> str:
        """Conversion function for massaging (or unifying different representations
        of objects) the parameters for version control systems.

        Massaging is mainly executed during from the command line interface, when
        one can e.g. use the references (like ``HEAD``) to specify concrete minor
        versions. Massing then unifies e.g. the references or proper hash
        representations, to just one representation for internal processing.

        :param parameter: vcs parameter (e.g. revision, minor or major version)
            which will be massaged, i.e. transformed to unified representation
        :param parameter_type: more detailed type of the parameter
        :returns: string representation of parameter
        """

    @abstractmethod
    def is_dirty(self) -> bool:
        """Tests whether the wrapped repository is dirty.

        By dirty repository we mean a repository that has either a submitted changes to its index
        (i.e. we are in the middle of commit) or any unsubmitted changes to tracked files
        in the current working directory.

        Note that this is crucial for performance testing, as any uncommited changes may skew
        the profiled data and hence the resulting profiles would not correctly represent
        the performance of minor versions.

        :return: whether the given repository is dirty or not
        """

    @abstractmethod
    def save_state(self) -> tuple[bool, str]:
        """Saves the state of the repository in case it is dirty.

        When saving the state of the repository one should store the uncommited changes to
        the working directory and index. Any issues while this process happens should be handled by
        user itself, hence no workarounds and mending should take place in this function.

        :returns: (1) indication that some changes were stashed, and,
                  (2) the state of previous head.
        """

    @abstractmethod
    def restore_state(self, saved: bool, state: str) -> None:
        """Restores the previous state of the repository

        When restoring the state of the repository one should pop the stored changes from the stash
        and reapply them on the current directory. This will make sure, that after the performance
        testing, the project is in the previous state and developer can continue with his work.

        :param saved: whether the stashed was something
        :param state: the previous state of the repository
        """

    @abstractmethod
    def checkout(self, minor_version: str) -> None:
        """Checks out the new working directory corresponding to the given minor version.

        According to the supplied minor version, this command should remake the working directory,
        so it corresponds to the state defined by the minor version.

        :param minor_version: minor version that will be checked out
        """
