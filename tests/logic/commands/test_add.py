"""Basic tests for 'perun add' command.

Tests basic functionality of adding profiles to initialized repositories, adding to empty
repositories, adding already added profiles, etc.
"""

import binascii
import git
import os
import pytest
import termcolor

import perun.core.logic.commands as commands
import perun.core.logic.store as store
import perun.utils.timestamps as timestamps

from perun.utils.exceptions import NotPerunRepositoryException, UnsupportedModuleException, \
    IncorrectProfileFormatException, EntryNotFoundException, VersionControlSystemException

__author__ = 'Tomas Fiedor'


def list_contents_on_path(path):
    """Helper function for listing the contents of the path

    Arguments:
        path(str): path to the director which we will list
    """
    for root, dirs, files in os.walk(path):
        for file in files:
            print("file: ", os.path.join(root, file))
        for d in dirs:
            print("dirs: ", os.path.join(root, d))


def count_contents_on_path(path):
    """Helper function for counting the contents of the path

    Arguments:
        path(str): path to the director which we will list

    Returns:
        (int, int): (file number, dir number) on path
    """
    file_number = 0
    dir_number = 0
    for root, dirs, files in os.walk(path):
        for _ in files:
            file_number += 1
        for _ in dirs:
            dir_number += 1
    return file_number, dir_number


def open_index(pcs_path, minor_version):
    """Helper function for opening handle of the index

    This encapsulates obtaining the full path to the given index

    Arguments:
        pcs_path(str): path to the pcs
        minor_version(str): sha minor version representation
    """
    assert store.is_sha1(minor_version)
    object_dir_path = os.path.join(pcs_path, 'objects')

    _, minor_version_index = store.split_object_name(object_dir_path, minor_version)
    return open(minor_version_index, 'rb+')


def exists_profile_in_index_such_that(index_handle, pred):
    """Helper assert to check, if there exists any profile in index such that pred holds.

    Arguments:
        index_handle(file): handle for the index
        pred(lambda): predicate over the index entry
    """
    for entry in store.walk_index(index_handle):
        if pred(entry):
            return True
    else:
        return False


def assert_before_add(path, commit, valid_profile):
    """Helper assertion for the state of the index before successfully adding a profile

    Arguments:
        path(str): path to the objects of the pcs
        commit(str): sha of the commit
        valid_profile(str): path to the valid profile

    Returns:
        int: number of entries in the index
    """
    with open_index(path, commit) as index_handle:
        store.print_index_from_handle(index_handle)
        before_number_of_entries = store.read_number_of_entries_from_handle(index_handle)
        assert not exists_profile_in_index_such_that(index_handle,
                                                     lambda entry: entry.path == valid_profile)
    return before_number_of_entries


def assert_after_valid_add(path, commit, valid_profile):
    """Helper assertion for the state of the index after successfully adding a profile

    Arguments:
        path(str): path to the objects of the pcs
        commit(str): sha of the working commit
        valid_profile(str): filename of the valid profile that was added to the index

    Returns:
        int: number of entries in the current index
    """
    with open_index(path, commit) as index_handle:
        after_number_of_entries = store.read_number_of_entries_from_handle(index_handle)
        assert successfully_added_profile_in(index_handle, valid_profile)
    return after_number_of_entries


def assert_after_invalid_add(path, commit, valid_profile):
    """Helper assertion for the state of the index after add resulting into an error

    Arguments:
        path(str): path to the objects of the pcs
        commit(str): sha of the working commit
        valid_profile(str): filename of the valid profile that was added to the index

    Returns:
        int: number of entries in the current index
    """
    with open_index(path, commit) as index_handle:
        after_number_of_entries = store.read_number_of_entries_from_handle(index_handle)
        assert not successfully_added_profile_in(index_handle, valid_profile)
    return after_number_of_entries


