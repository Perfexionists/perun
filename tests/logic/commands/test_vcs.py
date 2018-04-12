"""Basic tests for checking the correctness of the VCS modules"""

import perun.vcs as vcs
import perun.logic.store as store

__author__ = 'Tomas Fiedor'


def test_major_versions(pcs_full):
    """Test whether getting the major version for given VCS is correct

    Expecting correct behaviour and no error
    """
    vcs_type, vcs_path = pcs_full.vcs_type, pcs_full.vcs_path
    major_versions = list(vcs.walk_major_versions(vcs_type, vcs_path))

    assert len(major_versions) == 1
    major_version = major_versions[0]
    assert major_version.name == 'master'
    assert store.is_sha1(major_version.head)
