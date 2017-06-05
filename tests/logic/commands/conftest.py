"""Shared fixtures for the testing of functionality of Perun commands.

Helper snippets:
    for c in repo.iter_commits():
        print("commit {} \"{}\" {}".format(binascii.hexlify(c.binsha).decode('utf-8'), c.author, c.summary))
"""

import git
import pytest
import os
import shutil
import tempfile

import perun.core.logic.commands as commands
import perun.core.logic.pcs as pcs
import perun.core.logic.store as store
import perun.core.vcs as vcs

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


def get_all_profiles():
    """Helper generator for generating stream of profiles"""
    pool_path = os.path.join(os.path.split(__file__)[0], "to_add_profiles")
    profile_filenames = os.listdir(pool_path)
    profiles = [os.path.join(pool_path, filename) for filename in profile_filenames]
    profiles.sort()
    for profile in profiles:
        yield profile


@pytest.fixture(scope="session")
def valid_profile_pool():
    """
    Returns:
        list: dictionary with profiles that are not assigned and can be distributed
    """
    yield list(filter(lambda p: 'err' not in p, get_all_profiles()))


@pytest.fixture(scope="session")
def error_profile_pool():
    """
    Returns:
        list: list with profiles that contains some kind of error
    """
    yield list(filter(lambda p: 'err' in p, get_all_profiles()))


@pytest.fixture(scope="session")
def stored_profile_pool():
    """
    Returns:
        list: list of stored profiles in the pcs_full
    """
    prof_dirpath = os.path.join(os.path.split(__file__)[0], "full_profiles")
    profiles = [os.path.join(prof_dirpath, prof_file) for prof_file in os.listdir(prof_dirpath)]
    assert len(profiles) == 3
    return profiles


@pytest.fixture(scope="function")
def pcs_full():
    """
    Returns:
        PCS: object with performance control system, initialized with some files and stuff
    """
    # Change working dir into the temporary directory
    profiles = stored_profile_pool()
    pcs_path = tempfile.mkdtemp()
    os.chdir(pcs_path)
    commands.init_perun_at(pcs_path, False, False, {'vcs': {'url': '../', 'type': 'git'}})

    # Construct the PCS object
    pcs_obj = pcs.PCS(pcs_path)

    # Initialize git
    vcs.init('git', pcs_path, {})

    # Populate repo with commits
    repo = git.Repo(pcs_path)

    # Create first commit
    file1 = os.path.join(pcs_path, "file1")
    store.touch_file(file1)
    repo.index.add([file1])
    root = repo.index.commit("root")

    # Create second commit
    file2 = os.path.join(pcs_path, "file2")
    store.touch_file(file2)
    repo.index.add([file2])
    current_head = repo.index.commit("second commit")

    # Populate PCS with profiles
    commands.add(profiles[0], str(root))
    commands.add(profiles[1], str(current_head))
    commands.add(profiles[2], str(current_head))

    # Assert that we have five blobs: 2 for commits and 3 for profiles
    pcs_object_dir = os.path.join(pcs_path, ".perun", "objects")
    number_of_perun_objects = sum(
        len(os.listdir(os.path.join(pcs_object_dir, sub))) for sub in os.listdir(pcs_object_dir)
    )
    assert number_of_perun_objects == 5

    yield pcs_obj

    # clean up the directory
    shutil.rmtree(pcs_path)


@pytest.fixture(scope="function")
def pcs_with_empty_git():
    """
    Returns:
        PCS: object with performance control system initialized with empty git repository
    """
    # Change working dir into the temporary directory
    pcs_path = tempfile.mkdtemp()
    os.chdir(pcs_path)
    commands.init_perun_at(pcs_path, False, False, {'vcs': {'url': '../', 'type': 'git'}})

    # Construct the PCS object
    pcs_obj = pcs.PCS(pcs_path)

    # Initialize git
    vcs.init('git', pcs_path, {})

    yield pcs_obj

    # clean up the directory
    shutil.rmtree(pcs_path)


@pytest.fixture(scope="function")
def pcs_without_vcs():
    """
    Returns:
        PCS: object with performance control system initialized without vcs at all
    """
    # Change working dir into the temporary directory
    pcs_path = tempfile.mkdtemp()
    os.chdir(pcs_path)
    commands.init_perun_at(pcs_path, False, False, {'vcs': {'url': '../', 'type': 'pvcs'}})

    # Construct the PCS object
    pcs_obj = pcs.PCS(pcs_path)

    yield pcs_obj

    # clean up the directory
    shutil.rmtree(pcs_path)


@pytest.fixture(scope="function")
def pcs_with_git_in_separate_dir():
    """
    Returns:
        PCS: object with performance control system initialized with git at different directory
    """
    # Fixme: TODO Implement this
    assert False


@pytest.fixture(scope="function")
def cleandir():
    """Runs the test in the clean new dir, which is purged afterwards"""
    temp_path = tempfile.mkdtemp()
    os.chdir(temp_path)
    yield
    shutil.rmtree(temp_path)


