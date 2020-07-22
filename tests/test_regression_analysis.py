"""Tests of regression analysis functionality.

Every model is tested on a set of provided examples and the computation results are compared with
the expected values. This ensures that the regression analysis formulas are correct.
Sources (if any) to examples are provided in the test functions.

The postprocessby CLI is tested in test_cli module.
"""

import pytest

import perun.utils.exceptions as exceptions
from perun.postprocess.regression_analysis.run import postprocess
import perun.testing.utils as test_utils
from perun.testing.utils import compare_results, generate_models_by_uid

__author__ = 'Jiri Pavela'


def test_incorrect_calls(postprocess_profiles):
    """Test various incorrect calls and exceptions"""
    # Get any profile, in following we will try to
    const_model = test_utils.profile_filter(postprocess_profiles, 'const_model')
    assert const_model is not None

    # Try calling postprocess, while missing keys
    with pytest.raises(exceptions.DictionaryKeysValidationFailed) as exc:
        postprocess(
            const_model, method='full', steps=7, of_key='amount', per_key='structure-unit-size'
        )
    assert 'is missing required key' in str(exc.value)


def test_const_model(postprocess_profiles):
    """Test the constant model computation.

    The r^2 coefficient computation is currently not supported

    Both data sets were created manually as no constant regression analysis example was found.

    Expects to pass all assertions.
    """
    # Get the profile with exponential model testing data
    const_model = test_utils.profile_filter(postprocess_profiles, 'const_model')
    assert const_model is not None

    # Perform the analysis
    code, _, profile = postprocess(
        const_model, method='full', regression_models=['constant'], steps=1,
        of_key='amount', per_key='structure-unit-size')
    assert code.value == 0
    models = generate_models_by_uid(profile, 'constant', ['const::test1', 'const::test2'])

    # Example no. 1:
    # constant line: y = 3
    # expected results:
    #   a = b0 = 3.0
    #   b = b1 = 0.0
    #   r^2    = 1.0 - linear regression model is not matching
    model = next(models)[0]
    compare_results(model['r_square'], 1.0)
    compare_results([c['value'] for c in model['coeffs'] if c['name'] == 'b0'][0], 3.0)
    compare_results([c['value'] for c in model['coeffs'] if c['name'] == 'b1'][0], 0.0)

    # Example no. 2:
    # linear line: x
    # expected results:
    #   a = b0 = 5.5
    #   b = b1 = 0.0
    #   r^2    = 0.0 - linear regression model is perfect match
    model = next(models)[0]
    compare_results(model['r_square'], 0.0)
    compare_results([c['value'] for c in model['coeffs'] if c['name'] == 'b0'][0], 5.5)
    compare_results([c['value'] for c in model['coeffs'] if c['name'] == 'b1'][0], 0.0)


def test_linear_model(postprocess_profiles):
    """Test the linear model computation.

    Contains one sourced and one created example.

    Expects to pass all assertions.
    """
    # Get the profile with exponential model testing data
    linear_model = test_utils.profile_filter(postprocess_profiles, 'linear_model')
    assert linear_model is not None

    # Perform the analysis
    code, _, profile = postprocess(
        linear_model, method='full', regression_models=['linear'], steps=1,
        of_key='amount', per_key='structure-unit-size')
    assert code.value == 0
    models = generate_models_by_uid(profile, 'linear', ['linear::test1', 'linear::test2'])

    # Example no. 1:
    # source: Probability and Statistics for Engineering and the Sciences, 8th ed., example 12.4
    # expected results:
    #   a = b0 = 75.212432
    #   b = b1 = -0.20938742
    #   r^2    = 0.791
    model = next(models)[0]
    compare_results(model['r_square'], 0.791, 0.001)
    compare_results([c['value'] for c in model['coeffs'] if c['name'] == 'b0'][0], 75.212432)
    compare_results([c['value'] for c in model['coeffs'] if c['name'] == 'b1'][0], -0.20938742)

    # Example no. 2:
    # linear line: 8 + 2.5x
    # expected results:
    #   a = b0 = 8
    #   b = b1 = 2.5
    #   r^2    = 1.0
    model = next(models)[0]
    compare_results(model['r_square'], 1.0)
    compare_results([c['value'] for c in model['coeffs'] if c['name'] == 'b0'][0], 8)
    compare_results([c['value'] for c in model['coeffs'] if c['name'] == 'b1'][0], 2.5)


