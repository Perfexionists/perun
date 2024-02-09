"""Basic tests for 'perun status' command.

Fixme: Add test for detached head

Tests whether the perun correctly displays the status of the repository, with all of the extreme
cases, etc."""
from __future__ import annotations

# Standard Imports
import collections
import json
import os
import re

# Third-Party Imports
import git
import pytest

# Perun Imports
from perun.logic import config, commands
from perun.utils import timestamps, decorators
from perun.utils.common import common_kit
from perun.utils.exceptions import NotPerunRepositoryException
import perun.testing.utils as test_utils


TIMESTAMP_RE = re.compile(r"-[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{2}.perf")


def analyze_profile_pool(profile_pool):
    """
    Arguments:
        profile_pool(list): list of profiles

    Returns:
        dict: dictionary mapping types of profiles to number of profiles in that pool
    """
    types_to_count = collections.defaultdict(int)
    for profile in profile_pool:
        with open(profile, "r") as profile_handle:
            profile_contents = json.load(profile_handle)
            types_to_count[profile_contents["header"]["type"]] += 1
    return types_to_count


def profile_pool_to_info(profile_pool):
    """
    Arguments:
        profile_pool(list): list of profiles

    Returns:
        generator: yield profile information as tuple (type, split name, time)
    """
    for profile in profile_pool:
        with open(profile, "r") as profile_handle:
            profile_contents = json.load(profile_handle)
            profile_time = timestamps.timestamp_to_str(os.stat(profile).st_mtime)
            yield (
                profile_contents["header"]["type"],
                profile_contents["collector_info"]["name"],
                profile_time,
            )


def assert_head_info(header_line, git_repo):
    """Helper assert that checks that the info about head is written as it should

    Arguments:
        header_line(str): line containing header info
    """
    head_rev = str(git_repo.head.commit)
    head_branch = str(git_repo.active_branch)

    assert head_rev in header_line
    assert head_branch in header_line


def assert_tracked_overview_info(tracked_profiles_info, stored_profiles):
    """Helper assertion, that checks output according to the expected number of stored profiles

    Arguments:
        tracked_profiles_info(str): line containing info about number of tracked profiles
        stored_profiles(list): list of stored profiles in the repository
    """
    number_of_profiles = len(stored_profiles)
    if number_of_profiles:
        types_to_counts = analyze_profile_pool(stored_profiles)
        assert f"{number_of_profiles} tracked profiles" in tracked_profiles_info
        for profile_type, type_count in types_to_counts.items():
            assert f"{type_count} {profile_type}" in tracked_profiles_info
    else:
        assert "(no tracked profiles)" in tracked_profiles_info


def assert_untracked_overview_info(untracked_profiles_info, untracked_profiles):
    """Helper assertion, that checks output according to the expected number of profiles

    Arguments:
        untracked_profiles_info(str): line containing info about number of untracked profiles
        untracked_profiles(list): list of untracked profiles
    """
    number_of_untracked = len(untracked_profiles)
    if number_of_untracked:
        assert f"{number_of_untracked} untracked profiles" in untracked_profiles_info
    else:
        assert "(no untracked profiles)" in untracked_profiles_info


def assert_short_info(out, git_repo, stored_profiles, untracked_profiles):
    """Helper assert for checking short output

    Arguments:
        out(list): list of split lines of output
        git_repo(git.Repo): git repository wrapper
        stored_profiles(list): list of stored profiles in current branch
        untracked_profiles(list): list of untracked profiles
    """
    # Assert there is 1. header, 2. tracked info, 3. untracked info, 4+5 is degradation info 6. eof
    assert len(out) == 6

    # Check first the header, whether it contains the ref and header
    assert_head_info(out[0], git_repo)

    # Check tracked profiles
    assert_tracked_overview_info(out[1], stored_profiles)

    # Check untracked profiles
    assert_untracked_overview_info(out[2], untracked_profiles)


def assert_printed_profiles(profile_info, out):
    """Helper assert for checking how the profiles were outputed

    Arguments:
        profile_info(set): set with profiles to be checked
        out(str): line which we are checking
    """
    for profile_entry in profile_info:
        p_type, p_name, p_time = profile_entry
        if p_name in out:
            assert p_type in out
            assert p_time in out
            profile_info.remove(profile_entry)
            break


def assert_info(out, git_repo, stored_profiles, untracked_profiles):
    """Helper assert for checking long output

    Arguments:
        out(list): list of output from standard stream
        git_repo(git.Repo): git repository wrapper
        stored_profiles(list): list of stored profiles in current branch
        untracked_profiles(list): list of untracked profiles
    """
    joined_output = "\n".join(out)
    assert_head_info(out[0], git_repo)

    for no, line in enumerate(out):
        print(no, line)

    # Assert the commit message was correctly displayed
    head_commit = git_repo.head.commit
    head_msg = str(head_commit.message)
    assert str(head_commit.author) in joined_output
    assert head_msg in joined_output
    assert str(head_commit.parents[0]) in joined_output

    # Assert that the head message is oneliner
    assert "\n" not in head_msg
    i = out.index(head_msg) + 1

    assert_tracked_overview_info(out[i], stored_profiles)
    i += 1
    if stored_profiles:
        # Skip empty line and horizontal line
        i += 4
        count = 0
        profile_info = set(profile_pool_to_info(stored_profiles))
        while out[i].startswith(" "):
            assert_printed_profiles(profile_info, out[i])
            # We have to consider, that there are the boxes every 5 and after first profile
            i += 2 if count % 5 == 0 else 1
            count += 1
        # Skip horizontal line
        i += 1
        assert count == len(stored_profiles)
    i += 1
    assert_untracked_overview_info(out[i], untracked_profiles)
    if untracked_profiles:
        # Skip header and empty line
        i += 5
        count = 0
        profile_info = set(profile_pool_to_info(untracked_profiles))
        while out[i].startswith(" "):
            assert_printed_profiles(profile_info, out[i])
            # We have to consider, that there are the boxes every 5 and after first profile
            i += 2 if count % 5 == 0 else 1
            count += 1
        assert count == len(untracked_profiles)


