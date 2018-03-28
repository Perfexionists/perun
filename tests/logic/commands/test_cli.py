"""Basic tests for running the cli interface of the Perun

Note that the functionality of the commands themselves are not tested,
this is done in appropriate test files, only the API is tested."""

import os
import git
import re
import shutil

import pytest
from click.testing import CliRunner

import perun.cli as cli
import perun.utils.log as log
import perun.utils.decorators as decorators
import perun.logic.config as config
import perun.collect.complexity.run as complexity
import perun.utils.exceptions as exceptions

__author__ = 'Tomas Fiedor'


def _mocked_stap(**kwargs):
    """System tap mock, provide OK code and pre-fabricated collection output"""
    return 0, os.path.join(os.path.dirname(__file__), 'collect_complexity', 'tst_stap_record.txt')


def test_cli(pcs_full):
    """Generic tests for cli, such as testing verbosity setting etc."""
    runner = CliRunner()

    log.VERBOSITY = log.VERBOSE_RELEASE
    runner.invoke(cli.cli, ['-v', '-v', 'log'])
    assert log.VERBOSITY == log.VERBOSE_DEBUG

    # Restore the verbosity
    log.VERBOSITY = log.VERBOSE_RELEASE
    log.SUPPRESS_PAGING = True


def test_reg_analysis_incorrect(pcs_full):
    """Test various failure scenarios for regression analysis cli.

    Expecting no exceptions, all tests should end with status code 2.
    """

    # Instantiate the runner fist
    runner = CliRunner()

    # Test the lack of arguments
    result = runner.invoke(cli.postprocessby, ['1@i', 'regression_analysis'])
    assert result.exit_code == 2
    assert 'Usage' in result.output

    # Test non-existing argument
    result = runner.invoke(cli.postprocessby, ['1@i', 'regression_analysis', '-f'])
    assert result.exit_code == 2
    assert 'no such option: -f' in result.output

    # Test malformed method argument
    result = runner.invoke(cli.postprocessby, ['1@i', 'regression_analysis', '--metod', 'full'])
    assert result.exit_code == 2
    assert 'no such option: --metod' in result.output

    # Test missing method value
    result = runner.invoke(cli.postprocessby, ['1@i', 'regression_analysis', '-m'])
    assert result.exit_code == 2
    assert '-m option requires an argument' in result.output

    # Test invalid method name
    result = runner.invoke(cli.postprocessby, ['1@i', 'regression_analysis', '--method', 'extra'])
    assert result.exit_code == 2
    assert 'Invalid value for "--method"' in result.output

    # Test malformed model argument
    result = runner.invoke(cli.postprocessby, ['1@i', 'regression_analysis', '--method', 'full',
                                               '--regresion_models'])
    assert result.exit_code == 2
    assert 'no such option: --regresion_models' in result.output

    # Test missing model value
    result = runner.invoke(cli.postprocessby, ['1@i', 'regression_analysis', '--method', 'full',
                                               '-r'])
    assert result.exit_code == 2
    assert '-r option requires an argument' in result.output

    # Test invalid model name
    result = runner.invoke(cli.postprocessby, ['1@i', 'regression_analysis', '-m', 'full', '-r',
                                               'ultimastic'])
    assert result.exit_code == 2
    assert 'Invalid value for "--regression_models"' in result.output

    # Test multiple models specification with one invalid value
    result = runner.invoke(cli.postprocessby, ['1@i', 'regression_analysis', '-m', 'full',
                                               '-r', 'linear', '-r', 'fail'])
    assert result.exit_code == 2
    assert 'Invalid value for "--regression_models"' in result.output

    # Test malformed steps argument
    result = runner.invoke(cli.postprocessby, ['1@i', 'regression_analysis', '-m', 'full',
                                               '-r', 'all', '--seps'])
    assert result.exit_code == 2
    assert ' no such option: --seps' in result.output

    # Test missing steps value
    result = runner.invoke(cli.postprocessby, ['1@i', 'regression_analysis', '-m', 'full',
                                               '-r', 'all', '-s'])
    assert result.exit_code == 2
    assert '-s option requires an argument' in result.output

    # Test invalid steps type
    result = runner.invoke(cli.postprocessby, ['1@i', 'regression_analysis', '-m', 'full', '-r',
                                               'all', '-s', '0.5'])
    assert result.exit_code == 2
    assert '0.5 is not a valid integer' in result.output

    # Test multiple method specification resulting in extra argument
    result = runner.invoke(cli.postprocessby, ['1@i', 'regression_analysis', '-dp', 'snapshots',
                                               '-m', 'full', 'iterative'])
    assert result.exit_code == 2
    assert 'Got unexpected extra argument (iterative)' in result.output