def test_quad_model_using_power(postprocess_profiles):
    """Test the quadratic model computation.

    Contains only one sourced example.

    Expects to pass all assertions.
    """
    # Get the profile with quadratic model testing data
    quad_model = test_utils.profile_filter(postprocess_profiles, 'quad_model')
    assert quad_model is not None

    # Perform the analysis of quadratic-expected models
    code, _, profile = postprocess(quad_model, method='full', regression_models=['quadratic'], steps=1,
                                   of_key='amount', per_key='structure-unit-size')
    assert code.value == 0
    models = generate_models_by_uid(profile, 'quadratic', ['quad::test1'])

    # Example no. 1:
    # source: https://mathbits.com/MathBits/TISection/Statistics2/quadratic.html
    # expected results:
    #   a = b0 = -21.897744
    #   b = b1 = 14.521171
    #   c = b2 = -0.173714
    #   r^2    = 0.981224
    model = next(models)[0]
    compare_results(model['r_square'], 0.981224)
    compare_results([c['value'] for c in model['coeffs'] if c['name'] == 'b0'][0], -21.897744)
    compare_results([c['value'] for c in model['coeffs'] if c['name'] == 'b1'][0], 14.521171)
    compare_results([c['value'] for c in model['coeffs'] if c['name'] == 'b2'][0], -0.173714)


def test_log_model(postprocess_profiles):
    """Test the logarithmic model computation.

    Contains one sourced and one created example.

    Expects to pass all assertions.
    """
    # Get the profile with logarithmic model testing data
    pow_model = test_utils.profile_filter(postprocess_profiles, 'log_model')
    assert pow_model is not None

    # Perform the analysis
    code, _, profile = postprocess(pow_model, method='full', regression_models=['logarithmic'], steps=1,
                                   of_key='amount', per_key='structure-unit-size')
    assert code.value == 0
    models = generate_models_by_uid(profile, 'logarithmic', ['log::test1', 'log::test2'])

    # Example no. 1:
    # link: 'https://mathbits.com/MathBits/TISection/Statistics2/logarithmic.htm'
    # expected results:
    #   a = b0 = 6.099
    #   b = b1 = 6.108
    #   r^2    = 0.9863058
    model = next(models)[0]
    compare_results(model['r_square'], 0.9863058)
    compare_results([c['value'] for c in model['coeffs'] if c['name'] == 'b0'][0], 6.099, 0.01)
    compare_results([c['value'] for c in model['coeffs'] if c['name'] == 'b1'][0], 6.108, 0.01)

    # Example no. 2:
    # logarithmic curve: 0 + 0.434294482 * ln(x)
    # expected results:
    #   a = b0 = 0
    #   b = b1 = 0.434294482
    #   r^2    = 1.0
    model = next(models)[0]
    compare_results(model['r_square'], 1.0)
    compare_results([c['value'] for c in model['coeffs'] if c['name'] == 'b0'][0], 0)
    compare_results([c['value'] for c in model['coeffs'] if c['name'] == 'b1'][0], 0.434294482)


