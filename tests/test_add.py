"""Basic tests for 'perun add' command.

Tests basic functionality of adding profiles to initialized repositories, adding to empty
repositories, adding already added profiles, etc.
"""

# Standard Imports
import binascii
import os

# Third-Party Imports
import git
import pytest
import termcolor

# Perun Imports
from perun.logic import store, index, commands
from perun.utils import timestamps
from perun.utils.common import common_kit
from perun.utils.exceptions import (
    NotPerunRepositoryException,
    UnsupportedModuleException,
    IncorrectProfileFormatException,
    EntryNotFoundException,
    VersionControlSystemException,
)
import perun.testing.utils as test_utils


def assert_before_add(path, commit, valid_profile):
    """Helper assertion for the state of the index before successfully adding a profile

    Arguments:
        path(str): path to the objects of the pcs
        commit(str): sha of the commit
        valid_profile(str): path to the valid profile

    Returns:
        int: number of entries in the index
    """
    with test_utils.open_index(path, commit) as index_handle:

        def compare_profiles(entry):
            """Helper function for looking up the profile"""
            return entry.path == valid_profile

        index.print_index_from_handle(index_handle)
        before_entries_count = store.read_number_of_entries_from_handle(index_handle)
        assert not test_utils.exists_profile_in_index_such_that(index_handle, compare_profiles)
    return before_entries_count


def assert_after_valid_add(path, commit, valid_profile):
    """Helper assertion for the state of the index after successfully adding a profile

    Arguments:
        path(str): path to the objects of the pcs
        commit(str): sha of the working commit
        valid_profile(str): filename of the valid profile that was added to the index

    Returns:
        int: number of entries in the current index
    """
    with test_utils.open_index(path, commit) as index_handle:
        after_entries_count = store.read_number_of_entries_from_handle(index_handle)
        assert successfully_added_profile_in(index_handle, valid_profile)
    return after_entries_count


def assert_after_invalid_add(path, commit, valid_profile):
    """Helper assertion for the state of the index after add resulting into an error

    Arguments:
        path(str): path to the objects of the pcs
        commit(str): sha of the working commit
        valid_profile(str): filename of the valid profile that was added to the index

    Returns:
        int: number of entries in the current index
    """
    with test_utils.open_index(path, commit) as index_handle:
        after_entries_count = store.read_number_of_entries_from_handle(index_handle)
        assert not successfully_added_profile_in(index_handle, valid_profile)
    return after_entries_count


def successfully_added_profile_in(index_handle, valid_profile):
    """Helper assert that checks if the @p valid_profile was successfully added to index
    Arguments:
        index_handle(file): index handle of the corresponding minor version
        valid_profile(str): name of the valid profile
    """
    profile_timestamp = timestamps.timestamp_to_str(os.stat(valid_profile).st_mtime)
    profile_name = os.path.split(valid_profile)[-1]
    try:
        profile_entry = index.lookup_entry_within_index(
            index_handle, lambda entry: entry.path == profile_name, profile_name
        )
        assert profile_entry.path == profile_name
        assert profile_entry.time == profile_timestamp
        return True
    # This sounds weird, but I want to use this function in asserts
    except EntryNotFoundException:
        return False


def test_add_on_empty_repo(pcs_with_empty_git, valid_profile_pool, capsys):
    """Test calling 'perun add' on empty repository

    Expecting an error and system exist as there is no commit, so nothing can be add.
    """
    git_default_branch_name = pcs_with_empty_git.vcs().get_default_major_version()

    assert os.getcwd() == os.path.split(pcs_with_empty_git.get_path())[0]
    before_count = test_utils.count_contents_on_path(pcs_with_empty_git.get_path())

    # Assert that the program ends
    with pytest.raises(SystemExit):
        commands.add([valid_profile_pool[0]], None, keep_profile=True)

    # Assert that nothing was added (rather weak, but should be enough)
    after_count = test_utils.count_contents_on_path(pcs_with_empty_git.get_path())
    assert before_count == after_count

    # Assert that the error message is OK
    _, err = capsys.readouterr()
    expected = (
        "while fetching head minor version: "
        f"Reference at 'refs/heads/{git_default_branch_name}' does not exist"
    )
    assert termcolor.colored(expected, "red", force_color=True) in err.strip()


