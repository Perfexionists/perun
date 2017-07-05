"""Basic tests for running the cli interface of the Perun

Note that the functionality of the commands themselves are not tested,
this is done in appropriate test files, only the API is tested."""

import git
import os

import pytest
from click.testing import CliRunner

import perun.cli as cli

__author__ = 'Tomas Fiedor'


def test_status_correct(pcs_full):
    """Test running perun status in perun directory, without any problems.

    Expecting no exceptions, zero status.
    """
    # Try running status without anything
    runner = CliRunner()
    result = runner.invoke(cli.status, [])
    assert result.exit_code == 0
    assert "On major version" in result.output

    short_result = runner.invoke(cli.status, ['--short'])
    assert short_result.exit_code == 0
    assert len(short_result.output.split("\n")) == 4


@pytest.mark.usefixtures('cleandir')
def test_init_correct():
    """Test running init from cli, without any problems

    Expecting no exceptions, no errors, zero status.
    """
    runner = CliRunner()
    result = runner.invoke(cli.init, ['--vcs-type=git'])
    assert result.exit_code == 0


def test_add_correct(helpers, pcs_full, valid_profile_pool):
    """Test running add from cli, without any problems

    Expecting no exceptions, no errors, zero status.
    """
    runner = CliRunner()
    added_profile = helpers.prepare_profile(pcs_full, valid_profile_pool[0], pcs_full.get_head())
    result = runner.invoke(cli.add, ['--keep-profile', '{}'.format(added_profile)])
    assert result.exit_code == 0
    assert os.path.exists(added_profile)


def test_rm_correct(helpers, pcs_full, stored_profile_pool):
    """Test running rm from cli, without any problems

    Expecting no exceptions, no errors, zero status
    """
    runner = CliRunner()
    deleted_profile = os.path.split(stored_profile_pool[1])[-1]
    result = runner.invoke(cli.rm, ['{}'.format(deleted_profile)])
    assert result.exit_code == 0


def test_log_correct(pcs_full):
    """Test running log from cli, without any problems

    Expecting no exceptions, no errors, zero status
    """
    runner = CliRunner()
    result = runner.invoke(cli.log, [])
    assert result.exit_code == 0

    short_result = runner.invoke(cli.log, ['--short'])
    assert short_result.exit_code == 0
    assert len(result.output.split('\n')) > len(short_result.output.split('\n'))


def test_collect_correct(pcs_full):
    """Test running collector from cli, without any problems

    Expecting no exceptions, no errors, zero status
    """
    runner = CliRunner()
    result = runner.invoke(cli.collect, ['-c echo', '-w hello', 'time'])
    assert result.exit_code == 0


def test_show_help(pcs_full):
    """Test running show to see if there are registered modules for showing

    Expecting no error and help outputed, where the currently supported modules will be shown
    """
    runner = CliRunner()
    result = runner.invoke(cli.show, ['--help'])
    assert result.exit_code == 0
    assert 'heapmap' in result.output
    assert 'raw' in result.output


def test_add_tag(helpers, pcs_full, valid_profile_pool):
    """Test running add with tags instead of profile

    Expecting no errors and profile added as it should
    """
    git_repo = git.Repo(os.path.split(pcs_full.path)[0])
    head = str(git_repo.head.commit)
    helpers.populate_repo_with_untracked_profiles(pcs_full.path, valid_profile_pool)
    first_tagged = os.path.relpath(helpers.prepare_profile(pcs_full, valid_profile_pool[0], head))

    runner = CliRunner()
    result = runner.invoke(cli.add, ['0@p'])
    print(result.output)
    assert result.exit_code == 0
    assert "'{}' successfully registered".format(first_tagged) in result.output

    result = runner.invoke(cli.add, ['10@p'])
    assert result.exit_code == 2
    assert '0@p' in result.output


def test_postprocess_tag(helpers, pcs_full, valid_profile_pool):
    """Test running postprocessby with various valid and invalid tags

    Expecting no errors (or caught errors), everything postprocessed as it should be
    """
    helpers.populate_repo_with_untracked_profiles(pcs_full.path, valid_profile_pool)
    pending_dir = os.path.join(pcs_full.path, 'jobs')
    assert len(os.listdir(pending_dir)) == 2

    runner = CliRunner()
    result = runner.invoke(cli.postprocessby, ['0@p', 'normalizer'])
    assert result.exit_code == 0
    assert len(os.listdir(pending_dir)) == 3

    # Try incorrect tag -> expect failure and return code 2 (click error)
    result = runner.invoke(cli.postprocessby, ['666@p', 'normalizer'])
    assert result.exit_code == 2
    assert len(os.listdir(pending_dir)) == 3

    # Try correct index tag
    result = runner.invoke(cli.postprocessby, ['1@i', 'normalizer'])
    assert result.exit_code == 0
    assert len(os.listdir(pending_dir)) == 4

    # Try incorrect index tag -> expect failure and return code 2 (click error)
    result = runner.invoke(cli.postprocessby, ['1337@i', 'normalizer'])
    assert result.exit_code == 2
    assert len(os.listdir(pending_dir)) == 4


def test_show_tag(helpers, pcs_full, valid_profile_pool):
    """Test running show with several valid and invalid tags

    Expecting no errors (or caught errors), everythig shown as it should be
    """
    helpers.populate_repo_with_untracked_profiles(pcs_full.path, valid_profile_pool)

    runner = CliRunner()
    result = runner.invoke(cli.show, ['0@p', 'raw'])
    assert result.exit_code == 0

    # Try incorrect tag -> expect failure and return code 2 (click error)
    result = runner.invoke(cli.show, ['1337@p', 'raw'])
    assert result.exit_code == 2

    # Try correct index tag
    result = runner.invoke(cli.show, ['0@i', 'raw'])
    assert result.exit_code == 0

    # Try incorrect index tag
    result = runner.invoke(cli.show, ['666@i', 'raw'])
    assert result.exit_code == 2
