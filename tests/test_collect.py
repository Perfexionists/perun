"""Basic tests for running the currently supported collectors"""

import os
import subprocess
import signal

from click.testing import CliRunner

import perun.vcs as vcs
import perun.cli as cli
import perun.logic.runner as run
import perun.utils as utils
import perun.collect.complexity.makefiles as makefiles
import perun.collect.complexity.symbols as symbols
import perun.collect.complexity.run as complexity
import perun.utils.log as log

from subprocess import SubprocessError

from perun.profile.factory import Profile
from perun.utils.structs import Unit, Executable, CollectStatus, RunnerReport, Job
from perun.workload.integer_generator import IntegerGenerator

import perun.testing.asserts as asserts
import perun.testing.utils as test_utils

__author__ = 'Tomas Fiedor'


def _mocked_external_command(_, **__):
    return 1


def _mocked_flag_support(_):
    return True


def _mocked_libs_existence_fails(_):
    return False


def _mocked_libs_existence_exception(_):
    raise NameError


def _mocked_record_processing(_, __, ___, ____):
    return 1


def _mocked_symbols_extraction(_):
    return ['_Z13SLList_insertP6SLListi', 'main', '_fini', '_init', '_Z13SLList_removeP6SLListi',
            '_ZN9SLListclsD1Ev', '_ZN9SLListclsD2Ev', '_ZN9SLListclsC1Ev', '_ZN9SLListclsC2Ev',
            '_ZN9SLListcls6InsertEi', '__libc_csu_fini', '_Z14SLList_destroyP6SLList', '_start',
            '_ZN9SLListcls10SLLelemclsC1Ei', '_Z13SLList_searchP6SLListi', '__libc_csu_init',
            '_Z11SLList_initP6SLList', '_ZN9SLListcls10SLLelemclsC2Ei', '_ZN9SLListcls6SearchEi',
            'deregister_tm_clones', 'register_tm_clones', '__do_global_dtors_aux', 'frame_dummy',
            '_dl_relocate_static_pie', '_Z14SLList_destroyP6SLList', '_ZN9SLListclsD1Ev', 'main',
            '_ZN9SLListclsD2Ev', '_fini', '_ZN9SLListcls6SearchEi', '_start',
            '_Z11SLList_initP6SLList', '_ZN9SLListcls10SLLelemclsC1Ei', '_init',
            '_ZN9SLListcls6InsertEi', '_ZN9SLListcls10SLLelemclsC2Ei', '_Z13SLList_insertP6SLListi',
            '_ZN9SLListclsC2Ev', '_Z13SLList_searchP6SLListi', '__libc_csu_init', '__libc_csu_fini',
            '_ZN9SLListclsC1Ev', '_Z13SLList_removeP6SLListi',
            '_ZNSt8__detail12_Insert_baseIiSt4pairIKiSt6vectorI5ColorSaIS4_EEESaIS7_ENS_10_'
            'Select1stESt8equal_toIiESt4hashIiENS_18_Mod_range_hashingENS_20_Default_ranged_hash'
            'ENS_20_Prime_rehash_policyENS_17_Hashtable_traitsILb0ELb0ELb1EEEEC1Ev']


