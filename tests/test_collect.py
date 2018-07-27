"""Basic tests for running the currently supported collectors"""

import os

import perun.vcs as vcs
import perun.logic.runner as runner
import perun.profile.query as query
import perun.collect.trace.systemtap as stap

from perun.utils.helpers import Unit, Job
from perun.workload.integer_generator import IntegerGenerator

__author__ = 'Tomas Fiedor'


_mocked_stap_code = 0
_mocked_stap_file = 'tst_stap_record.txt'


def _mocked_stap(**_):
    """System tap mock, provide OK code and pre-fabricated collection output"""
    code = _mocked_stap_code
    file = os.path.join(os.path.dirname(__file__), 'collect_trace', _mocked_stap_file)
    return code, file


def test_collect_trace(monkeypatch, helpers, pcs_full, trace_collect_job):
    """Test collecting the profile using trace collector"""
    head = vcs.get_minor_version_info(vcs.get_minor_head())
    monkeypatch.setattr(stap, 'systemtap_collect', _mocked_stap)

    before_object_count = helpers.count_contents_on_path(pcs_full.get_path())[0]

    cmd, args, work, collectors, posts, config = trace_collect_job
    runner.run_single_job(cmd, args, work, collectors, posts, [head], **config)

    # Assert that nothing was removed
    after_object_count = helpers.count_contents_on_path(pcs_full.get_path())[0]
    assert before_object_count + 1 == after_object_count
    profiles = os.listdir(os.path.join(pcs_full.get_path(), 'jobs'))

    new_profile = profiles[0]
    assert len(profiles) == 1
    assert new_profile.endswith(".perf")

    # Fixme: Add check that the profile was correctly generated


def test_collect_trace_fail(monkeypatch, helpers, pcs_full, trace_collect_job):
    """Test failed collecting using trace collector"""
    global _mocked_stap_code
    global _mocked_stap_file
    head = vcs.get_minor_version_info(vcs.get_minor_head())

    monkeypatch.setattr(stap, 'systemtap_collect', _mocked_stap)

    before_object_count = helpers.count_contents_on_path(pcs_full.get_path())[0]

    # Test malformed file that ends in unexpected way
    _mocked_stap_file = 'record_malformed.txt'
    cmd, args, work, collectors, posts, config = trace_collect_job
    runner.run_single_job(cmd, args, work, collectors, posts, [head], **config)

    # Assert that nothing was added
    after_object_count = helpers.count_contents_on_path(pcs_full.get_path())[0]
    assert before_object_count == after_object_count

    # Test malformed file that ends in another unexpected way
    _mocked_stap_file = 'record_malformed2.txt'
    runner.run_single_job(cmd, args, work, collectors, posts, [head], **config)

    # Assert that nothing was added
    after_object_count = helpers.count_contents_on_path(pcs_full.get_path())[0]
    assert before_object_count == after_object_count

    # Simulate the failure of the systemTap
    _mocked_stap_code = 1
    runner.run_single_job(cmd, args, work, collectors, posts, [head], **config)

    # Assert that nothing was added
    after_object_count = helpers.count_contents_on_path(pcs_full.get_path())[0]
    assert before_object_count == after_object_count


def test_collect_memory(capsys, helpers, pcs_full, memory_collect_job, memory_collect_no_debug_job):
    """Test collecting the profile using the memory collector"""
    # Fixme: Add check that the profile was correctly generated
    before_object_count = helpers.count_contents_on_path(pcs_full.get_path())[0]
    head = vcs.get_minor_version_info(vcs.get_minor_head())
    memory_collect_job += ([head], )

    runner.run_single_job(*memory_collect_job)

    # Assert that nothing was removed
    after_object_count = helpers.count_contents_on_path(pcs_full.get_path())[0]
    assert before_object_count + 1 == after_object_count

    profiles = os.listdir(os.path.join(pcs_full.get_path(), 'jobs'))
    new_profile = profiles[0]
    assert len(profiles) == 1
    assert new_profile.endswith(".perf")

    cmd, args, _, colls, posts, _ = memory_collect_job
    runner.run_single_job(cmd, args, ["hello"], colls, posts, [head], **{'no_func': 'fun', 'sampling': 0.1})

    profiles = os.listdir(os.path.join(pcs_full.get_path(), 'jobs'))
    new_smaller_profile = [p for p in profiles if p != new_profile][0]
    assert len(profiles) == 2
    assert new_smaller_profile.endswith(".perf")

    # Assert that nothing was removed
    after_second_object_count = helpers.count_contents_on_path(pcs_full.get_path())[0]
    assert after_object_count + 1 == after_second_object_count

    # Fixme: Add check that the profile was correctly generated

    memory_collect_no_debug_job += ([head], )
    runner.run_single_job(*memory_collect_no_debug_job)
    last_object_count = helpers.count_contents_on_path(pcs_full.get_path())[0]
    _, err = capsys.readouterr()
    assert after_second_object_count == last_object_count
    assert 'debug info' in err

    target_bin = memory_collect_job[0][0]
    collector_unit = Unit('memory', {
        'all': False,
        'no_func': 'main'
    })
    job = Job('memory', [], str(target_bin), '', '')
    _, prof = runner.run_collector(collector_unit, job)

    assert len(list(query.all_resources_of(prof))) == 2

    collector_unit = Unit('memory', {
        'all': False,
        'no_source': 'memory_collect_test.c'
    })
    job = Job('memory', [], str(target_bin), '', '')
    _, prof = runner.run_collector(collector_unit, job)

    assert len(list(query.all_resources_of(prof))) == 0


def test_collect_memory_with_generator(pcs_full, memory_collect_job):
    """Tries to collect the memory with integer generators"""
    cmd = memory_collect_job[0][0]
    collector = Unit('memory', {})
    integer_job = Job(collector, [], cmd, '', '')
    integer_generator = IntegerGenerator(integer_job, 1, 3, 1)
    memory_profiles = list(integer_generator.generate(runner.run_collector))
    assert len(memory_profiles) == 1


def test_collect_time(monkeypatch, helpers, pcs_full, capsys):
    """Test collecting the profile using the time collector"""
    # Count the state before running the single job
    before_object_count = helpers.count_contents_on_path(pcs_full.get_path())[0]
    head = vcs.get_minor_version_info(vcs.get_minor_head())

    runner.run_single_job(["echo"], "", ["hello"], ["time"], [], [head])

    # Assert outputs
    out, err = capsys.readouterr()
    assert err == ''
    assert 'Successfully collected data from echo' in out

    # Assert that just one profile was created
    after_object_count = helpers.count_contents_on_path(pcs_full.get_path())[0]
    assert before_object_count + 1 == after_object_count

    profiles = os.listdir(os.path.join(pcs_full.get_path(), 'jobs'))
    new_profile = profiles[0]
    assert len(profiles) == 1
    assert new_profile.endswith(".perf")

    # Test running time with error
    runner.run_single_job(["echo"], "", ["hello"], ["time"], [], [head])

    def collect_raising_exception(**kwargs):
        raise Exception("Something happened lol!")

    monkeypatch.setattr("perun.collect.time.run.collect", collect_raising_exception)
    runner.run_single_job(["echo"], "", ["hello"], ["time"], [], [head])
    _, err = capsys.readouterr()
    assert 'Something happened lol!' in err