def test_reg_analysis_correct(pcs_full):
    """Test correct usages of the regression analysis cli.

    Expecting no exceptions and errors, all tests should end with status code 0.
    """

    # Instantiate the runner fist
    runner = CliRunner()

    result = runner.invoke(cli.status, [])
    match = re.search(r"([0-9]+@i).*mixed", result.output)
    assert match
    cprof_idx = match.groups(1)[0]

    # Test the help printout first
    result = runner.invoke(cli.postprocessby, [cprof_idx, 'regression_analysis', '--help'])
    assert result.exit_code == 0
    assert 'Usage' in result.output

    # Test multiple method specifications -> the last one is chosen
    result = runner.invoke(cli.postprocessby, [cprof_idx, 'regression_analysis', '-m', 'full',
                                               '-m', 'iterative'])
    assert result.exit_code == 0
    assert 'Successfully postprocessed' in result.output

    # Test the full computation method with all models set as a default value
    result = runner.invoke(cli.postprocessby, [cprof_idx, 'regression_analysis', '-m', 'full'])
    assert result.exit_code == 0
    assert 'Successfully postprocessed' in result.output

    # Test the iterative method with all models
    result = runner.invoke(cli.postprocessby, [cprof_idx, 'regression_analysis', '-m', 'iterative'])
    assert result.exit_code == 0
    assert 'Successfully postprocessed' in result.output

    # Test the interval method with all models
    result = runner.invoke(cli.postprocessby, [cprof_idx, 'regression_analysis', '-m', 'interval'])
    assert result.exit_code == 0
    assert 'Successfully postprocessed' in result.output

    # Test the initial guess method with all models
    result = runner.invoke(cli.postprocessby, [cprof_idx, 'regression_analysis',
                                               '-m', 'initial_guess'])
    assert result.exit_code == 0
    assert 'Successfully postprocessed' in result.output

    # Test the bisection method with all models
    result = runner.invoke(cli.postprocessby, [cprof_idx, 'regression_analysis', '-m', 'bisection'])
    assert result.exit_code == 0
    assert 'Successfully postprocessed' in result.output

    # Test explicit models specification on full computation
    result = runner.invoke(cli.postprocessby, [cprof_idx, 'regression_analysis', '-m', 'full',
                                               '-r', 'all'])
    assert result.exit_code == 0
    assert 'Successfully postprocessed' in result.output

    # Test explicit models specification for multiple models
    result = runner.invoke(cli.postprocessby, [cprof_idx, 'regression_analysis', '-m', 'full',
                                               '-r', 'linear', '-r', 'log', '-r', 'exp'])
    assert result.exit_code == 0
    assert 'Successfully postprocessed' in result.output

    # Test explicit models specification for all models
    result = runner.invoke(cli.postprocessby, [cprof_idx, 'regression_analysis', '-m', 'full',
                                               '-r', 'linear', '-r', 'log', '-r', 'power',
                                               '-r', 'exp'])
    assert result.exit_code == 0
    assert 'Successfully postprocessed' in result.output

    # Test explicit models specification for all models values (also with 'all' value)
    result = runner.invoke(cli.postprocessby, [cprof_idx, 'regression_analysis', '-m', 'full',
                                               '-r', 'linear', '-r', 'log', '-r', 'power', '-r',
                                               'exp', '-r', 'all'])
    assert result.exit_code == 0
    assert 'Successfully postprocessed' in result.output

    # Test steps specification for full computation which has no effect
    result = runner.invoke(cli.postprocessby, [cprof_idx, 'regression_analysis', '-m', 'full',
                                               '-r', 'all', '-s', '100'])
    assert result.exit_code == 0
    assert 'Successfully postprocessed' in result.output

    # Test reasonable steps value for iterative method
    result = runner.invoke(cli.postprocessby, [cprof_idx, 'regression_analysis', '-m', 'iterative',
                                               '-r', 'all', '-s', '4'])
    assert result.exit_code == 0
    assert result.output.count('Too few points') == 5
    assert 'Successfully postprocessed' in result.output

    # Test too many steps output
    result = runner.invoke(cli.postprocessby, [cprof_idx, 'regression_analysis', '-m', 'iterative',
                                               '-r', 'all', '-s', '1000'])
    assert result.exit_code == 0
    assert result.output.count('Too few points') == 7
    assert 'Successfully postprocessed' in result.output

    # Test steps value clamping with iterative method
    result = runner.invoke(cli.postprocessby, [cprof_idx, 'regression_analysis', '-m', 'iterative',
                                               '-r', 'all', '-s', '-1'])
    assert result.exit_code == 0
    assert 'Successfully postprocessed' in result.output

    # Test different arguments positions
    result = runner.invoke(cli.postprocessby, [cprof_idx, 'regression_analysis', '-s', '2',
                                               '-r', 'all', '-m', 'full'])
    assert result.exit_code == 0
    assert 'Successfully postprocessed' in result.output


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
    dst = str(os.getcwd())
    result = runner.invoke(cli.init, [dst, '--vcs-type=git'])
    assert result.exit_code == 0


