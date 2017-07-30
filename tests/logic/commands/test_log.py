"""Basic tests for 'perun log' command.

Tests whether the log is correctly outputting the information about currently wrapped repository,
and profiles assigned to minor versions.
"""

import binascii

import git
import pytest

import perun.logic.commands as commands
from perun.utils.exceptions import NotPerunRepositoryException, UnsupportedModuleException

__author__ = 'Tomas Fiedor'


@pytest.mark.usefixtures('cleandir')
def test_log_not_in_pcs():
    """Test calling 'perun log' when not in the scope of the perun pcs

    Expecting ending with error, as we are not inside the perun repository
    """
    with pytest.raises(NotPerunRepositoryException):
        commands.log(None)


def test_log_on_empty_vcs(pcs_with_empty_git):
    """Test calling 'perun log', when there is no commit yet

    Expecting ending of the system, without printing anything at all
    """
    with pytest.raises(SystemExit):
        commands.log(None)


def test_log_on_no_vcs(pcs_without_vcs):
    """Test calling 'perun log', when there is no VCS at all

    Expecting error, as this will call a wrapper over custom "repo" called pvcs, which
    is not supported but is simply a sane default
    """
    with pytest.raises(UnsupportedModuleException):
        commands.log(None)


def test_log_short(pcs_full, capsys):
    """Test calling 'perun log --short', which outputs shorter info

    Expecting no error, everything on standard output, and list of commits with number of profiles
    for each of them starting from the head.
    """
    git_repo = git.Repo(pcs_full.vcs_path)
    commits = list(git_repo.iter_commits())

    commands.log(None, short=True)

    out, err = capsys.readouterr()

    # Assert nothing was printed on error stream
    assert len(err) == 0
    # Assert we have one line per each commit + 1 for header
    assert len(out.split('\n')) - 1 == len(commits) + 1

    for commit in commits:
        c_binsha = binascii.hexlify(commit.binsha).decode('utf-8')[:6]
        c_short_msg = commit.message[:60]

        assert c_binsha in out
        assert c_short_msg in out


def test_log(pcs_full, capsys):
    """Test calling 'perun log' with working stuff

    Expecting no error, everything on standard output, and list of commits, with full messages
    and number of profiles for each of the starting from the head.
    """
    git_repo = git.Repo(pcs_full.vcs_path)
    commits = list(git_repo.iter_commits())

    commands.log(None)

    out, err = capsys.readouterr()

    # Assert nothing was printed on error stream
    assert len(err) == 0

    for commit in commits:
        c_binsha = binascii.hexlify(commit.binsha).decode('utf-8')
        c_msg = commit.message
        c_author = str(commit.author)

        assert c_binsha in out
        assert c_msg in out
        assert c_author in out

        for parent in commit.parents:
            assert str(parent) in out
