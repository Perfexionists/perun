"""Basic tests for 'perun rm' command.

Tests removing of profiles, within and outside of the scope of the wrapped perun system,
removing nonexistent profiles, etc.
"""
from __future__ import annotations

# Standard Imports
import os

# Third-Party Imports
import git
import pytest

# Perun Imports
from perun.logic import commands
from perun.utils.common import common_kit
from perun.utils.exceptions import NotPerunRepositoryException, EntryNotFoundException
import perun.testing.utils as test_utils


@pytest.mark.usefixtures("cleandir")
def test_rm_outside_pcs():
    """Test calling 'perun rm', when outside of the scope of the perun repository

    Expecting an exception NotPerunRepositoryExpcetion, as we are outside of the perun scope,
    and thus should not do anything, should be caught on the CLI/UI level
    """
    # Any profile will do
    profile = test_utils.load_profilename("postprocess_profiles", "full_computation.perf")
    with pytest.raises(NotPerunRepositoryException):
        # Remove first profile from the head
        commands.remove_from_index([profile], None)


def test_rm_on_empty_repo(pcs_with_empty_git, capsys):
    """Test calling 'perun rm', when the wrapped VCS is empty"""
    # Any profile will do
    profile = test_utils.load_profilename("postprocess_profiles", "full_computation.perf")
    with pytest.raises(SystemExit):
        commands.remove_from_index([profile], None)

    # Test that nothing is printed on out and something is printed on err
    out, err = capsys.readouterr()
    assert out == ""
    assert err != "" and "error" in err.lower()


def test_rm_no_profiles(pcs_full_no_prof, capsys):
    """Test calling 'perun rm', when there are no profiles to be removed

    Expecting error message and nothing removed at all
    """
    before_count = test_utils.count_contents_on_path(pcs_full_no_prof.get_path())

    git_repo = git.Repo(pcs_full_no_prof.get_vcs_path())
    file = os.path.join(os.getcwd(), "file3")
    common_kit.touch_file(file)
    git_repo.index.add([file])
    git_repo.index.commit("new commit")

    with pytest.raises(EntryNotFoundException) as exc:
        commands.remove_from_index(["nonexistent.perf"], None)
    assert "none of the entries found in the index" in str(exc.value)

    out, _ = capsys.readouterr()
    assert out == ""

    # Assert that nothing was removed
    after_count = test_utils.count_contents_on_path(pcs_full_no_prof.get_path())
    assert before_count == after_count


def test_rm_nonexistent(pcs_single_prof, capsys):
    """Test calling 'perun rm', trying to remove nonexistent profile

    Expecting error message and nothing removed at all
    """
    before_count = test_utils.count_contents_on_path(pcs_single_prof.get_path())
    commands.remove_from_index(["nonexistent.perf"], None)
    out, _ = capsys.readouterr()

    assert "not found" in out
    assert "deregistered" not in out and "deleted" not in out
    assert "Nothing to remove" in out

    # Assert that nothing was removed
    after_count = test_utils.count_contents_on_path(pcs_single_prof.get_path())
    assert before_count == after_count


def test_rm(pcs_full, stored_profile_pool, capsys):
    """Test calling 'perun rm', expecting normal behaviour

    Expecting removing the profile from the index, keeping the number of files
    intact.
    """
    before_count = test_utils.count_contents_on_path(pcs_full.get_path())

    git_repo = git.Repo(pcs_full.get_vcs_path())
    head = str(git_repo.head.commit)

    # We need relative path
    deleted_profile = os.path.split(stored_profile_pool[1])[-1]

    def entry_contains_profile(entry):
        """Helper function for looking up entry to be deleted"""
        return deleted_profile == entry.path

    with test_utils.open_index(pcs_full.get_path(), head) as index_handle:
        assert test_utils.exists_profile_in_index_such_that(index_handle, entry_contains_profile)

    commands.remove_from_index([deleted_profile], None)

    with test_utils.open_index(pcs_full.get_path(), head) as index_handle:
        assert not test_utils.exists_profile_in_index_such_that(
            index_handle, entry_contains_profile
        )

    _, err = capsys.readouterr()
    assert len(err) == 0

    # Assert that nothing was removed
    after_count = test_utils.count_contents_on_path(pcs_full.get_path())
    assert before_count == after_count


def test_rm_pending(pcs_with_root, stored_profile_pool):
    """Basic test of removing pending from the perun"""
    jobs_dir = pcs_with_root.get_job_directory()

    test_utils.populate_repo_with_untracked_profiles(pcs_with_root.get_path(), stored_profile_pool)
    number_of_pending = len(os.listdir(jobs_dir))
    assert number_of_pending == 3

    removed_profiles = [os.path.join(jobs_dir, prof) for prof in os.listdir(jobs_dir)]
    commands.remove_from_pending(removed_profiles)
    number_of_pending = len(os.listdir(jobs_dir))
    assert number_of_pending == 0
