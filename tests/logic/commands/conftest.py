"""Shared fixtures for the testing of functionality of Perun commands."""

import pytest
import tempfile
import os
import shutil

import perun.core.logic.commands as commands
import perun.core.logic.pcs as pcs
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


@pytest.fixture(scope="module")
def pcs_full():
    """
    Returns:
        PCS: object with performance control system, initialized with some files and stuff
    """
    # Change working dir into the temporary directory
    pcs_path = tempfile.mkdtemp()
    os.chdir(pcs_path)
    commands.init_perun_at(pcs_path, False, False, {'vcs': {'url': '../', 'type': 'git'}})

    # Construct the PCS object
    pcs_obj = pcs.PCS(pcs_path)

    # Initialize git
    vcs.init('git', pcs_path, {})

    # TODO: Populate this with commits and profiles

    yield pcs_obj

    # clean up the directory
    shutil.rmtree(pcs_path)


@pytest.fixture(scope="module")
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


@pytest.fixture(scope="module")
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


@pytest.fixture(scope="module")
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


