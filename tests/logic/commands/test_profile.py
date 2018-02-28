import pytest

import perun.logic.config as config
import perun.profile.factory as factory

__author__ = 'Tomas Fiedor'


def test_name_generation(capsys):
    """Test generation of profile names for various configurations

    Expecting correct outputs
    """
    rt_config = config.runtime()
    rt_config.set('format.output_profile_template', '%collector%-of-%cmd%-%args%-%workload%')
    profile_name = factory.generate_profile_name({
        'header': {
            'cmd': './whatever/sub/fun/mybin',
            'args': '-O2 -q',
            'workload': 'input.txt'
        },
        'collector_info': {
            'name': 'memory',
            'params': {}
        }
    })
    assert profile_name == "memory-of-mybin-[-O2_-q]-[input.txt].perf"

    rt_config.set('format.output_profile_template', '%collector%-%postprocessors%-%origin%')
    profile_name = factory.generate_profile_name({
        'origin': 'c4592b902b7c5773d20693021b76d83de63e4a3a',
        'header': {
            'cmd': './whatever/sub/fun/mybin',
            'args': '-O2 -q',
            'workload': 'input.txt'
        },
        'postprocessors': [
            {'name': 'filter', 'params': {}},
            {'name': 'normalizer', 'params': {}},
        ],
        'collector_info': {
            'name': 'memory',
            'params': {}
        }
    })
    assert profile_name == \
           "memory-after-filter-and-normalizer-c4592b902b7c5773d20693021b76d83de63e4a3a.perf"

    # Lookup of collectors params
    rt_config.set('format.output_profile_template', '%collector%-sampling-[%memory.sampling%]')
    profile_name = factory.generate_profile_name({
        'origin': 'c4592b902b7c5773d20693021b76d83de63e4a3a',
        'header': {
            'cmd': './whatever/sub/fun/mybin',
            'args': '-O2 -q',
            'workload': 'input.txt'
        },
        'postprocessors': [
            {'name': 'filter', 'params': {}},
            {'name': 'normalizer', 'params': {}},
        ],
        'collector_info': {
            'name': 'memory',
            'params': {
                'sampling': 0.01
            }
        }
    })
    assert profile_name == "memory-sampling-[0.01].perf"

    # Lookup in incorrect formatting string
    rt_config.set('format.output_profile_template', '%')
    with pytest.raises(SystemExit):
        factory.generate_profile_name({
            'origin': 'c4592b902b7c5773d20693021b76d83de63e4a3a',
            'header': {
                'cmd': './whatever/sub/fun/mybin',
                'args': '-O2 -q',
                'workload': 'input.txt'
            },
            'postprocessors': [
                {'name': 'filter', 'params': {}},
                {'name': 'normalizer', 'params': {}},
            ],
            'collector_info': {
                'name': 'memory',
                'params': {
                    'sampling': 0.01
                }
            }
        })

    _, err = capsys.readouterr()
    assert "formatting string '%' could not be parsed" in err

    # Try missing param
    rt_config.set('format.output_profile_template', 'sampling-[%memory.sampling%]')
    profile_name = factory.generate_profile_name({
        'collector_info': {
            'name': 'complexity'
        }
    })
    assert profile_name == "sampling-[_].perf"
