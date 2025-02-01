"""Basic tests for checking the correctness of the VCS modules"""

from __future__ import annotations

# Standard Imports
import operator
import os

# Third-Party Imports
import git
import pytest

# Perun Imports
from perun.vcs import vcs_kit, svs_repository
from perun.vcs.abstract_repository import AbstractRepository
from perun.logic import pcs, store


def test_on_empty_git(pcs_with_empty_git):
    """Tests how vcs handles the git without any commits (should not fail or so)

    Excepts handled errors and not uncaught shit
    """
    # Assert that when we walk with bogus head then nothing is returned
    assert len(list(pcs.vcs().walk_minor_versions(""))) == 0


def test_major_versions(pcs_full_no_prof):
    """Test whether getting the major version for given VCS is correct

    Expecting correct behaviour and no error
    """
    git_default_branch_name = pcs.vcs().get_default_major_version()

    major_versions = list(pcs.vcs().walk_major_versions())

    assert len(major_versions) == 1
    major_version = major_versions[0]
    assert major_version.name == git_default_branch_name
    assert store.is_sha1(major_version.head)

    head_major = pcs.vcs().get_head_major_version()
    assert not store.is_sha1(str(head_major))
    assert str(head_major) == git_default_branch_name

    prev_commit = pcs.vcs().get_minor_version_info(pcs.vcs().get_minor_head()).parents[0]
    git_repo = git.Repo(pcs_full_no_prof.get_vcs_path())
    git_repo.git.checkout(prev_commit)
    # Try to detach head
    head_major = pcs.vcs().get_head_major_version()
    assert store.is_sha1(head_major)


def test_saved_states(pcs_full_no_prof):
    """Tests saving states of the repository and check outs

    Expecting correct behaviour, without any raised exceptions
    """

    # Is not dirty
    assert not pcs.vcs().is_dirty()

    with open("file2", "r+") as write_handle:
        previous_state = write_handle.readlines()
        write_handle.write("hello")

    # Should be dirty
    assert pcs.vcs().is_dirty()

    # The changes should be cleared
    with vcs_kit.CleanState():
        assert not pcs.vcs().is_dirty()

        with open("file2", "r") as read_handle:
            new_state = read_handle.readlines()
        assert new_state == previous_state

    head = pcs.vcs().get_minor_head()
    minor_versions = list(map(operator.attrgetter("checksum"), pcs.vcs().walk_minor_versions(head)))

    with open("file2", "w") as write_handle:
        write_handle.write("".join(previous_state))

    with vcs_kit.CleanState():
        # Now try checkout for all of the stuff
        pcs.vcs().checkout(minor_versions[1])
        tracked_files = os.listdir(os.getcwd())
        assert set(tracked_files) == {".perun", ".git", "file1", "file2"}

    # Test that the head was not changed and kept unchanged by CleanState
    assert pcs.vcs().get_minor_head() == head
    # Assert that save state is not used if the dir is not dirty:w
    assert not pcs.vcs().is_dirty() and not pcs.vcs().save_state()[0]

    # Test saving detached head state
    pcs.vcs().checkout(minor_versions[1])
    saved, _ = pcs.vcs().save_state()
    assert not saved


def test_diffs(pcs_full_no_prof):
    """Test getting diff of two versions

    Expecting correct behaviour and no error
    """
    diff = pcs.vcs().minor_versions_diff("HEAD", "HEAD~1")
    assert diff != ""


def test_abstract_base():
    with pytest.raises(TypeError):
        _ = AbstractRepository()


def test_svs(pcs_with_svs):
    """Tests working with svs"""
    svs = pcs_with_svs.vcs()
    assert svs.init({})
    assert svs.get_minor_head() == svs_repository.SINGLE_VERSION_TAG
    assert svs.get_default_major_version() == svs_repository.SINGLE_VERSION_BRANCH
    minors = list(svs.walk_minor_versions(svs_repository.SINGLE_VERSION_TAG))
    assert len(minors) == 1
    assert minors[0].checksum == svs_repository.SINGLE_VERSION_TAG
    majors = list(svs.walk_major_versions())
    assert len(majors) == 1
    assert majors[0].head == svs_repository.SINGLE_VERSION_TAG
    assert majors[0].name == svs_repository.SINGLE_VERSION_BRANCH
    head = svs.get_minor_version_info(svs_repository.SINGLE_VERSION_TAG)
    assert head.desc == "Singleton version"
    assert (
        svs.minor_versions_diff(
            svs_repository.SINGLE_VERSION_TAG, svs_repository.SINGLE_VERSION_TAG
        )
        == ""
    )

    with pytest.raises(AssertionError):
        svs.minor_versions_diff("hello", "world")

    assert svs.get_head_major_version() == svs_repository.SINGLE_VERSION_BRANCH
    assert svs.is_dirty() == False
    svs.check_minor_version_validity(svs_repository.SINGLE_VERSION_TAG)
    with pytest.raises(AssertionError):
        svs.check_minor_version_validity("hello")
    assert (
        svs.massage_parameter(svs_repository.SINGLE_VERSION_TAG, "commit")
        == svs_repository.SINGLE_VERSION_TAG
    )
    assert svs.save_state() == (False, svs_repository.SINGLE_VERSION_TAG)
    # Nothing should fail here
    svs.restore_state(False, svs_repository.SINGLE_VERSION_TAG)
    svs.checkout(svs_repository.SINGLE_VERSION_TAG)
