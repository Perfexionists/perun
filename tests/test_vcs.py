"""Basic tests for checking the correctness of the VCS modules"""

import git
import os
import operator

import perun.vcs as vcs
import perun.logic.store as store

__author__ = 'Tomas Fiedor'


def test_on_empty_git(pcs_with_empty_git):
    """Tests how vcs handles the git without any commits (should not fail or so)

    Excepts handled errors and not uncaught shit
    """
    # Assert that when we walk with bogus head then nothing is returned
    assert len(list(vcs.walk_minor_versions(""))) == 0


def test_major_versions(pcs_full):
    """Test whether getting the major version for given VCS is correct

    Expecting correct behaviour and no error
    """
    git_config_parser = git.config.GitConfigParser()
    git_default_branch_name = git_config_parser.get_value('init', 'defaultBranch', 'master')

    major_versions = list(vcs.walk_major_versions())

    assert len(major_versions) == 1
    major_version = major_versions[0]
    assert major_version.name == git_default_branch_name
    assert store.is_sha1(major_version.head)

    head_major = vcs.get_head_major_version()
    assert not store.is_sha1(str(head_major))
    assert str(head_major) == git_default_branch_name

    prev_commit = vcs.get_minor_version_info(vcs.get_minor_head()).parents[0]
    git_repo = git.Repo(pcs_full.get_vcs_path())
    git_repo.git.checkout(prev_commit)
    # Try to detach head
    head_major = vcs.get_head_major_version()
    assert store.is_sha1(head_major)


def test_saved_states(pcs_full):
    """Tests saving states of the repository and check outs

    Expecting correct behaviour, without any raised exceptions
    """

    # Is not dirty
    assert not vcs.is_dirty()

    with open("file2", "r+") as write_handle:
        previous_state = write_handle.readlines()
        write_handle.write("hello")

    # Should be dirty
    assert vcs.is_dirty()

    # The changes should be cleared
    with vcs.CleanState():
        assert not vcs.is_dirty()

        with open("file2", "r") as read_handle:
            new_state = read_handle.readlines()
        assert new_state == previous_state

    head = vcs.get_minor_head()
    minor_versions = list(
        map(operator.attrgetter('checksum'), vcs.walk_minor_versions(head))
    )

    with open("file2", "w") as write_handle:
        write_handle.write("".join(previous_state))

    with vcs.CleanState():
        # Now try checkout for all of the stuff
        vcs.checkout(minor_versions[1])
        tracked_files = os.listdir(os.getcwd())
        assert set(tracked_files) == {'.perun', '.git', 'file1'}

    # Test that the head was not changed and kept unchanged by CleanState
    assert vcs.get_minor_head() == head
    # Assert that save state is not used if the dir is not dirty:w
    assert not vcs.is_dirty() and not vcs.save_state()[0]

    # Test saving detached head state
    vcs.checkout(minor_versions[1])
    saved, _ = vcs.save_state()
    assert not saved


def test_diffs(pcs_full):
    """Test getting diff of two versions

    Expecting correct behaviour and no error
    """
    diff = vcs.minor_versions_diff("HEAD", "HEAD~1")
    assert diff != ""
