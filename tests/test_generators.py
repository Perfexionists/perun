"""Basic tests of generators"""

import pytest

from perun.utils.helpers import Job, CollectStatus, Unit
from perun.workload.integer_generator import IntegerGenerator
from perun.workload.generator import Generator


__author__ = 'Tomas Fiedor'


def test_integer_generator():
    """Tests generation of integers from given range"""
    collector = Unit('time', {})
    integer_job = Job(collector, [], 'factor', '', '')
    integer_generator = IntegerGenerator(integer_job, 10, 100, 10)

    for c_status, profile in integer_generator.generate():
        assert c_status == CollectStatus.OK
        assert profile
        assert len(profile['global']['resources']) > 0

    # Try that the pure generator raises error
    pure_generator = Generator(integer_job)
    with pytest.raises(SystemExit):
        _ = list(pure_generator.generate())
