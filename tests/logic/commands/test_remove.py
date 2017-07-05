"""Basic tests for 'perun rm' command.

Tests removing of profiles, within and outside of the scope of the wrapped perun system,
removing nonexistent profiles, etc.
"""

import os

import git
import perun.logic.store as store
import pytest

import perun.logic.commands as commands
from perun.utils.exceptions import NotPerunRepositoryException, EntryNotFoundException

__author__ = 'Tomas Fiedor'


@pytest.mark.usefixtures('cleandir')
def test_rm_outside_pcs(stored_profile_pool):
    """Test calling 'perun rm', when outside of the scope of the perun repository

    Expecting an exception NotPerunRepositoryExpcetion, as we are outside of the perun scope,
    and thus should not do anything, should be caught on the CLI/UI level
    """
    with pytest.raises(NotPerunRepositoryException):
        # Remove first profile from the head
        commands.remove(stored_profile_pool[0], None)


def test_rm_on_empty_repo(pcs_with_empty_git, stored_profile_pool, capsys):
    """Test calling 'perun rm', when the wrapped VCS is empty"""
    with pytest.raises(SystemExit):
        commands.remove(stored_profile_pool[0], None)

    # Test that nothing is printed on out and something is printed on err
    out, err = capsys.readouterr()
    assert out == ''
    assert err != '' and 'fatal' in err


def test_rm_no_profiles(helpers, pcs_full, capsys):
    """Test calling 'perun rm', when there are no profiles to be removed

    Expecting error message and nothing removed at all
    """
    before_count = helpers.count_contents_on_path(pcs_full.path)

    git_repo = git.Repo(pcs_full.vcs_path)
    file = os.path.join(os.getcwd(), 'file3')
    store.touch_file(file)
    git_repo.index.add([file])
    git_repo.index.commit("new commit")

    with pytest.raises(EntryNotFoundException):
        commands.remove('nonexistent.perf', None)

    out, _ = capsys.readouterr()
    assert out == ''

    # Assert that nothing was removed
    after_count = helpers.count_contents_on_path(pcs_full.path)
    assert before_count == after_count


def test_rm_nonexistent(helpers, pcs_full, capsys):
    """Test calling 'perun rm', trying to remove nonexistent profile

    Expecting error message and nothing removed at all
    """
    before_count = helpers.count_contents_on_path(pcs_full.path)
    with pytest.raises(EntryNotFoundException):
        commands.remove('nonexistent.perf', None)

    out, _ = capsys.readouterr()
    assert out == ''

    # Assert that nothing was removed
    after_count = helpers.count_contents_on_path(pcs_full.path)
    assert before_count == after_count


def test_rm(helpers, pcs_full, stored_profile_pool, capsys):
    """Test calling 'perun rm', expecting normal behaviour

    Expecting removing the profile from the index, keeping the number of files
    intact.
    """
    before_count = helpers.count_contents_on_path(pcs_full.path)

    git_repo = git.Repo(pcs_full.vcs_path)
    head = str(git_repo.head.commit)

    # We need relative path
    deleted_profile = os.path.split(stored_profile_pool[1])[-1]

    def entry_contains_profile(entry):
        """Helper function for looking up entry to be deleted"""
        return deleted_profile == entry.path

    with helpers.open_index(pcs_full.path, head) as index_handle:
        assert helpers.exists_profile_in_index_such_that(index_handle, entry_contains_profile)

    commands.remove(deleted_profile, None)

    with helpers.open_index(pcs_full.path, head) as index_handle:
        assert not helpers.exists_profile_in_index_such_that(index_handle, entry_contains_profile)

    _, err = capsys.readouterr()
    assert len(err) == 0

    # Assert that nothing was removed
    after_count = helpers.count_contents_on_path(pcs_full.path)
    assert before_count == after_count