def test_power_model(postprocess_profiles):
    """Test the power model computation.

    Contains two sourced and one created example.

    Expects to pass all assertions.
    """
    # Get the profile with power model testing data
    pow_model = test_utils.profile_filter(postprocess_profiles, 'pow_model')
    assert pow_model is not None

    # Perform the analysis
    code, _, profile = postprocess(pow_model, method='full', regression_models=['power'], steps=1,
                                   of_key='amount', per_key='structure-unit-size')
    assert code.value == 0
    models = generate_models_by_uid(profile, 'power', ['pow::test1', 'pow::test2', 'pow::test3'])

    # Example no. 1:
    # link: 'http://www.real-statistics.com/regression/power-regression/'
    # expected results:
    #   a = b0 = 16.6575389
    #   b = b1 = 0.23438143
    #   r^2    = 0.56822483
    model = next(models)[0]
    compare_results(model['r_square'], 0.56822483)
    compare_results([c['value'] for c in model['coeffs'] if c['name'] == 'b0'][0], 16.6575389)
    compare_results([c['value'] for c in model['coeffs'] if c['name'] == 'b1'][0], 0.23438143)

    # Example no. 2:
    # link: 'https://mathbits.com/MathBits/TISection/Statistics2/power.htm'
    # expected results:
    #   a = b0 = 24.12989312
    #   b = b1 = 0.65949782
    #   r^2    = 0.999992507
    model = next(models)[0]
    compare_results(model['r_square'], 0.999992507)
    compare_results([c['value'] for c in model['coeffs'] if c['name'] == 'b0'][0], 24.12989312)
    compare_results([c['value'] for c in model['coeffs'] if c['name'] == 'b1'][0], 0.65949782)

    # Example no. 3:
    # power curve: 3 * x^3
    # expected results:
    #   a = b0 = 3
    #   b = b1 = 3
    #   r^2    = 1.0
    model = next(models)[0]
    compare_results(model['r_square'], 1.0)
    compare_results([c['value'] for c in model['coeffs'] if c['name'] == 'b0'][0], 3.0)
    compare_results([c['value'] for c in model['coeffs'] if c['name'] == 'b1'][0], 3.0)


def test_exp_model(postprocess_profiles):
    """Test the exponential model computation.

    Contains two sourced and one created example.

    Expects to pass all assertions.
    """
    # Get the profile with exponential model testing data
    exp_model = test_utils.profile_filter(postprocess_profiles, 'exp_model')
    assert exp_model is not None

    # Perform the analysis
    code, _, profile = postprocess(exp_model, method='full', regression_models=['exponential'], steps=1,
                                   of_key='amount', per_key='structure-unit-size')
    assert code.value == 0
    models = generate_models_by_uid(profile, 'exponential',
                                    ['exp::test1', 'exp::test2', 'exp::test3'])

    # Example no. 1:
    # link: 'https://www.youtube.com/watch?v=aw-GluLZIWA'
    # expected results:
    #   a = b0 = 0.1377
    #   b = b1 = 1.023778
    #   r^2    = 0.9652
    model = next(models)[0]
    compare_results(model['r_square'], 0.9652)
    compare_results([c['value'] for c in model['coeffs'] if c['name'] == 'b0'][0], 0.1377)
    compare_results([c['value'] for c in model['coeffs'] if c['name'] == 'b1'][0], 1.023778)

    # Example no. 2:
    # link: 'http://www.real-statistics.com/regression/exponential-regression-models/
    # exponential-regression/'
    # expected results:
    #   a = b0 = 14.0513516
    #   b = b1 = 1.016221137
    #   r^2    = 0.88161289
    model = next(models)[0]
    compare_results(model['r_square'], 0.88161289)
    compare_results([c['value'] for c in model['coeffs'] if c['name'] == 'b0'][0], 14.0513516)
    compare_results([c['value'] for c in model['coeffs'] if c['name'] == 'b1'][0], 1.016221137)

    # Example no. 3:
    # exponential curve y = 1 * 2^x
    # expected results:
    #   a = b0 = 1.0
    #   b - b1 = 2.0
    #   r^2    = 1.0
    model = next(models)[0]
    compare_results(model['r_square'], 1.0)
    compare_results([c['value'] for c in model['coeffs'] if c['name'] == 'b0'][0], 1.0)
    compare_results([c['value'] for c in model['coeffs'] if c['name'] == 'b1'][0], 2.0)