@pytest.mark.usefixtures('cleandir')
def test_init_correct_with_edit(monkeypatch):
    """Test running init from cli, without any problems

    Expecting no exceptions, no errors, zero status.
    """
    runner = CliRunner()
    dst = str(os.getcwd())

    def donothing(*_):
        pass

    monkeypatch.setattr('perun.utils.run_external_command', donothing)
    result = runner.invoke(cli.init, [dst, '--vcs-type=git', '--configure'])
    assert result.exit_code == 0


@pytest.mark.usefixtures('cleandir')
def test_init_correct_with_incorrect_edit(monkeypatch):
    """Test running init from cli, without any problems

    Expecting no exceptions, no errors, zero status.
    """
    runner = CliRunner()
    dst = str(os.getcwd())

    def raiseexc(*_):
        raise exceptions.ExternalEditorErrorException("", "")
    monkeypatch.setattr('perun.utils.run_external_command', raiseexc)
    result = runner.invoke(cli.init, [dst, '--vcs-type=git', '--configure'])
    assert result.exit_code == 1
    monkeypatch.undo()

    for stuff in os.listdir(dst):
        shutil.rmtree(stuff)

    def raiseexc(*_):
        raise PermissionError('')
    monkeypatch.setattr('perun.logic.config.write_config_to', raiseexc)
    result = runner.invoke(cli.init, [dst, '--vcs-type=git'])
    assert result.exit_code == 1
    monkeypatch.undo()

    for stuff in os.listdir(dst):
        shutil.rmtree(stuff)

    def raiseexc(*_):
        raise exceptions.UnsupportedModuleFunctionException('git', 'shit')
    monkeypatch.setattr('perun.vcs.git._init', raiseexc)
    result = runner.invoke(cli.init, [dst, '--vcs-type=git'])
    assert result.exit_code == 1


@pytest.mark.usefixtures('cleandir')
def test_init_correct_with_params():
    """Test running init from cli with parameters for git, without any problems

    Expecting no exceptions, no errors, zero status.
    """
    runner = CliRunner()
    dst = str(os.getcwd())
    result = runner.invoke(cli.init, [dst, '--vcs-type=git', '--vcs-flag', 'bare'])
    assert result.exit_code == 0
    assert 'config' in os.listdir(os.getcwd())
    with open(os.path.join(os.getcwd(), 'config'), 'r') as config_file:
        assert "bare = true" in "".join(config_file.readlines())


