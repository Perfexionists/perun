"""Basic tests for detection method which using polynomial regression.

Tests whether the change is correctly detected and classified. All types of models
are tested to the three types of changes.
"""

import os

import perun.logic.store as store
from tests.degradation_profiles.degradation_results import EXPECTED_RESULTS


def load_profiles():
    pool_path = os.path.join(os.path.split(__file__)[0], 'degradation_profiles')
    profiles = [
        [
            store.load_profile_from_file(os.path.join(pool_path, 'const1.perf'), True),
            store.load_profile_from_file(os.path.join(pool_path, 'const2.perf'), True),
            store.load_profile_from_file(os.path.join(pool_path, 'const3.perf'), True),
            store.load_profile_from_file(os.path.join(pool_path, 'const4.perf'), True)
        ],
        [
            store.load_profile_from_file(os.path.join(pool_path, 'lin1.perf'), True),
            store.load_profile_from_file(os.path.join(pool_path, 'lin2.perf'), True),
            store.load_profile_from_file(os.path.join(pool_path, 'lin3.perf'), True),
            store.load_profile_from_file(os.path.join(pool_path, 'lin4.perf'), True)
        ],
        [
            store.load_profile_from_file(os.path.join(pool_path, 'log1.perf'), True),
            store.load_profile_from_file(os.path.join(pool_path, 'log2.perf'), True),
            store.load_profile_from_file(os.path.join(pool_path, 'log3.perf'), True),
            store.load_profile_from_file(os.path.join(pool_path, 'log4.perf'), True)
        ],
        [
            store.load_profile_from_file(os.path.join(pool_path, 'quad1.perf'), True),
            store.load_profile_from_file(os.path.join(pool_path, 'quad2.perf'), True),
            store.load_profile_from_file(os.path.join(pool_path, 'quad3.perf'), True),
            store.load_profile_from_file(os.path.join(pool_path, 'quad4.perf'), True)
        ],
        [
            store.load_profile_from_file(os.path.join(pool_path, 'pow1.perf'), True),
            store.load_profile_from_file(os.path.join(pool_path, 'pow2.perf'), True),
            store.load_profile_from_file(os.path.join(pool_path, 'pow3.perf'), True),
            store.load_profile_from_file(os.path.join(pool_path, 'pow4.perf'), True)
        ],
        [
            store.load_profile_from_file(os.path.join(pool_path, 'exp1.perf'), True),
            store.load_profile_from_file(os.path.join(pool_path, 'exp2.perf'), True),
            store.load_profile_from_file(os.path.join(pool_path, 'exp3.perf'), True),
            store.load_profile_from_file(os.path.join(pool_path, 'exp4.perf'), True)
        ]
    ]
    return profiles


def check_degradation_result(base_profile, targ_profile, expected_result, function):
    result = list(function(base_profile, targ_profile))
    assert expected_result['result'] in [r.result for r in result]
    assert expected_result['type'] in [r.type for r in result]
    assert expected_result['rate'] in [round(r.rate_degradation) for r in result]


def test_regression_detections_methods():
    """Set of basic tests for testing degradation between profiles

    Expects correct behaviour
    """
    # loading the profiles
    profiles = load_profiles()

    for expected_results in EXPECTED_RESULTS:
        function = expected_results['function']
        expected_results = expected_results['results']
        for profiles_kind, results_kind in zip(profiles, expected_results):
            base_profile = profiles_kind[0]
            for targ_profile, error_kind in zip(profiles_kind[1:], results_kind):
                check_degradation_result(base_profile, targ_profile, error_kind[0], function)
                check_degradation_result(targ_profile, base_profile, error_kind[1], function)