@pytest.mark.usefixtures("cleandir")
def test_status_outside_vcs():
    """Test calling 'perun status', without any wrapped repository

    Expecting ending with error, as we are not inside the perun repository
    """
    with pytest.raises(NotPerunRepositoryException):
        commands.status()


def test_status_on_empty_repo(pcs_with_empty_git, capsys):
    """Test calling 'perun status', with wrapped repository without head"""
    with pytest.raises(SystemExit):
        commands.status()

    # Test that nothing is printed on out and something is printed on err
    out, err = capsys.readouterr()
    assert out == ""
    assert err != "" and "error" in err.lower()


def test_status_no_pending(pcs_full, capsys, stored_profile_pool):
    """Test calling 'perun status', without pending profiles

    Expecting no error and long display of the current status of the perun, without any pending.
    """
    commands.status()

    git_repo = git.Repo(pcs_full.get_vcs_path())
    out = capsys.readouterr()[0].split("\n")
    assert_info(out, git_repo, stored_profile_pool[1:], [])


def test_status_short_no_pending(pcs_full, capsys, stored_profile_pool):
    """Test calling 'perun status --short', without any pendding profiles

    Expecting no errors and short display of profiles.
    """
    commands.status(short=True)

    # Assert the repo
    git_repo = git.Repo(pcs_full.get_vcs_path())
    raw_out, _ = capsys.readouterr()
    out = raw_out.split("\n")
    assert_short_info(out, git_repo, stored_profile_pool[1:], [])


def test_status_no_profiles(pcs_full_no_prof, capsys):
    """Test calling 'perun status', without any assigned profiles

    Expecting no error and long display of the current status of the perun, without any pending.
    """
    # First we will do a new commit, with no profiles
    git_repo = git.Repo(pcs_full_no_prof.get_vcs_path())
    file = os.path.join(os.getcwd(), "file3")
    common_kit.touch_file(file)
    git_repo.index.add([file])
    git_repo.index.commit("new commit")

    commands.status()
    out = capsys.readouterr()[0].split("\n")
    assert_info(out, git_repo, [], [])
    capsys.readouterr()

    # Test short command
    commands.status(**{"short": True})
    out = capsys.readouterr()[0].split("\n")
    assert_short_info(out, git_repo, [], [])


def test_status(pcs_full, capsys, stored_profile_pool, valid_profile_pool):
    """Test calling 'perun status' with expected behaviour

    Expecting no errors and long display of the current status of the perun, with all profiles.
    """
    test_utils.populate_repo_with_untracked_profiles(pcs_full.get_path(), valid_profile_pool)
    git_repo = git.Repo(pcs_full.get_vcs_path())

    commands.status()
    raw_out, _ = capsys.readouterr()
    out = raw_out.split("\n")
    assert_info(out, git_repo, stored_profile_pool[1:], valid_profile_pool)
    capsys.readouterr()

    # Test short command
    commands.status(**{"short": True})
    raw_out, _ = capsys.readouterr()
    out = raw_out.split("\n")
    assert_short_info(out, git_repo, stored_profile_pool[1:], valid_profile_pool)


def test_status_sort(monkeypatch, pcs_single_prof, capsys, valid_profile_pool):
    """Test calling 'perun status' with expected behaviour

    TODO: Testing that the profiles are really sorted

    Expecting no errors and long display of the current status of the perun, with all profiles.
    """
    test_utils.populate_repo_with_untracked_profiles(pcs_single_prof.get_path(), valid_profile_pool)
    decorators.remove_from_function_args_cache("lookup_key_recursively")

    # Try what happens if we screw the stored profile keys ;)
    cfg = config.Config(
        "shared",
        "",
        {
            "general": {"paging": "never"},
            "format": {
                "status": "\u2503 %type% \u2503 %collector%  \u2503 (%time%) \u2503 %source% \u2503"
            },
        },
    )
    ldata = config.local(pcs_single_prof.get_path()).data.copy()
    ldata.update(
        {
            "general": {"paging": "never"},
            "format": {
                "status": (
                    "\u2503 %type% \u2503 %collector%  \u2503 (%time%) \u2503 %source% \u2503"
                ),
            },
        }
    )
    lcfg = config.Config("local", pcs_single_prof.get_path(), ldata)
    monkeypatch.setattr("perun.logic.config.local", lambda _: lcfg)
    monkeypatch.setattr("perun.logic.config.shared", lambda: cfg)
    commands.status()

    out, _ = capsys.readouterr()
    assert "missing set option" in out

    cfg = config.Config(
        "shared",
        "",
        {
            "general": {"paging": "never"},
            "format": {
                "status": (
                    "\u2503 %type% \u2503 %collector%  \u2503 (%time%) \u2503 %source% \u2503"
                ),
                "sort_profiles_by": "bogus",
            },
        },
    )
    monkeypatch.setattr("perun.logic.config.shared", lambda: cfg)
    commands.status()

    out, _ = capsys.readouterr()
    assert "invalid sort key" in out
    monkeypatch.undo()