@pytest.mark.usefixtures('cleandir')
def test_init_correct_with_params_and_flags(helpers):
    """Test running init from cli with parameters and flags for git, without any problems

    Expecting no exceptions, no errors, zero status.
    """
    runner = CliRunner()
    dst = str(os.getcwd())
    result = runner.invoke(cli.init, [dst, '--vcs-type=git', '--vcs-flag', 'quiet',
                                      '--vcs-param', 'separate-git-dir', 'sepdir'])
    assert result.exit_code == 0
    assert 'sepdir' in os.listdir(os.getcwd())
    initialized_dir = os.path.join(os.getcwd(), 'sepdir')
    dir_content = os.listdir(initialized_dir)

    # Should be enough for sanity check
    assert 'HEAD' in dir_content
    assert 'refs' in dir_content
    assert 'branches' in dir_content


def test_add_correct(helpers, pcs_full, valid_profile_pool):
    """Test running add from cli, without any problems

    Expecting no exceptions, no errors, zero status.
    """
    runner = CliRunner()
    added_profile = helpers.prepare_profile(pcs_full, valid_profile_pool[0], pcs_full.get_head())
    result = runner.invoke(cli.add, ['--keep-profile', '{}'.format(added_profile)])
    assert result.exit_code == 0
    assert os.path.exists(added_profile)


@pytest.mark.usefixtures('cleandir')
def test_cli_outside_pcs(helpers, valid_profile_pool):
    """Test running add from cli, with problems"""
    # Calling add outside of the perun repo
    runner = CliRunner()
    dst_dir = os.getcwd()
    added_profile = helpers.prepare_profile(dst_dir, valid_profile_pool[0], "")
    result = runner.invoke(cli.add, ['--keep-profile', '{}'.format(added_profile)])
    assert result.exit_code == 1

    result = runner.invoke(cli.rm, ['{}'.format(added_profile)])
    assert result.exit_code == 1

    result = runner.invoke(cli.log, [])
    assert result.exit_code == 1

    result = runner.invoke(cli.status, [])
    assert result.exit_code == 1


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


def test_collect_complexity(monkeypatch, pcs_full, complexity_collect_job):
    """Test running the complexity collector from the CLI with parameter handling

    Expecting no errors
    """
    monkeypatch.setattr(complexity, '_call_stap', _mocked_stap)

    script_dir = os.path.join(os.path.split(__file__)[0], 'collect_complexity')
    target = os.path.join(script_dir, 'tst')
    job_params = complexity_collect_job[5]['collector_params']['complexity']

    rules = [
        '-r{}'.format(rule) for rule in job_params['rules']
    ]
    samplings = sum([
        ['-s {}'.format(sample['func']), sample['sample']] for sample in job_params['sampling']
    ], [])
    runner = CliRunner()
    result = runner.invoke(cli.collect, ['-c{}'.format(target),
                                         'complexity',
                                         ] + rules + samplings)

    assert result.exit_code == 0

    # Test running the job from the params using the job file
    script_dir = os.path.split(__file__)[0]
    source_dir = os.path.join(script_dir, 'collect_complexity')
    job_config_file = os.path.join(source_dir, 'job.yml')
    result = runner.invoke(cli.collect, ['-c{} -p{}'.format(target, job_config_file), 'complexity'])
    assert result.exit_code == 0

    # Test running the job from the params using the yaml string
    result = runner.invoke(cli.collect, ['-c{}'.format(target),
                                         '-p\"global_sampling: 2\"',
                                         'complexity'] + rules + samplings)
    assert result.exit_code == 0

    # Try different template
    result = runner.invoke(cli.collect, [
        '-ot', '%collector%-profile',
        '-c{}'.format(target),
        '-p\"method: custom\"',
        'complexity'
    ] + rules + samplings)
    del config.runtime().data['format']
    decorators.func_args_cache['lookup_key_recursively'].pop(
        tuple(["format.output_profile_template"]), None)
    assert result.exit_code == 0
    assert "info: stored profile at: .perun/jobs/complexity-profile.perf" in result.output

    # Test negative global sampling
    result = runner.invoke(cli.collect, ['-c{}'.format(target), 'complexity', '-g -2'])
    assert result.exit_code == 0

    # Try missing parameter -c
    # Fixme: before fails but still produces 0?
    result = runner.invoke(cli.collect, ['complexity'])
    assert result.exit_code == 0

    # Try using not implemented method 'all'
    result = runner.invoke(cli.collect, ['-c{}'.format(target), 'complexity', '-mall'])
    assert result.exit_code == 0

    # Try invalid parameter --method
    result = runner.invoke(cli.collect, ['-c{}'.format(target), 'complexity', '-minvalid'])
    assert result.exit_code == 2


