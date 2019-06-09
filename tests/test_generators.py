"""Basic tests of generators"""

import pytest

import perun.logic.config as config
import perun.workload as workload
import perun.logic.runner as runner

from perun.utils.helpers import Job, CollectStatus
from perun.utils.structs import Unit, Executable
from perun.workload.integer_generator import IntegerGenerator
from perun.workload.singleton_generator import SingletonGenerator
from perun.workload.string_generator import StringGenerator
from perun.workload.textfile_generator import TextfileGenerator
from perun.workload.generator import Generator


__author__ = 'Tomas Fiedor'


def test_integer_generator():
    """Tests generation of integers from given range"""
    collector = Unit('time', {})
    executable = Executable('factor')
    integer_job = Job(collector, [], executable)
    integer_generator = IntegerGenerator(integer_job, 10, 100, 10)

    for c_status, profile in integer_generator.generate(runner.run_collector):
        assert c_status == CollectStatus.OK
        assert profile
        assert len(profile['resources']) > 0

    # Try that the pure generator raises error
    pure_generator = Generator(integer_job)
    with pytest.raises(SystemExit):
        _ = list(pure_generator.generate(runner.run_collector))


def test_integer_generator_for_each():
    """Tests the profile_for_each_workload option"""
    # When profile_for_each_workload is not set, we yield profiles for each workload
    collector = Unit('time', {})
    executable = Executable('factor')
    integer_job = Job(collector, [], executable)
    integer_generator = IntegerGenerator(integer_job, 10, 100, 10, profile_for_each_workload=True)

    collection_pairs = list(
        integer_generator.generate(runner.run_collector)
    )
    assert len(collection_pairs) == 10

    # When profile_for_each_workload is set, then we merge the resources
    integer_generator = IntegerGenerator(integer_job, 10, 100, 10, profile_for_each_workload=False)
    collection_pairs = list(
        integer_generator.generate(runner.run_collector)
    )
    assert len(collection_pairs) == 1


def test_loading_generators_from_config(monkeypatch, pcs_full):
    """Tests loading generator specification from config"""
    # Initialize the testing configurations
    collector = Unit('time', {})
    executable = Executable('factor')
    integer_job = Job(collector, [], executable)
    temp_local = config.Config('local', '', {
        'generators': {
            'workload': [
                {
                    'id': 'gen1',
                    'type': 'integer',
                    'min_range': 10,
                    'max_range': 20,
                    'step': 1
                }
            ]
        }
    })
    temp_global = config.Config('global', '', {
        'generators': {
            'workload': [
                {
                    'id': 'gen2',
                    'type': 'integer',
                    'min_range': 100,
                    'max_range': 200,
                    'step': 10
                },
                {
                    'id': 'gen_incorrect',
                    'min_range': 100
                },
                {
                    'id': 'gen_almost_correct',
                    'type': 'bogus'
                }
            ]
        }
    })
    monkeypatch.setattr("perun.logic.config.local", lambda _: temp_local)
    monkeypatch.setattr("perun.logic.config.shared", lambda: temp_global)

    spec_map = workload.load_generator_specifications()
    assert len(spec_map.keys()) == 2
    assert 'gen1' in spec_map.keys()
    assert 'gen2' in spec_map.keys()
    assert 'gen_incorrect' not in spec_map.keys()
    assert 'gen_almost_correct' not in spec_map.keys()

    # Now test that the generators really work :P
    constructor, params = spec_map['gen1']
    for c_status, profile in constructor(integer_job, **params).generate(runner.run_collector):
        assert c_status == CollectStatus.OK
        assert profile
        assert len(profile['resources'])


def test_singleton():
    """Tests singleton generator"""
    collector = Unit('time', {})
    executable = Executable('factor')
    integer_job = Job(collector, [], executable)
    singleton_generator = SingletonGenerator(integer_job, "10")

    job_count = 0
    for c_status, profile in singleton_generator.generate(runner.run_collector):
        assert c_status == CollectStatus.OK
        assert profile
        assert len(profile['resources']) > 0
        job_count += 1
    assert job_count == 1


def test_string_generator():
    """Tests string generator"""
    collector = Unit('time', {})
    executable = Executable('echo')
    string_job = Job(collector, [], executable)
    string_generator = StringGenerator(string_job, 10, 20, 1)

    for c_status, profile in string_generator.generate(runner.run_collector):
        assert c_status == CollectStatus.OK
        assert profile
        assert len(profile['resources']) > 0


def test_file_generator():
    """Tests file generator"""
    collector = Unit('time', {})
    executable = Executable('wc', '-l')
    file_job = Job(collector, [], executable)
    file_generator = TextfileGenerator(file_job, 2, 5)

    for c_status, profile in file_generator.generate(runner.run_collector):
        assert c_status == CollectStatus.OK
        assert profile
        assert len(profile['resources']) > 0