def test_collect_complexity(monkeypatch, pcs_full, complexity_collect_job):
    """Test collecting the profile using complexity collector"""
    before_object_count = test_utils.count_contents_on_path(pcs_full.get_path())[0]

    cmd, args, work, collectors, posts, config = complexity_collect_job
    head = vcs.get_minor_version_info(vcs.get_minor_head())
    result = run.run_single_job(cmd, args, work, collectors, posts, [head], **config)
    assert result == CollectStatus.OK

    # Assert that nothing was removed
    after_object_count = test_utils.count_contents_on_path(pcs_full.get_path())[0]
    assert before_object_count + 2 == after_object_count
    profiles = list(filter(test_utils.index_filter, os.listdir(os.path.join(pcs_full.get_path(), 'jobs'))))

    new_profile = profiles[0]
    assert len(profiles) == 1
    assert new_profile.endswith(".perf")

    # Fixme: Add check that the profile was correctly generated

    script_dir = os.path.join(os.path.split(__file__)[0], 'sources', 'collect_complexity', 'target')
    job_params = complexity_collect_job[5]['collector_params']['complexity']

    files = [
        '-f{}'.format(os.path.abspath(os.path.join(script_dir, file)))
        for file in job_params['files']
    ]
    rules = [
        '-r{}'.format(rule) for rule in job_params['rules']
    ]
    samplings = sum([
        ['-s {}'.format(sample['func']), sample['sample']] for sample in job_params['sampling']
    ], [])
    runner = CliRunner()
    result = runner.invoke(cli.collect, ['-c{}'.format(job_params['target_dir']),
                                         '-a test', '-w input', 'complexity',
                                         '-t{}'.format(job_params['target_dir']),
                                         ] + files + rules + samplings)
    asserts.predicate_from_cli(result, result.exit_code == 0)

    # Test running the job from the params using the job file
    # TODO: troubles with paths in job.yml, needs some proper solving
    # script_dir = os.path.split(__file__)[0]
    # source_dir = os.path.join(script_dir, 'collect_complexity')
    # job_config_file = os.path.join(source_dir, 'job.yml')
    # result = runner.invoke(cli.collect, ['-c{}'.format(job_params['target_dir']),
    #                                      '-p{}'.format(job_config_file), 'complexity'])
    # assert result.exit_code == 0

    # test some scoped and templatized prototypes taken from a more difficult project
    monkeypatch.setattr(symbols, 'extract_symbols', _mocked_symbols_extraction)
    more_rules = ['Gif::Ctable::Ctable(Gif::Ctable&&)',
                  'std::tuple<int&&>&& std::forward<std::tuple<int&&> >(std::remove_reference<std::tuple<int&&> >::type&)']
    rules.extend(['-r{}'.format(rule) for rule in more_rules])
    result = runner.invoke(cli.collect, ['-c{}'.format(job_params['target_dir']), 'complexity',
                                         '-t{}'.format(job_params['target_dir']),
                                         ] + files + rules + samplings)
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(result, 'stored profile' in result.output)

    original_run = utils.run_safely_external_command
    def patched_run(cmd, *args, **kwargs):
        if cmd.startswith('g++') or cmd.startswith('readelf') or cmd.startswith('echo'):
            return original_run(cmd, *args, **kwargs)
        else:
            raise subprocess.CalledProcessError(1, 'error')

    monkeypatch.setattr('perun.utils.run_safely_external_command', patched_run)

    runner = CliRunner()
    result = runner.invoke(cli.collect, ['-c{}'.format(job_params['target_dir']),
                                         '-a test', '-w input', 'complexity',
                                         '-t{}'.format(job_params['target_dir']),
                                         ] + files + rules + samplings)
    asserts.predicate_from_cli(result, result.exit_code == 1)