def test_show_help(pcs_full):
    """Test running show to see if there are registered modules for showing

    Expecting no error and help outputed, where the currently supported modules will be shown
    """
    runner = CliRunner()
    result = runner.invoke(cli.show, ['--help'])
    assert result.exit_code == 0
    assert 'heapmap' in result.output
    assert 'raw' in result.output


def test_add_massaged_head(helpers, pcs_full, valid_profile_pool):
    """Test running add with tags instead of profile

    Expecting no errors and profile added as it should, or errors for incorrect revs
    """
    git_repo = git.Repo(os.path.split(pcs_full.path)[0])
    head = str(git_repo.head.commit)
    helpers.populate_repo_with_untracked_profiles(pcs_full.path, valid_profile_pool)
    first_tagged = os.path.relpath(helpers.prepare_profile(pcs_full, valid_profile_pool[0], head))

    runner = CliRunner()
    result = runner.invoke(cli.add, ['0@p', '--minor=HEAD'])
    assert result.exit_code == 0
    assert "'{}' successfully registered".format(first_tagged) in result.output

    runner = CliRunner()
    result = runner.invoke(cli.add, ['0@p', r"--minor=HEAD^{d"])
    assert result.exit_code == 2
    assert "Missing closing brace"

    runner = CliRunner()
    result = runner.invoke(cli.add, ['0@p', r"--minor=HEAD^}"])
    assert result.exit_code == 2

    runner = CliRunner()
    result = runner.invoke(cli.add, ['0@p', '--minor=tag2'])
    assert result.exit_code == 2
    assert "Ref 'tag2' did not resolve to object"


def test_add_tag(helpers, pcs_full, valid_profile_pool):
    """Test running add with tags instead of profile

    Expecting no errors and profile added as it should
    """
    git_repo = git.Repo(os.path.split(pcs_full.path)[0])
    head = str(git_repo.head.commit)
    parent = str(git_repo.head.commit.parents[0])
    helpers.populate_repo_with_untracked_profiles(pcs_full.path, valid_profile_pool)
    first_sha = os.path.relpath(helpers.prepare_profile(pcs_full, valid_profile_pool[0], head))
    os.path.relpath(helpers.prepare_profile(pcs_full, valid_profile_pool[1], parent))

    runner = CliRunner()
    result = runner.invoke(cli.add, ['0@p'])
    assert result.exit_code == 0
    assert "'{}' successfully registered".format(first_sha) in result.output

    runner = CliRunner()
    result = runner.invoke(cli.add, ['0@p'])
    assert result.exit_code == 1
    assert "originates from minor version '{}'".format(parent) in result.output

    result = runner.invoke(cli.add, ['10@p'])
    assert result.exit_code == 2
    assert '0@p' in result.output


def test_remove_tag(helpers, pcs_full):
    """Test running remove with tags instead of profile

    Expecting no errors and profile removed as it should
    """
    runner = CliRunner()
    result = runner.invoke(cli.rm, ['0@i'])
    assert result.exit_code == 0
    assert "removed" in result.output


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

    # Try absolute postprocessing
    first_in_jobs = os.listdir(pending_dir)[0]
    absolute_first_in_jobs = os.path.join(pending_dir, first_in_jobs)
    result = runner.invoke(cli.postprocessby, [absolute_first_in_jobs, 'normalizer'])
    assert result.exit_code == 0

    # Try lookup postprocessing
    result = runner.invoke(cli.postprocessby, [first_in_jobs, 'normalizer'])
    assert result.exit_code == 0