def successfully_added_profile_in(index_handle, valid_profile):
    """Helper assert that checks if the @p valid_profile was successfully added to index
    Arguments:
        index_handle(file): index handle of the corresponding minor version
        valid_profile(str): name of the valid profile
    """
    profile_timestamp = timestamps.timestamp_to_str(os.stat(valid_profile).st_mtime)
    try:
        profile_entry \
            = store.lookup_entry_within_index(index_handle,
                                              lambda entry: entry.path == valid_profile)
        assert profile_entry.path == valid_profile
        assert profile_entry.time == profile_timestamp
        return True
    # This sounds weird, but I want to use this function in asserts
    except EntryNotFoundException:
        return False
    except AssertionError:
        return False


def test_add_on_empty_repo(pcs_with_empty_git, valid_profile_pool, capsys):
    """Test calling 'perun add' on empty repository

    Expecting an error and system exist as there is no commit, so nothing can be add.
    """
    assert os.getcwd() == os.path.split(pcs_with_empty_git.path)[0]
    before_count = count_contents_on_path(pcs_with_empty_git.path)

    # Assert that the program ends
    with pytest.raises(SystemExit):
        commands.add(valid_profile_pool[0], None)

    # Assert that nothing was added (rather weak, but should be enough)
    after_count = count_contents_on_path(pcs_with_empty_git.path)
    assert before_count == after_count

    # Assert that the error message is OK
    out, err = capsys.readouterr()
    expected = "fatal: could not obtain head minor version: " \
               "Reference at 'refs/heads/master' does not exist"
    assert err.strip() == termcolor.colored(expected, 'red')


def test_add_on_no_vcs(pcs_without_vcs, valid_profile_pool):
    """Test calling 'perun add' without having a wrapped vcs

    Expecting and error, as this will call a wrapper over custom "repo" called pvcs, which
    is not supported, but is simply a sane default.
    """
    before_count = count_contents_on_path(pcs_without_vcs.path)
    assert pcs_without_vcs.vcs_type == 'pvcs'
    with pytest.raises(UnsupportedModuleException):
        commands.add(valid_profile_pool[0], None)

    # Assert that nothing was added (rather weak, but should be enough)
    after_count = count_contents_on_path(pcs_without_vcs.path)
    assert before_count == after_count


def test_add(pcs_full, valid_profile_pool):
    """Test calling 'perun add profile hash', i.e. basic functionality

    Expecting no error. Profile is added to the repository, and to the index, to the specified
    minor version.
    """
    git_repo = git.Repo(os.path.split(pcs_full.path)[0])
    commits = [binascii.hexlify(c.binsha).decode('utf-8') for c in git_repo.iter_commits()]
    working_commit = commits[0]
    before_count = count_contents_on_path(pcs_full.path)
    obj_path = pcs_full.path

    # First valid profile should be mapped to the same chunk
    for valid_profile in valid_profile_pool:
        # Check that the profile was NOT in the index before
        before_number_of_entries = assert_before_add(obj_path, working_commit, valid_profile)

        # Add the profile to timestamp
        commands.add(valid_profile, working_commit)

        # Now check, that the profile was successfully added to index, and its entry is valid
        after_number_of_entries = assert_after_valid_add(obj_path, working_commit, valid_profile)
        assert before_number_of_entries == (after_number_of_entries - 1)

    # Assert that just len-1 blobs was added, as the second profile has the same structure as
    #   one of the profiles already in the tracking
    after_count = count_contents_on_path(pcs_full.path)
    assert before_count[1] == (after_count[1] - (len(valid_profile_pool) - 1))


def test_add_no_minor(pcs_full, valid_profile_pool):
    """Test calling 'perun add profile hash' without specified minor version

    Expecting no error. Profiles are added to the repository, and to the index, to the head.

    Fixme: Extend with more checks
    """
    git_repo = git.Repo(os.path.split(pcs_full.path)[0])
    head = str(git_repo.head.commit)
    before_count = count_contents_on_path(pcs_full.path)
    obj_path = pcs_full.path

    for valid_profile in valid_profile_pool:
        # Check that the profile was NOT in the index before
        before_number_of_entries = assert_before_add(obj_path, head, valid_profile)

        commands.add(valid_profile, None)

        # Now check, that the profile was successfully added to index, and its entry is valid
        after_number_of_entries = assert_after_valid_add(obj_path, head, valid_profile)
        assert before_number_of_entries == (after_number_of_entries - 1)

    # Assert that just len-1 blobs was added, as the second profile has the same structure as
    #   one of the profiles already in the tracking
    after_count = count_contents_on_path(pcs_full.path)
    assert before_count[1] == (after_count[1] - (len(valid_profile_pool) - 1))