def test_collect_complexity_errors(monkeypatch, pcs_full, complexity_collect_job):
    """Test various scenarios where something goes wrong during the collection process.
    """
    # Get the job.yml parameters
    script_dir = os.path.join(os.path.split(__file__)[0], 'sources', 'collect_complexity', 'target')
    job_params = complexity_collect_job[5]['collector_params']['complexity']

    files = [
        '-f{}'.format(os.path.abspath(os.path.join(script_dir, file)))
        for file in job_params['files']
    ]
    rules = [
        '-r{}'.format(rule) for rule in job_params['rules']
    ]
    samplings = sum([
        ['-s {}'.format(sample['func']), sample['sample']] for sample in job_params['sampling']
    ], [])

    # prepare the runner
    runner = CliRunner()

    # Try missing parameters --target-dir and --files
    result = runner.invoke(cli.collect, ['complexity'])
    asserts.predicate_from_cli(result, result.exit_code == 1)
    asserts.predicate_from_cli(result, '--target-dir parameter must be supplied' in result.output)

    result = runner.invoke(cli.collect, ['complexity', '-t{}'.format(job_params['target_dir'])])
    asserts.predicate_from_cli(result, result.exit_code == 1)
    asserts.predicate_from_cli(result, '--files parameter must be supplied' in result.output)

    # Try supplying invalid directory path, which is a file instead
    invalid_target = os.path.join(os.path.dirname(script_dir), 'job.yml')
    result = runner.invoke(cli.collect, ['complexity', '-t{}'.format(invalid_target)])
    asserts.predicate_from_cli(result, result.exit_code == 1)
    asserts.predicate_from_cli(result, 'already exists' in result.output)

    # Simulate the failure of 'cmake' utility
    old_run = utils.run_external_command
    monkeypatch.setattr(utils, 'run_external_command', _mocked_external_command)
    command = ['-c{}'.format(job_params['target_dir']), 'complexity',
               '-t{}'.format(job_params['target_dir'])] + files + rules + samplings
    result = runner.invoke(cli.collect, command)
    asserts.predicate_from_cli(result, 'CalledProcessError(1, \'cmake\')' in result.output)
    monkeypatch.setattr(utils, 'run_external_command', old_run)

    # Simulate that the flag is supported, which leads to failure in build process for older g++
    old_flag = makefiles._is_flag_support
    monkeypatch.setattr(makefiles, '_is_flag_support', _mocked_flag_support)
    result = runner.invoke(cli.collect, command)
    asserts.predicate_from_cli(result, 'stored profile' in result.output or 'CalledProcessError(2, \'make\')' in result.output)
    monkeypatch.setattr(makefiles, '_is_flag_support', old_flag)

    # Simulate that some required library is missing
    old_libs_existence = makefiles._libraries_exist
    monkeypatch.setattr(makefiles, '_libraries_exist', _mocked_libs_existence_fails)
    result = runner.invoke(cli.collect, command)
    asserts.predicate_from_cli(result, 'libraries are missing' in result.output)

    # Simulate that the libraries directory path cannot be found
    monkeypatch.setattr(makefiles, '_libraries_exist', _mocked_libs_existence_exception)
    result = runner.invoke(cli.collect, command)
    asserts.predicate_from_cli(result, 'Unable to locate' in result.output)
    monkeypatch.setattr(makefiles, '_libraries_exist', old_libs_existence)

    # Simulate the failure of output processing
    old_record_processing = complexity._process_file_record
    monkeypatch.setattr(complexity, '_process_file_record', _mocked_record_processing)
    result = runner.invoke(cli.collect, command)
    asserts.predicate_from_cli(result, 'Call stack error' in result.output)
    monkeypatch.setattr(complexity, '_process_file_record', old_record_processing)


