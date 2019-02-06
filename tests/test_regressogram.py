"""
Tests of non-parametric method regressogram functionality.

Every method to choose optimal width of bins is tested on a set
of provided examples and the computation results are compared with
the expected values. This ensures that the methods works correctly
always.

The postprocessby CLI is tested in test_cli module.
"""
from perun.postprocess.regressogram.run import postprocess
from tests.test_regression_analysis import profile_filter, generate_models_by_uid, compare_results


def test_bins_method(postprocess_profiles):
    """
    Test the regressogram method with user choice of bins width.

    Expects to pass all assertions.
    """
    # Get the profile with testing data
    test_model = profile_filter(postprocess_profiles, 'exp_model')
    assert test_model is not None

    for bins_method in _EXPECTED_RESULTS.keys():
        # Perform the non-parametric analysis using by regressogram
        code, _, profile = postprocess(test_model, of_key='amount', statistic='mean',
                                       bins=10 if bins_method == 'user' else bins_method, per_key='structure-unit-size')
        # Expected successful analysis by non-parametric postprocessor
        assert code.value == 0
        # Obtaining generator of models from profile in the UID order
        models = generate_models_by_uid(profile, 'regressogram', ['exp::test1', 'exp::test2', 'exp::test3'],
                                        key='method')

        # Test the expected result with each obtained model
        for model, exp_result, interval_result in zip(models, _EXPECTED_RESULTS[bins_method], _COMMON_INTERVAL):
            # Concatenate expected results with interval results to one dict
            exp_result.update(interval_result)
            # Comparison each significant value
            for key in exp_result.keys():
                # Comparison of bin_stats array length
                if key == 'bin_stats':
                    assert len(model[0][key]) == exp_result[key]
                # Double comparison of individual values (r_square, x_interval_start, x_interval_end)
                else:
                    compare_results(model[0][key], exp_result[key], eps=0.00001)
        # Remove generated models for next run of iteration
        del profile['profile']['global']['models']


# Common expected interval edges
_COMMON_INTERVAL = [
    # uid: exp::test1
    {'x_interval_start': 0.0, 'x_interval_end': 110.0, 'y_interval_start': 0.2},
    # uid: exp::test2
    {'x_interval_start': 17.0, 'x_interval_end': 103.0, 'y_interval_start': 18.0},
    # uid: exp::test3
    {'x_interval_start': 0.0, 'x_interval_end': 8.0, 'y_interval_start': 1.0, }
]

# Expected Results
_EXPECTED_RESULTS = {
    'user': [
        # uid: exp::test1
        {'r_square': 0.98007, 'bin_stats': 10},
        # uid: exp::test2
        {'r_square': 0.97567, 'bin_stats': 10},
        # uid: exp::test3
        {'r_square': 1.0, 'bin_stats': 10},
    ],
    'auto': [
        # uid: exp::test1
        {'r_square': 0.99601, 'bin_stats': 22},
        # uid: exp::test2
        {'r_square': 0.99428, 'bin_stats': 19},
        # uid: exp::test3
        {'r_square': 0.0, 'bin_stats': 1},
    ],
    'doane': [
        # uid: exp::test1
        {'r_square': 0.99601, 'bin_stats': 20},
        # uid: exp::test2
        {'r_square': 0.99428, 'bin_stats': 16},
        # uid: exp::test3
        {'r_square': 0.0, 'bin_stats': 1},
    ],
    'fd': [
        # uid: exp::test1
        {'r_square': 1.0, 'bin_stats': 50},
        # uid: exp::test2
        {'r_square': 1.0, 'bin_stats': 36},
        # uid: exp::test3
        {'r_square': 0.66732, 'bin_stats': 3},
    ],
    'rice': [
        # uid: exp::test1
        {'r_square': 0.99601, 'bin_stats': 22},
        # uid: exp::test2
        {'r_square': 0.99428, 'bin_stats': 19},
        # uid: exp::test3
        {'r_square': 0.0, 'bin_stats': 1},
    ],
    'scott': [
        # uid: exp::test1
        {'r_square': 1.0, 'bin_stats': 51},
        # uid: exp::test2
        {'r_square': 1.0, 'bin_stats': 44},
        # uid: exp::test3
        {'r_square': 0.67017, 'bin_stats': 4},
    ],
    'sqrt': [
        # uid: exp::test1
        {'r_square': 1.0, 'bin_stats': 29},
        # uid: exp::test2
        {'r_square': 1.0, 'bin_stats': 25},
        # uid: exp::test3
        {'r_square': 0.34687, 'bin_stats': 2},
    ],
    'sturges': [
        # uid: exp::test1
        {'r_square': 0.99601, 'bin_stats': 22},
        # uid: exp::test2
        {'r_square': 0.99428, 'bin_stats': 19},
        # uid: exp::test3
        {'r_square': 0.0, 'bin_stats': 1},
    ]
}