def test_add_wrong_minor(pcs_full, valid_profile_pool):
    """Test calling 'perun add profile hash' with hash not occuring in wrapped VCS

    Expecting raising an exception, that the specified minor version is wrong.
    """
    git_repo = git.Repo(os.path.split(pcs_full.path)[0])
    commits = [binascii.hexlify(c.binsha).decode('utf-8') for c in git_repo.iter_commits()]
    wrong_commit = commits[0][:20] + commits[1][20:]
    assert len(wrong_commit) == 40
    assert wrong_commit != commits[0] and wrong_commit != commits[1]
    before_count = count_contents_on_path(pcs_full.path)

    with pytest.raises(VersionControlSystemException):
        commands.add(valid_profile_pool[0], wrong_commit)

    # Assert that nothing was added (rather weak, but should be enough)
    after_count = count_contents_on_path(pcs_full.path)
    assert before_count == after_count


def test_add_wrong_profile(pcs_full, error_profile_pool):
    """Test calling 'perun add profile hash' with profile in wrong format

    Expecting raising an exception, that the profile is wrong.
    """
    git_repo = git.Repo(os.path.split(pcs_full.path)[0])
    head = str(git_repo.head.commit)
    before_count = count_contents_on_path(pcs_full.path)

    for error_profile in error_profile_pool:
        before_number_of_entries = assert_before_add(pcs_full.path, head, error_profile)
        with pytest.raises(IncorrectProfileFormatException):
            commands.add(error_profile, None)

        # Assert that the profile was not added into the index
        after_number_of_entries = assert_after_invalid_add(pcs_full.path, head, error_profile)
        assert before_number_of_entries == after_number_of_entries

    # Assert that nothing was added (rather weak, but should be enough)
    after_count = count_contents_on_path(pcs_full.path)
    assert before_count == after_count


def test_add_existing(pcs_full, valid_profile_pool, capsys):
    """Test calling 'perun add profile hash', when the profile is already assigned to current

    Expecting probably to warn the user, that the profile is already assigned and don't change
    anything or add new redundant entry for that.

    Fixme: Extend with more checks
    """
    git_repo = git.Repo(os.path.split(pcs_full.path)[0])
    head = str(git_repo.head.commit)
    before_count = count_contents_on_path(pcs_full.path)
    obj_path = pcs_full.path

    for valid_profile in valid_profile_pool:
        # Check that the profile was NOT in the index before
        before_number_of_entries = assert_before_add(obj_path, head, valid_profile)

        commands.add(valid_profile, None)

        # Assert that the profile was successfully added to the index
        middle_number_of_entries = assert_after_valid_add(obj_path, head, valid_profile)
        assert before_number_of_entries == (middle_number_of_entries - 1)

        commands.add(valid_profile, None)

        # Assert that nothing was added to the index
        after_number_of_entries = assert_after_valid_add(obj_path, head, valid_profile)
        assert middle_number_of_entries == after_number_of_entries

        # Check that some kind of message was written to user
        out, _ = capsys.readouterr()
        assert 'already registered in' in out

    # Assert that just len-1 blobs was added, as the second profile has the same structure as
    #   one of the profiles already in the tracking
    after_count = count_contents_on_path(pcs_full.path)
    assert before_count[1] == (after_count[1] - (len(valid_profile_pool) - 1))


@pytest.mark.usefixtures('cleandir')
def test_add_outside_pcs(valid_profile_pool):
    """Test calling 'perun add outside of the scope of the PCS wrapper

    Expecting an exception NotPerunRepositoryException, as we are outside of the perun scope,
    and thus should not do anything, should be caught on the CLI/UI level
    """
    with pytest.raises(NotPerunRepositoryException):
        commands.add(valid_profile_pool[0], None)