def test_collect_memory(capsys, pcs_full, memory_collect_job, memory_collect_no_debug_job):
    """Test collecting the profile using the memory collector"""
    # Fixme: Add check that the profile was correctly generated
    before_object_count = test_utils.count_contents_on_path(pcs_full.get_path())[0]
    head = vcs.get_minor_version_info(vcs.get_minor_head())
    memory_collect_job += ([head], )

    run.run_single_job(*memory_collect_job)

    # Assert that nothing was removed
    after_object_count = test_utils.count_contents_on_path(pcs_full.get_path())[0]
    assert before_object_count + 2 == after_object_count

    profiles = list(filter(test_utils.index_filter, os.listdir(os.path.join(pcs_full.get_path(), 'jobs'))))
    new_profile = profiles[0]
    assert len(profiles) == 1
    assert new_profile.endswith(".perf")

    cmd, args, _, colls, posts, _ = memory_collect_job
    run.run_single_job(cmd, args, ["hello"], colls, posts, [head], **{'no_func': 'fun', 'sampling': 0.1})

    profiles = list(filter(test_utils.index_filter, os.listdir(os.path.join(pcs_full.get_path(), 'jobs'))))
    new_smaller_profile = [p for p in profiles if p != new_profile][0]
    assert len(profiles) == 2
    assert new_smaller_profile.endswith(".perf")

    # Assert that nothing was removed
    after_second_object_count = test_utils.count_contents_on_path(pcs_full.get_path())[0]
    assert after_object_count + 1 == after_second_object_count

    # Fixme: Add check that the profile was correctly generated

    log.VERBOSITY = log.VERBOSE_DEBUG
    memory_collect_no_debug_job += ([head], )
    run.run_single_job(*memory_collect_no_debug_job)
    last_object_count = test_utils.count_contents_on_path(pcs_full.get_path())[0]
    _, err = capsys.readouterr()
    assert after_second_object_count == last_object_count
    assert 'debug info' in err
    assert 'File "' in err
    log.VERBOSITY = log.VERBOSE_RELEASE

    target_bin = memory_collect_job[0][0]
    collector_unit = Unit('memory', {
        'all': False,
        'no_func': 'main'
    })
    executable = Executable(str(target_bin))
    assert executable.to_escaped_string() != ""
    job = Job('memory', [], executable)
    _, prof = run.run_collector(collector_unit, job)
    prof = Profile(prof)

    assert len(list(prof.all_resources())) == 2

    collector_unit = Unit('memory', {
        'all': False,
        'no_source': 'memory_collect_test.c'
    })
    job = Job('memory', [], executable)
    _, prof = run.run_collector(collector_unit, job)
    prof = Profile(prof)

    assert len(list(prof.all_resources())) == 0


def test_collect_memory_with_generator(pcs_full, memory_collect_job):
    """Tries to collect the memory with integer generators"""
    executable = Executable(memory_collect_job[0][0])
    collector = Unit('memory', {})
    integer_job = Job(collector, [], executable)
    integer_generator = IntegerGenerator(integer_job, 1, 3, 1)
    memory_profiles = list(integer_generator.generate(run.run_collector))
    assert len(memory_profiles) == 1


def test_collect_bounds(monkeypatch, pcs_full):
    """Test collecting the profile using the bounds collector"""
    current_dir = os.path.split(__file__)[0]
    test_dir = os.path.join(current_dir, 'sources', 'collect_bounds')
    sources = [
        os.path.join(test_dir, src) for src in os.listdir(test_dir) if src.endswith('.c')
    ]
    single_sources = [os.path.join(test_dir, "partitioning.c")]
    job = Job(Unit('bounds', {'sources': sources}), [], Executable('echo', '', 'hello'))

    status, prof = run.run_collector(job.collector, job)
    assert status == CollectStatus.OK
    assert len(prof['global']['resources']) == 17

    job = Job(Unit('bounds', {'sources': single_sources}), [], Executable('echo', '', 'hello'))

    status, prof = run.run_collector(job.collector, job)
    assert status == CollectStatus.OK
    assert len(prof['global']['resources']) == 8

    original_function = utils.run_safely_external_command

    def before_returning_error(cmd, **kwargs):
        if cmd.startswith('clang'):
            raise SubprocessError("something happened")
    monkeypatch.setattr("perun.utils.run_safely_external_command", before_returning_error)
    status, prof = run.run_collector(job.collector, job)
    assert status == CollectStatus.ERROR

    def collect_returning_error(cmd, **kwargs):
        if 'loopus' in cmd:
            raise SubprocessError("something happened")
        else:
            original_function(cmd, **kwargs)
    monkeypatch.setattr("perun.utils.run_safely_external_command", collect_returning_error)
    status, prof = run.run_collector(job.collector, job)
    assert status == CollectStatus.ERROR


