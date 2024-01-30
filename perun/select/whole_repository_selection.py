"""Whole Repository Selection is conservative selection that does no pruning

In particular:
  1. Each version is analysed;
  2. Each pair of profiles is analysed.

"""

# Standard Imports
from typing import Iterator

# Third-Party Imports

# Perun Imports
from perun.logic import pcs
from perun.profile import helpers as profile_helpers
from perun.profile.factory import Profile
from perun.profile.helpers import ProfileInfo
from perun.select.abstract_base_selection import AbstractBaseSelection
from perun.utils.structs import MinorVersion


class WholeRepositorySelection(AbstractBaseSelection):
    """Implementation of Whole Repository Selection"""

    def should_check_version(self, _: MinorVersion) -> tuple[bool, float]:
        """We check all versions always when checking by whole repository selector

        :param _: analysed target version
        :return: always true with 100% confidence
        """
        return True, 1

    def should_check_versions(self, _: MinorVersion, __: MinorVersion) -> tuple[bool, float]:
        """We check all pairs of versions always when checking by whole repository selector

        :param _: analysed target version
        :param __: corresponding baseline version (compared against)
        :return: always true with 100% confidence
        """
        return True, 1

    def should_check_profiles(self, _: Profile, __: Profile) -> tuple[bool, float]:
        """We check all pairs of profiles always when checking by whole repository selector

        :param _: analysed target profile
        :param __: corresponding baseline profile (compared against)
        :return: always true with 100% confidence
        """
        return True, 1

    def get_parents(self, target_version: MinorVersion) -> list[MinorVersion]:
        """We check both parents when checking by whole repository selector

        :param target_version: analysed target version
        :return: both parents of the version
        """
        return [pcs.vcs().get_minor_version_info(parent) for parent in target_version.parents]

    def get_profiles(
        self, target_version: MinorVersion, target_profile: Profile
    ) -> list[tuple[MinorVersion, ProfileInfo]]:
        """We return all profiles compatible with target profile for parents of the target version

        :param target_version: analysed target version
        :param target_profile: analysed target profile
        :return: list of profiles corresponding to parents of the minor version;
            each profile has to be compatible with target profile
        """
        analysis_worklist = []
        for parent in target_version.parents:
            parent_info = pcs.vcs().get_minor_version_info(parent)
            for profile_info in profile_helpers.load_list_for_minor_version(parent):
                if profile_info.is_compatible_with_profile(target_profile):
                    analysis_worklist.append((parent_info, profile_info))
        return analysis_worklist

    def get_skeleton_for_profile(
        self, target_version: MinorVersion, target_profile: Profile
    ) -> Iterator[tuple[MinorVersion, ProfileInfo]]:
        """Iterates over the skeleton of the version history wrt given target profile

        This generates all compatible profiles without any pruning.

        :param target_version: analysed target version (the skeleton head)
        :param target_profile: profile corresponding to analysed target version
        :return: iterator of pairs of minor versions and their corresponding profiles;
            each profile is compatible with target profile
        """
        for minor_version in pcs.vcs().walk_minor_versions(target_version.checksum):
            yield from self.get_profiles(minor_version, target_profile)

    def get_skeleton(self, target_version: MinorVersion) -> Iterator[MinorVersion]:
        """Iterates over the skeleton of the version history

        :param target_version: analysed target version (the skeleton head)
        :return: iterator of minor versions
        """
        yield from pcs.vcs().walk_minor_versions(target_version.checksum)

    def find_nearest(self, target_version: MinorVersion) -> MinorVersion:
        """Returns the identity: the target version itself

        :param target_version: analysed version
        :return: the target version itself
        """
        return target_version
