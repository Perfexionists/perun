"""Basic tests for detection method which using polynomial regression.

Tests whether the change is correctly detected and classified. All types of models
are tested to the three types of changes.
"""
from __future__ import annotations

# Standard Imports
import itertools
import os

# Third-Party Imports

# Perun Imports
from perun.logic import store
from perun.testing.mock_results import PARAM_EXPECTED_RESULTS, NONPARAM_EXPECTED_RESULTS
from perun.utils.log import aggregate_intervals
from perun.utils.structs import PerformanceChange
import perun.check.factory as check_factory


def load_profiles(param):
    pool_path = os.path.join(os.path.split(__file__)[0], "profiles", "degradation_profiles")
    if param:
        profiles = [
            [
                store.load_profile_from_file(os.path.join(pool_path, "const1.perf"), True, True),
                store.load_profile_from_file(os.path.join(pool_path, "const2.perf"), True, True),
                store.load_profile_from_file(os.path.join(pool_path, "const3.perf"), True, True),
                store.load_profile_from_file(os.path.join(pool_path, "const4.perf"), True, True),
            ],
            [
                store.load_profile_from_file(os.path.join(pool_path, "lin1.perf"), True, True),
                store.load_profile_from_file(os.path.join(pool_path, "lin2.perf"), True, True),
                store.load_profile_from_file(os.path.join(pool_path, "lin3.perf"), True, True),
                store.load_profile_from_file(os.path.join(pool_path, "lin4.perf"), True, True),
            ],
            [
                store.load_profile_from_file(os.path.join(pool_path, "log1.perf"), True, True),
                store.load_profile_from_file(os.path.join(pool_path, "log2.perf"), True, True),
                store.load_profile_from_file(os.path.join(pool_path, "log3.perf"), True, True),
                store.load_profile_from_file(os.path.join(pool_path, "log4.perf"), True, True),
            ],
            [
                store.load_profile_from_file(os.path.join(pool_path, "quad1.perf"), True, True),
                store.load_profile_from_file(os.path.join(pool_path, "quad2.perf"), True, True),
                store.load_profile_from_file(os.path.join(pool_path, "quad3.perf"), True, True),
                store.load_profile_from_file(os.path.join(pool_path, "quad4.perf"), True, True),
            ],
            [
                store.load_profile_from_file(os.path.join(pool_path, "pow1.perf"), True, True),
                store.load_profile_from_file(os.path.join(pool_path, "pow2.perf"), True, True),
                store.load_profile_from_file(os.path.join(pool_path, "pow3.perf"), True, True),
                store.load_profile_from_file(os.path.join(pool_path, "pow4.perf"), True, True),
            ],
            [
                store.load_profile_from_file(os.path.join(pool_path, "exp1.perf"), True, True),
                store.load_profile_from_file(os.path.join(pool_path, "exp2.perf"), True, True),
                store.load_profile_from_file(os.path.join(pool_path, "exp3.perf"), True, True),
                store.load_profile_from_file(os.path.join(pool_path, "exp4.perf"), True, True),
            ],
        ]
    else:
        profiles = [
            store.load_profile_from_file(
                os.path.join(pool_path, "baseline_all_models.perf"), True, True
            ),
            store.load_profile_from_file(
                os.path.join(pool_path, "target_all_models.perf"), True, True
            ),
        ]
    return profiles


def check_degradation_result(baseline_profile, target_profile, expected_result, function):
    result = list(check_factory.run_degradation_check(function, baseline_profile, target_profile))
    assert expected_result["result"] & {r.result for r in result}
    assert expected_result["type"] & {r.type for r in result}
    assert expected_result["rate"] & {round(r.rate_degradation) for r in result}


def test_regression_detections_methods():
    """Set of basic tests for testing degradation between profiles

    Expects correct behaviour
    """
    # loading the profiles
    profiles = load_profiles(param=True)

    for expected_results in PARAM_EXPECTED_RESULTS:
        function = expected_results["function"]
        expected_results = expected_results["results"]
        for profiles_kind, results_kind in zip(profiles, expected_results):
            baseline_profile = profiles_kind[0]
            for target_profile, error_kind in zip(profiles_kind[1:], results_kind):
                check_degradation_result(baseline_profile, target_profile, error_kind[0], function)
                check_degradation_result(target_profile, baseline_profile, error_kind[1], function)


def test_complex_detection_methods():
    """Set of basic tests for testing degradation between profiles

    Expects correct behaviour
    """
    # loading the profiles
    profiles = load_profiles(param=False)

    for expected_results in NONPARAM_EXPECTED_RESULTS:
        degradation_list = list(
            check_factory.run_degradation_check(
                expected_results["function"], profiles[0], profiles[1], models_strategy="all-models"
            )
        )
        expected_result = expected_results["results"].pop(0)
        degradation_list.sort(key=lambda item: (item.location, item.from_baseline))
        for _, changes in itertools.groupby(
            degradation_list, lambda item: (item.location, item.from_baseline)
        ):
            for test_deg_info in changes:
                if test_deg_info.result != PerformanceChange.NoChange:
                    assert expected_result.result == test_deg_info.result
                    assert expected_result.location == test_deg_info.location
                    assert expected_result.from_baseline == test_deg_info.from_baseline
                    assert expected_result.to_target == test_deg_info.to_target
                    assert expected_result.rate_degradation == test_deg_info.rate_degradation
                    if len(test_deg_info.partial_intervals) > 0:
                        assert expected_result.partial_intervals == aggregate_intervals(
                            test_deg_info.partial_intervals
                        )
                    if expected_results["results"]:
                        expected_result = expected_results["results"].pop(0)