def test_collect_time(monkeypatch, pcs_full, capsys):
    """Test collecting the profile using the time collector"""
    # Count the state before running the single job
    before_object_count = test_utils.count_contents_on_path(pcs_full.get_path())[0]
    head = vcs.get_minor_version_info(vcs.get_minor_head())

    run.run_single_job(["echo"], "", ["hello"], ["time"], [], [head])

    # Assert outputs
    out, err = capsys.readouterr()
    assert err == ''
    assert 'Successfully collected data from echo' in out

    # Assert that just one profile was created
    # + 1 for index
    after_object_count = test_utils.count_contents_on_path(pcs_full.get_path())[0]
    assert before_object_count + 2 == after_object_count

    profiles = list(filter(test_utils.index_filter, os.listdir(os.path.join(pcs_full.get_path(), 'jobs'))))
    new_profile = profiles[0]
    assert len(profiles) == 1
    assert new_profile.endswith(".perf")

    # Test running time with error
    run.run_single_job(["echo"], "", ["hello"], ["time"], [], [head])

    def collect_raising_exception(**kwargs):
        raise Exception("Something happened lol!")

    monkeypatch.setattr("perun.collect.time.run.collect", collect_raising_exception)
    run.run_single_job(["echo"], "", ["hello"], ["time"], [], [head])
    _, err = capsys.readouterr()
    assert 'Something happened lol!' in err


def test_integrity_tests(capsys):
    """Basic tests for checking integrity of runners"""
    mock_report = RunnerReport(complexity, 'postprocessor', {'profile': {}})
    run.check_integrity_of_runner(complexity, 'postprocessor', mock_report)
    out, err = capsys.readouterr()
    assert "warning: complexity is missing postprocess() function" in out
    assert "" == err

    mock_report = RunnerReport(complexity, 'collector', {})
    run.check_integrity_of_runner(complexity, 'collector', mock_report)
    out, err = capsys.readouterr()
    assert "warning: collector complexity does not return any profile"
    assert "" == err


def test_teardown(pcs_full, monkeypatch, capsys):
    """Basic tests for integrity of the teardown phase"""
    head = vcs.get_minor_version_info(vcs.get_minor_head())
    original_phase_f = run.run_phase_function

    # Assert that collection went OK and teardown returns error
    status = run.run_single_job(["echo"], "", ["hello"], ["time"], [], [head])
    assert status == CollectStatus.OK

    def teardown_returning_error(report, phase):
        if phase == 'teardown':
            result = (CollectStatus.ERROR, "error in teardown", {})
            report.update_from(*result)
        else:
            original_phase_f(report, phase)
    monkeypatch.setattr("perun.logic.runner.run_phase_function", teardown_returning_error)
    status = run.run_single_job(["echo"], "", ["hello"], ["time"], [], [head])
    assert status == CollectStatus.ERROR
    _, err = capsys.readouterr()
    assert "error in teardown" in err

    # Assert that collection went Wrong, teardown went OK, and still returns the error
    def teardown_not_screwing_things(report, phase):
        if phase == 'teardown':
            print("Teardown was executed")
            assert report.status == CollectStatus.ERROR
            result = (CollectStatus.OK, "", {})
            report.update_from(*result)
        elif phase == 'before':
            result = (CollectStatus.ERROR, "error while before", {})
            report.update_from(*result)
    monkeypatch.setattr("perun.logic.runner.run_phase_function", teardown_not_screwing_things)
    status = run.run_single_job(["echo"], "", ["hello"], ["time"], [], [head])
    assert status == CollectStatus.ERROR
    out, err = capsys.readouterr()
    assert "Teardown was executed" in out
    assert "error while before" in err

    # Test signals
    def collect_firing_sigint(report, phase):
        if phase == 'collect':
            os.kill(os.getpid(), signal.SIGINT)
        else:
            original_phase_f(report, phase)
    monkeypatch.setattr("perun.logic.runner.run_phase_function", collect_firing_sigint)
    status = run.run_single_job(["echo"], "", ["hello"], ["time"], [], [head])
    assert status == CollectStatus.ERROR
    out, err = capsys.readouterr()
    assert "fatal: while collecting by time: Received signal: 2" in err
