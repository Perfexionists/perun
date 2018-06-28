"""Basic tests of generators"""

import pytest

import perun.logic.config as config
import perun.workload as workload
import perun.logic.runner as runner

from perun.utils.helpers import Job, CollectStatus, Unit
from perun.workload.integer_generator import IntegerGenerator
from perun.workload.singleton_generator import SingletonGenerator
from perun.workload.string_generator import StringGenerator
from perun.workload.textfile_generator import TextfileGenerator
from perun.workload.generator import Generator


__author__ = 'Tomas Fiedor'


def test_integer_generator():
    """Tests generation of integers from given range"""
    collector = Unit('time', {})
    integer_job = Job(collector, [], 'factor', '', '')
    integer_generator = IntegerGenerator(integer_job, 10, 100, 10)

    for c_status, profile in integer_generator.generate(runner.run_collector):
        assert c_status == CollectStatus.OK
        assert profile
        assert len(profile['global']['resources']) > 0

    # Try that the pure generator raises error
    pure_generator = Generator(integer_job)
    with pytest.raises(SystemExit):
        _ = list(pure_generator.generate(runner.run_collector))


def test_loading_generators_from_config(monkeypatch, pcs_full):
    """Tests loading generator specification from config"""
    # Initialize the testing configurations
    collector = Unit('time', {})
    integer_job = Job(collector, [], 'factor', '', '')
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
        assert len(profile['global']['resources'])


def test_singleton():
    """Tests singleton generator"""
    collector = Unit('time', {})
    integer_job = Job(collector, [], 'factor', '', '')
    singleton_generator = SingletonGenerator(integer_job, "10")

    job_count = 0
    for c_status, profile in singleton_generator.generate(runner.run_collector):
        assert c_status == CollectStatus.OK
        assert profile
        assert len(profile['global']['resources']) > 0
        job_count += 1
    assert job_count == 1


def test_string_generator():
    """Tests string generator"""
    collector = Unit('time', {})
    string_job = Job(collector, [], 'echo', '', '')
    string_generator = StringGenerator(string_job, 10, 20, 1)

    for c_status, profile in string_generator.generate(runner.run_collector):
        assert c_status == CollectStatus.OK
        assert profile
        assert len(profile['global']['resources']) > 0


def test_file_generator():
    """Tests file generator"""
    collector = Unit('time', {})
    file_job = Job(collector, [], 'wc', '-l', '')
    file_generator = TextfileGenerator(file_job, 2, 5)

    for c_status, profile in file_generator.generate(runner.run_collector):
        assert c_status == CollectStatus.OK
        assert profile
        assert len(profile['global']['resources']) > 0