def test_add_on_no_vcs(pcs_without_vcs, valid_profile_pool):
    """Test calling 'perun add' without having a wrapped vcs

    Expecting and error, as this will call a wrapper over custom "repo" called pvcs, which
    is not supported, but is simply a sane default.
    """
    before_count = test_utils.count_contents_on_path(pcs_without_vcs.get_path())
    vtype, _ = pcs_without_vcs.get_vcs_type_and_url()
    assert vtype == "pvcs"
    with pytest.raises(UnsupportedModuleException) as exc:
        commands.add([valid_profile_pool[0]], None, keep_profile=True)
    assert "'pvcs' is not supported" in str(exc.value)

    # Assert that nothing was added (rather weak, but should be enough)
    after_count = test_utils.count_contents_on_path(pcs_without_vcs.get_path())
    assert before_count == after_count


def test_add(pcs_full, valid_profile_pool):
    """Test calling 'perun add profile hash', i.e. basic functionality

    Expecting no error. Profile is added to the repository, and to the index, to the specified
    minor version.
    """
    git_repo = git.Repo(os.path.split(pcs_full.get_path())[0])
    commits = [binascii.hexlify(c.binsha).decode("utf-8") for c in git_repo.iter_commits()]
    current_head = commits[0]
    before_count = test_utils.count_contents_on_path(pcs_full.get_path())
    obj_path = pcs_full.get_path()

    # First valid profile should be mapped to the same chunk
    for valid_profile in valid_profile_pool:
        valid_profile = test_utils.prepare_profile(
            pcs_full.get_job_directory(), valid_profile, current_head
        )
        # Check that the profile was NOT in the index before
        before_entries_count = assert_before_add(obj_path, current_head, valid_profile)

        # Add the profile to timestamp
        commands.add([valid_profile], current_head, keep_profile=True)

        # Now check, that the profile was successfully added to index, and its entry is valid
        after_entries_count = assert_after_valid_add(obj_path, current_head, valid_profile)
        assert before_entries_count == (after_entries_count - 1)

    # Assert that just len-1 blobs was added, as the second profile has the same structure as
    #   one of the profiles already in the tracking. With new profile format the number may wary
    after_count = test_utils.count_contents_on_path(pcs_full.get_path())
    after_expected = after_count[0] - (len(valid_profile_pool) - 1) - 2
    assert after_expected in (before_count[0], before_count[0] + 1)


def test_add_no_minor(pcs_full, valid_profile_pool):
    """Test calling 'perun add profile hash' without specified minor version

    Expecting no error. Profiles are added to the repository, and to the index, to the head.

    Fixme: Extend with more checks
    """
    git_repo = git.Repo(os.path.split(pcs_full.get_path())[0])
    head = str(git_repo.head.commit)
    before_count = test_utils.count_contents_on_path(pcs_full.get_path())
    obj_path = pcs_full.get_path()

    for valid_profile in valid_profile_pool:
        valid_profile = test_utils.prepare_profile(
            pcs_full.get_job_directory(), valid_profile, head
        )
        # Check that the profile was NOT in the index before
        before_entries_count = assert_before_add(obj_path, head, valid_profile)

        commands.add([valid_profile], None, keep_profile=True)

        # Now check, that the profile was successfully added to index, and its entry is valid
        after_entries_count = assert_after_valid_add(obj_path, head, valid_profile)
        assert before_entries_count == (after_entries_count - 1)

    # Assert that just len-1 blobs was added, as the second profile has the same structure as
    #   one of the profiles already in the tracking. With new profile format the number may wary
    after_count = test_utils.count_contents_on_path(pcs_full.get_path())
    after_expected = after_count[0] - (len(valid_profile_pool) - 1) - 2
    assert after_expected in (before_count[0], before_count[0] + 1)