def test_show_tag(helpers, pcs_full, valid_profile_pool, monkeypatch):
    """Test running show with several valid and invalid tags

    Expecting no errors (or caught errors), everythig shown as it should be
    """
    helpers.populate_repo_with_untracked_profiles(pcs_full.path, valid_profile_pool)
    pending_dir = os.path.join(pcs_full.path, 'jobs')

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

    # Try absolute showing
    first_in_jobs = os.listdir(pending_dir)[0]
    absolute_first_in_jobs = os.path.join(pending_dir, first_in_jobs)
    result = runner.invoke(cli.show, [absolute_first_in_jobs, 'raw'])
    assert result.exit_code == 0

    # Try lookup showing
    result = runner.invoke(cli.show, [first_in_jobs, 'raw'])
    assert result.exit_code == 0

    # Try iterating through files
    monkeypatch.setattr('click.confirm', lambda *_: True)
    result = runner.invoke(cli.show, ['prof', 'raw'])
    assert result.exit_code == 0

    # Try iterating through files, but none is confirmed to be true
    monkeypatch.setattr('click.confirm', lambda *_: False)
    result = runner.invoke(cli.show, ['prof', 'raw'])
    assert result.exit_code == 1

    # Try getting something from index
    result = runner.invoke(cli.show, ['prof-2-2017-03-20-21-40-42.perf', 'raw'])
    assert result.exit_code == 0


def test_config(pcs_full, monkeypatch):
    """Test running config

    Expecting no errors, everything shown as it should be
    """
    runner = CliRunner()

    # OK usage
    result = runner.invoke(cli.config, ['--local', 'get', 'vcs.type'])
    assert result.exit_code == 0

    result = runner.invoke(cli.config, ['--local', 'set', 'vcs.remote', 'url'])
    assert result.exit_code == 0

    # Error cli usage
    result = runner.invoke(cli.config, ['--local', 'get'])
    assert result.exit_code == 2

    result = runner.invoke(cli.config, ['--local', 'get', 'bogus.key'])
    assert result.exit_code == 1

    result = runner.invoke(cli.config, ['--local', 'set', 'key'])
    assert result.exit_code == 2

    result = runner.invoke(cli.config, ['--local', 'get', 'wrong,key'])
    assert result.exit_code == 2
    assert "invalid format" in result.output

    # Try to run the monkey-patched editor
    def donothing(*_):
        pass
    monkeypatch.setattr('perun.utils.run_external_command', donothing)
    result = runner.invoke(cli.config, ['--local', 'edit'])
    assert result.exit_code == 0

    def raiseexc(*_):
        raise exceptions.ExternalEditorErrorException
    monkeypatch.setattr('perun.utils.run_external_command', raiseexc)
    result = runner.invoke(cli.config, ['--local', 'edit'])
    assert result.exit_code == 1


def test_check_profiles(helpers, pcs_with_degradations):
    """Tests checking degradation between two profiles"""
    pool_path = os.path.join(os.path.split(__file__)[0], 'degradation_profiles')
    profiles = [
        os.path.join(pool_path, 'linear_base.perf'),
        os.path.join(pool_path, 'linear_base_degradated.perf'),
        os.path.join(pool_path, 'quad_base.perf')
    ]
    helpers.populate_repo_with_untracked_profiles(pcs_with_degradations.path, profiles)

    runner = CliRunner()
    for tag in ("0@p", "1@p", "2@p"):
        result = runner.invoke(cli.check_profiles, ["0@i", tag])
        assert result.exit_code == 0


def test_check_head(pcs_with_degradations):
    """Test checking degradation for one point of history

    Expecting correct behaviours
    """
    runner = CliRunner()

    result = runner.invoke(cli.check_head, [])
    assert result.exit_code == 0

    result = runner.invoke(cli.check_group, ['-c', 'head'])
    assert result.exit_code == 1
    assert "is unsupported" in result.output


def test_check_all(pcs_with_degradations):
    """Test checking degradation for whole history

    Expecting correct behaviours
    """
    runner = CliRunner()
    result = runner.invoke(cli.check_group, [])
    assert result.exit_code == 0

    result = runner.invoke(cli.check_all, [])
    assert result.exit_code == 0


