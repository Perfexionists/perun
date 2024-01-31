"""
Tests of non-parametric method regressogram functionality.

Every method to choose optimal width of buckets is tested on a set
of provided examples and the computation results are compared with
the expected values. This ensures that the methods works correctly
always.

The postprocessby CLI is tested in test_cli module.
"""
from __future__ import annotations

# Standard Imports

# Third-Party Imports

# Perun Imports
from perun.postprocess.regressogram.run import postprocess
import perun.testing.utils as test_utils


def test_regressogram_method():
    """
    Test the regressogram method with user choice of buckets width.

    Expects to pass all assertions.
    """
    # Get the profile with testing data
    test_model = test_utils.load_profile("postprocess_profiles", "exp_model_datapoints.perf")
    assert test_model is not None

    for current_method in _EXPECTED_RESULTS.keys():
        # Perform the non-parametric analysis using by regressogram
        code, _, profile = postprocess(
            test_model,
            of_key="amount",
            statistic_function="mean",
            bucket_number=10 if current_method == "user" else None,
            bucket_method=current_method if current_method != "user" else None,
            per_key="structure-unit-size",
        )
        # Expected successful analysis by non-parametric postprocessor
        assert code.value == 0
        # Obtaining generator of models from profile in the UID order
        models = test_utils.generate_models_by_uid(
            profile,
            "regressogram",
            ["exp::test1", "exp::test2", "exp::test3"],
            key="model",
        )

        # Test the expected result with each obtained model
        for model, exp_result, interval_result in zip(
            models, _EXPECTED_RESULTS[current_method], _COMMON_INTERVAL
        ):
            # Concatenate expected results with interval results to one dict
            exp_result.update(interval_result)
            # Comparison each significant value
            for key in exp_result.keys():
                # Comparison of bucket_stats array length
                if key == "bucket_stats":
                    assert len(model[0][key]) == exp_result[key]
                # Double comparison of individual values (r_square, x_start, x_end)
                else:
                    test_utils.compare_results(model[0][key], exp_result[key], eps=0.00001)
        # Remove generated models for next run of iteration
        profile["profile"]["models"].clear()


# Common expected interval edges
_COMMON_INTERVAL = [
    # uid: exp::test1
    {"x_start": 0.0, "x_end": 110.0, "y_start": 0.2},
    # uid: exp::test2
    {"x_start": 17.0, "x_end": 103.0, "y_start": 18.0},
    # uid: exp::test3
    {"x_start": 0.0, "x_end": 8.0, "y_start": 1.0},
]

# Expected Results
_EXPECTED_RESULTS = {
    "user": [
        # uid: exp::test1
        {"r_square": 0.98007, "bucket_stats": 10},
        # uid: exp::test2
        {"r_square": 0.97567, "bucket_stats": 10},
        # uid: exp::test3
        {"r_square": 1.0, "bucket_stats": 10},
    ],
    "auto": [
        # uid: exp::test1
        {"r_square": 0.99601, "bucket_stats": 22},
        # uid: exp::test2
        {"r_square": 0.99428, "bucket_stats": 19},
        # uid: exp::test3
        {"r_square": 0.0, "bucket_stats": 1},
    ],
    "doane": [
        # uid: exp::test1
        {"r_square": 0.99601, "bucket_stats": 20},
        # uid: exp::test2
        {"r_square": 0.99428, "bucket_stats": 16},
        # uid: exp::test3
        {"r_square": 0.0, "bucket_stats": 1},
    ],
    "fd": [
        # uid: exp::test1
        {"r_square": 1.0, "bucket_stats": 50},
        # uid: exp::test2
        {"r_square": 1.0, "bucket_stats": 36},
        # uid: exp::test3
        {"r_square": 0.66732, "bucket_stats": 3},
    ],
    "rice": [
        # uid: exp::test1
        {"r_square": 0.99601, "bucket_stats": 22},
        # uid: exp::test2
        {"r_square": 0.99428, "bucket_stats": 19},
        # uid: exp::test3
        {"r_square": 0.0, "bucket_stats": 1},
    ],
    "scott": [
        # uid: exp::test1
        {"r_square": 1.0, "bucket_stats": 51},
        # uid: exp::test2
        {"r_square": 1.0, "bucket_stats": 44},
        # uid: exp::test3
        {"r_square": 0.67017, "bucket_stats": 4},
    ],
    "sqrt": [
        # uid: exp::test1
        {"r_square": 1.0, "bucket_stats": 29},
        # uid: exp::test2
        {"r_square": 1.0, "bucket_stats": 25},
        # uid: exp::test3
        {"r_square": 0.34687, "bucket_stats": 2},
    ],
    "sturges": [
        # uid: exp::test1
        {"r_square": 0.99601, "bucket_stats": 22},
        # uid: exp::test2
        {"r_square": 0.99428, "bucket_stats": 19},
        # uid: exp::test3
        {"r_square": 0.0, "bucket_stats": 1},
    ],
}