def test_add_wrong_minor(pcs_full_no_prof, valid_profile_pool):
    """Test calling 'perun add profile hash' with hash not occuring in wrapped VCS

    Expecting raising an exception, that the specified minor version is wrong.
    """
    git_repo = git.Repo(os.path.split(pcs_full_no_prof.get_path())[0])
    commits = [binascii.hexlify(c.binsha).decode("utf-8") for c in git_repo.iter_commits()]
    wrong_commit = commits[0][:20] + commits[1][20:]
    assert len(wrong_commit) == 40
    assert wrong_commit != commits[0] and wrong_commit != commits[1]
    before_count = test_utils.count_contents_on_path(pcs_full_no_prof.get_path())

    with pytest.raises(VersionControlSystemException):
        commands.add([valid_profile_pool[0]], wrong_commit, keep_profile=True)

    # Assert that nothing was added (rather weak, but should be enough)
    after_count = test_utils.count_contents_on_path(pcs_full_no_prof.get_path())
    assert before_count == after_count


def test_add_wrong_profile(pcs_full, error_profile_pool, capsys):
    """Test calling 'perun add profile hash' with profile in wrong format

    Expecting raising an exception, that the profile is wrong.
    """
    git_repo = git.Repo(os.path.split(pcs_full.get_path())[0])
    head = str(git_repo.head.commit)
    before_count = test_utils.count_contents_on_path(pcs_full.get_path())

    for error_profile in error_profile_pool:
        before_entries_count = assert_before_add(pcs_full.get_path(), head, error_profile)
        with pytest.raises(IncorrectProfileFormatException) as exc:
            commands.add([error_profile], None, keep_profile=True)
        assert "not in profile format" in str(exc.value)

        # Assert that the profile was not added into the index
        after_entries_count = assert_after_invalid_add(pcs_full.get_path(), head, error_profile)
        assert before_entries_count == after_entries_count

    # Assert that nothing was added (rather weak, but should be enough)
    after_count = test_utils.count_contents_on_path(pcs_full.get_path())
    assert before_count == after_count

    # Try to assert adding not existing profile
    with pytest.raises(SystemExit):
        commands.add(["notexisting.perf"], None, keep_profile=True)
    after_count = test_utils.count_contents_on_path(pcs_full.get_path())
    assert before_count == after_count

    out, err = capsys.readouterr()
    assert "Profile does not exist" in out
    assert "Registration failed for - 1 profile" in common_kit.escape_ansi(err)


def test_add_existing(pcs_full, valid_profile_pool, capsys):
    """Test calling 'perun add profile hash', when the profile is already assigned to current

    Expecting probably to warn the user, that the profile is already assigned and don't change
    anything or add new redundant entry for that.

    Fixme: Extend with more checks
    """
    git_repo = git.Repo(os.path.split(pcs_full.get_path())[0])
    head = str(git_repo.head.commit)
    before_count = test_utils.count_contents_on_path(pcs_full.get_path())
    obj_path = pcs_full.get_path()

    for valid_profile in valid_profile_pool:
        valid_profile = test_utils.prepare_profile(
            pcs_full.get_job_directory(), valid_profile, head
        )
        # Check that the profile was NOT in the index before
        before_entries_count = assert_before_add(obj_path, head, valid_profile)

        commands.add([valid_profile], None, keep_profile=True)

        # Assert that the profile was successfully added to the index
        middle_entries_count = assert_after_valid_add(obj_path, head, valid_profile)
        assert before_entries_count == (middle_entries_count - 1)

        commands.add([valid_profile], None, keep_profile=True)

        # Assert that nothing was added to the index
        after_entries_count = assert_after_valid_add(obj_path, head, valid_profile)
        assert middle_entries_count == after_entries_count

        # Check that some kind of message was written to user
        out, _ = capsys.readouterr()
        assert "already registered in" in out

    # Assert that just len-1 blobs was added, as the second profile has the same structure as
    #   one of the profiles already in the tracking. With new profile format the number may wary
    after_count = test_utils.count_contents_on_path(pcs_full.get_path())
    after_expected = after_count[0] - (len(valid_profile_pool) - 1) - 2
    assert after_expected in (before_count[0], before_count[0] + 1)


@pytest.mark.usefixtures("cleandir")
def test_add_outside_pcs(valid_profile_pool):
    """Test calling 'perun add outside of the scope of the PCS wrapper

    Expecting an exception NotPerunRepositoryException, as we are outside of the perun scope,
    and thus should not do anything, should be caught on the CLI/UI level
    """
    with pytest.raises(NotPerunRepositoryException):
        commands.add([valid_profile_pool[0]], None, keep_profile=True)