@pytest.mark.usefixtures('cleandir')
def test_utils_create(monkeypatch, tmpdir):
    """Tests creating stuff in the perun"""
    # Prepare different directory
    monkeypatch.setattr('perun.utils.script_helpers.__file__', os.path.join(str(tmpdir), "utils", "script_helpers.py"))
    monkeypatch.chdir(str(tmpdir))

    runner = CliRunner()
    result = runner.invoke(cli.create, ['postprocess', 'mypostprocessor', '--no-edit'])
    assert result.exit_code == 1
    assert "cannot use" in result.output and "as target developer directory" in result.output

    # Now correctly initialize the directory structure
    tmpdir.mkdir('collect')
    tmpdir.mkdir('postprocess')
    tmpdir.mkdir('view')
    tmpdir.mkdir('check')

    # Try to successfully create the new postprocessor
    result = runner.invoke(cli.create, ['postprocess', 'mypostprocessor', '--no-edit'])
    assert result.exit_code == 0
    target_dir = os.path.join(str(tmpdir), 'postprocess', 'mypostprocessor')
    created_files = os.listdir(target_dir)
    assert '__init__.py' in created_files
    assert 'run.py' in created_files

    # Try to successfully create the new collector
    result = runner.invoke(cli.create, ['collect', 'mycollector', '--no-edit'])
    assert result.exit_code == 0
    target_dir = os.path.join(str(tmpdir), 'collect', 'mycollector')
    created_files = os.listdir(target_dir)
    assert '__init__.py' in created_files
    assert 'run.py' in created_files

    # Try to successfully create the new collector
    result = runner.invoke(cli.create, ['view', 'myview', '--no-edit'])
    assert result.exit_code == 0
    target_dir = os.path.join(str(tmpdir), 'view', 'myview')
    created_files = os.listdir(target_dir)
    assert '__init__.py' in created_files
    assert 'run.py' in created_files

    # Try to successfully create the new collector
    result = runner.invoke(cli.create, ['check', 'mycheck', '--no-edit'])
    assert result.exit_code == 0
    target_dir = os.path.join(str(tmpdir), 'check')
    created_files = os.listdir(target_dir)
    assert 'mycheck.py' in created_files

    # Try to run the monkey-patched editor
    def donothing(*_):
        pass
    monkeypatch.setattr('perun.utils.run_external_command', donothing)
    result = runner.invoke(cli.create, ['check', 'mydifferentcheck'])
    assert result.exit_code == 0

    def raiseexc(*_):
        raise exceptions.ExternalEditorErrorException
    monkeypatch.setattr('perun.utils.run_external_command', raiseexc)
    result = runner.invoke(cli.create, ['check', 'mythirdcheck'])
    assert result.exit_code == 1


def test_run(pcs_full, monkeypatch):
    matrix = config.Config('local', '', {
        'vcs': {'type': 'git', 'url': '../'},
        'cmds': ['perun'],
        'args': ['-v', '-v -v'],
        'workloads': ['--help'],
        'collectors': [
            {'name': 'time', 'params': {}}
        ],
        'postprocessors': []
    })
    monkeypatch.setattr("perun.logic.config.local", lambda _: matrix)
    runner = CliRunner()
    result = runner.invoke(cli.matrix, [])
    assert result.exit_code == 0

    job_dir = pcs_full.get_job_directory()
    job_profiles = os.listdir(job_dir)
    assert len(job_profiles) == 2

    script_dir = os.path.split(__file__)[0]
    source_dir = os.path.join(script_dir, 'collect_complexity')
    job_config_file = os.path.join(source_dir, 'job.yml')
    result = runner.invoke(cli.job, [
        '--cmd', 'perun',
        '--args', '-vvv',
        '--workload', '--help',
        '--collector', 'time',
        '--collector-params', 'time', 'param: key',
        '--collector-params', 'time', '{}'.format(job_config_file)
    ])
    assert result.exit_code == 0
    job_profiles = os.listdir(job_dir)
    assert len(job_profiles) == 3
