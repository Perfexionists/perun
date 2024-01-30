"""Base Class for different notions of selecting versions for analysis

This class is not meant to be instantiated and serves as base point for creating
new notions of selecting version. In particular, this should include:

  1. Checking whether some unit (version, a pair of versions, a pair of profiles) should be analysed at all.
  2. For given unit, selecting corresponding unit to form a pair. E.g. for given target version,
     this should return corresponding baseline version.
  3. Finding nearest suitable unit for some given unit: this could be either predecessor or successor in history.
"""
from __future__ import annotations

# Standard Imports
from typing import TYPE_CHECKING, Iterator
import abc

# Third-Party Imports

# Perun Imports


if TYPE_CHECKING:
    from perun.utils.structs import MinorVersion
    from perun.profile.factory import Profile
    from perun.profile.helpers import ProfileInfo


class AbstractBaseSelection(abc.ABC):
    """Base interface for selecting units in history"""

    @abc.abstractmethod
    def should_check_version(
        self,
        target_version: MinorVersion,
    ) -> tuple[bool, float]:
        """Checks whether the given version should be performance analysed

        :param target_version: given target version in the history
        :return: (1) boolean flag whether the given version should be analysed, and,
                 (2) confidence of the underlying selection method
        """

    @abc.abstractmethod
    def should_check_versions(
        self, target_version: MinorVersion, baseline_version: MinorVersion
    ) -> tuple[bool, float]:
        """Checks whether the target version should be compared against the given baseline version

        :param target_version: given target in the history (version we are analysing)
        :param baseline_version: corresponding baseline version in the history
            (which we analysed in the past)
        :return: (1) boolean flag whether the given pair of versions should be analysed, and,
                 (2) confidence of the underlying selection method
        """

    @abc.abstractmethod
    def should_check_profiles(
        self, target_profile: Profile, baseline_profile: Profile
    ) -> tuple[bool, float]:
        """Checks whether the target profile should be compared against the given baseline profile

        :param target_profile: given target profile in the history (version we are analysing)
        :param baseline_profile: corresponding, compatible baseline profile in the history
            (which we analysed in the past)
        :return: (1) boolean flag whether the given pair of versions should be analysed, and,
                 (2) confidence of the underlying selection method
        """

    @abc.abstractmethod
    def get_parents(self, target_version: MinorVersion) -> list[MinorVersion]:
        """For given target version returns list of baseline parent minor versions

        Note that given target version can have multiple suitable baseline parent version
        to compare against. This is mainly in case of merge commits, that can compare
        against multiple parents in the corresponding branches.

        :param target_version: given target version in the history (version we are analysing)
        :return: list of minor versions we should compare against
        """

    @abc.abstractmethod
    def get_profiles(
        self, target_version: MinorVersion, target_profile: Profile
    ) -> list[tuple[MinorVersion, ProfileInfo]]:
        """For given target version and its profile returns list of profiles and their versions.

        Note that given profile in the corresponding target version can have multiple suitable
        profiles in multiple different parent versions. This is mainly the case of merge commits,
        that can compare against multiple parents and profiles in the corresponding branches.

        :param target_version: given target version in the history (version we are analysing
        :param target_profile: profile corresponding to the target version
            (particular profile we are analysing).
        :return: list of tuples of baseline minor versions and their particular profile infos
        """

    @abc.abstractmethod
    def get_skeleton_for_profile(
        self, target_version: MinorVersion, target_profile: Profile
    ) -> Iterator[tuple[MinorVersion, ProfileInfo]]:
        """From given point in history (the target version) generates the portion of the history
        which contains only relevant profiles and minor versions wrt given target version.

        For example, given a HEAD minor version, the skeleton could e.g. contain all the tags
        in the history (since, tags usually corresponds to the stable releases and hence are
        ideal for comparison in history).

        :param target_version: head (or target) version in the history for which we are generating the skeleton
        :param target_profile: optionally one can restrict the searching to one particular type of profile
        :return: iterable of the minor versions and optionally profiles that forms the skeleton for given
            target version.
        """

    @abc.abstractmethod
    def get_skeleton(self, target_version: MinorVersion) -> Iterator[MinorVersion]:
        """From given point in history (the target version) generates the portion of the history
        relevant to performance analysis.

        For example, the skeleton could e.g. contain all the tags in the history
        (since, tags usually corresponds to the stable releases and hence are
        ideal for comparison in history).

        :param target_version: head (or target) version in the history for which we are generating the skeleton
        :return: iterable of the minor versions
        """

    @abc.abstractmethod
    def find_nearest(self, target_version: MinorVersion) -> MinorVersion:
        """For the given point in history (the target version) finds the nearest point in history.

        Note that this could correspond both to parent or successor. This is mostly meant for
        bisectional search of the history.

        :param target_version: target version in the history for which we are finding nearest version
        :return: the nearest version in the history (either parent or successor)
        """
