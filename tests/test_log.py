"""Basic tests for 'perun log' command.

Tests whether the log is correctly outputting the information about currently wrapped repository,
and profiles assigned to minor versions.
"""
from __future__ import annotations

# Standard Imports
import binascii
import os

# Third-Party Imports
import git
import pytest

# Perun Imports
from perun.logic import commands, config
from perun.profile.helpers import ProfileInfo
from perun.utils import decorators
from perun.utils.common import common_kit
from perun.utils.exceptions import (
    NotPerunRepositoryException,
    UnsupportedModuleException,
)
from perun.utils.structs import MinorVersion, ProfileListConfig


@pytest.mark.usefixtures("cleandir")
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
    with pytest.raises(UnsupportedModuleException) as exc:
        commands.log(None)
    assert "'pvcs' is not supported" in str(exc.value)


def test_log_short_error(pcs_with_root, capsys, monkeypatch):
    cfg = config.Config("shared", "", {"format": {"shortlog": "%checksum:6% -> %notexist%"}})
    monkeypatch.setattr("perun.logic.config.shared", lambda: cfg)
    decorators.remove_from_function_args_cache("lookup_key_recursively")

    with pytest.raises(SystemExit):
        commands.log(None, short=True)

    decorators.remove_from_function_args_cache("lookup_key_recursively")
    _, err = capsys.readouterr()
    assert len(err) != 0
    assert "object does not contain 'notexist' attribute" in err


@pytest.mark.usefixtures("cleandir")
def test_log_short(pcs_single_prof, capsys):
    """Test calling 'perun log --short', which outputs shorter info

    Expecting no error, everything on standard output, and list of commits with number of profiles
    for each of them starting from the head.
    """
    git_repo = git.Repo(pcs_single_prof.get_vcs_path())
    commits = list(git_repo.iter_commits())

    commands.log(None, short=True)

    out, err = capsys.readouterr()

    # Assert nothing was printed on error stream
    assert len(err) == 0
    # Assert we have one line per each commit + 1 for header
    assert len(out.split("\n")) - 1 == len(commits) + 1

    for commit in commits:
        c_binsha = binascii.hexlify(commit.binsha).decode("utf-8")[:6]
        c_short_msg = commit.message[:60]

        assert c_binsha in out
        assert c_short_msg in out

    file = os.path.join(os.getcwd(), "file3")
    common_kit.touch_file(file)
    git_repo.index.add([file])
    git_repo.index.commit("new commit")

    commands.log(None, short=True)

    out, err = capsys.readouterr()
    # Assert nothing was printed on error stream
    assert len(err) == 0
    # Assert we have one line per each commit + 1 for header
    assert len(out.split("\n")) - 1 == len(commits) + 2


@pytest.mark.usefixtures("cleandir")
def test_log(pcs_single_prof, capsys):
    """Test calling 'perun log' with working stuff

    Expecting no error, everything on standard output, and list of commits, with full messages
    and number of profiles for each of the starting from the head.
    """
    git_repo = git.Repo(pcs_single_prof.get_vcs_path())
    commits = list(git_repo.iter_commits())

    commands.log(None)

    out, err = capsys.readouterr()

    # Assert nothing was printed on error stream
    assert len(err) == 0
    assert len(out) != 0

    for commit in commits:
        c_binsha = binascii.hexlify(commit.binsha).decode("utf-8")
        c_msg = commit.message
        c_author = str(commit.author)

        assert c_binsha in out
        assert c_msg in out
        assert c_author in out

        for parent in commit.parents:
            assert str(parent) in out


def test_internals(capsys, monkeypatch):
    """Test internal functions used in log and short logs"""
    # Testing incorrect token
    with pytest.raises(SystemExit):
        commands.print_shortlog_token(
            "%short:9", {}, MinorVersion("", "", "", "", "", []), 0, "%short:9"
        )
    _, err = capsys.readouterr()
    assert "incorrect formatting token %short:9" in err

    with pytest.raises(SystemExit):
        commands.print_shortlog_profile_list_header([("fmt_string", "%short:9")], {})
    _, err = capsys.readouterr()
    assert "incorrect formatting token %short:9" in err

    def patched_cwd():
        return "."

    # This test could be better
    monkeypatch.setattr("os.getcwd", patched_cwd)
    test_profile = {
        "header": {"type": "memory", "cmd": "cmd", "workload": "w"},
        "collector_info": {"name": "n"},
        "postprocessors": [],
    }
    pi = ProfileInfo("path", "..", "time", test_profile)
    with pytest.raises(SystemExit):
        commands.print_status_profiles(
            [("fmt_string", "%short:9")],
            ProfileListConfig("pending", True, []),
            {},
            "%short:9",
            [pi],
        )

    with pytest.raises(SystemExit):
        commands.adjust_header_length(
            [("fmt_string", "%short:9")],
            {},
            ProfileListConfig("pending", True, []),
        )
