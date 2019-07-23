"""
The module contains the methods, that executes the computational logic of
`integral_comparison` detection method.
"""

import numpy as np
import scipy.integrate as integrate

import perun.check.factory as factory
import perun.postprocess.regression_analysis.regression_models as regression_models
import perun.postprocess.regression_analysis.tools as tools

from perun.check.factory import PerformanceChange

__author__ = 'Simon Stupinsky'

# acceptable value of relative error between compared profiles to detect NO_CHANGE state
_INTEGRATE_DIFF_NO_CHANGE = .10
# an upper limit of relative error to detect changes between compared profiles
# - the difference between these two values represents the state of uncertain changes - MAYBE
_INTEGRATE_DIFF_CHANGE = .25


def compute_param_integral(model):
    """
    Computation of definite integral of parametric model.

    A method performs the computation of definite integral of the parametric
    model with using its `formula` (function) on interval <`x_start`, `x_end`>.
    According to the value of coefficients from these formulae is computed the
    integral using the general integration method from `scipy` package.

    :param ModelRecord model: model with its required metrics (coefficients,type,etc)
    :return float: the value of integral of `formula` from `x_start` to `x_end`
    """
    formula = regression_models.get_formula_of(model.type)
    coeffs = (model.b0, model.b1,)
    coeffs = coeffs + (model.b2,) if model.type == 'quadratic' else coeffs
    return integrate.quad(formula, model.x_start, model.x_end, args=coeffs)[0]


def compute_nparam_integral(model):
    """
    Computation of integral of non-parametric model.

    A method performs integration of y(x) using samples along the given interval
    from `x_start` to `x_end`. A method divided the `x`-interval according to the
    length of `y`-interval and then execute the computation with using `scipy`
    package.

    :param ModelRecord model: regressogram model with its required metrics
        (bucket_stats, x_start, x_end, ...)
    :return float: the value of integral computed using samples
    """
    x_pts = np.linspace(model.x_start, model.x_end, num=len(model.b0))
    return integrate.simps(model.b0, x_pts)


def classify_change(diff_value, no_change, change, base_per=1):
    """
    Classification of changes according to the value of relative error.

    A method performs an evaluation of relative error value, that was
    computed between two compared profiles. This value is compared
    with threshold values and subsequently is specified the type
    of changes. Following rules are applied:

        * if DIFF_VALUE > 0 then change=DEGRADATION
        ** else DIFF_VALUE <= 0 then change=OPTIMIZATION

        | -> if DIFF_VALUE <= NO_CHANGE_THRESHOLD then state=NO_CHANGE
        || -> elif DIFF_VALUE <= CHANGE_THRESHOLD then state=MAYBE_CHANGE
        ||| -> else DIFF_VALUE > CHANGE_THRESHOLD then state=CHANGE

    :param float diff_value: value of diff value computed between compared profiles
    :param float no_change: threshold to determine `no_change` state
    :param float change: threshold to determine remaining two states (`maybe_change` and `change`)
    :param float base_per: percentage rate from the threshold according to the baseline value
    :return PerformanceChange: determined changes in the basis of given arguments
    """
    if abs(diff_value) <= no_change * base_per:
        change = PerformanceChange.NoChange
    elif abs(diff_value) <= change * base_per:
        change = PerformanceChange.MaybeOptimization if diff_value < 0 else \
            PerformanceChange.MaybeDegradation
    else:
        change = PerformanceChange.Optimization if diff_value < 0 else \
            PerformanceChange.Degradation

    return change


def execute_analysis(_, base_model, targ_model, **__):
    """
    A method performs the primary analysis for pair of models.

    A method executes the comparison of a pair of models. Method computes the integral from
    model values a subsequently is computed the relative error of target model against to
    baseline model. From a value of relative error is determined the change between these
    models with using of the threshold value. At the end is returned the dictionary
    with relevant information about the detected change.

    :param str _: unique identification of given models (not used in this detection method)
    :param ModelRecord base_model: dictionary of baseline model with its required properties
    :param ModelRecord targ_model: dictionary of target_model with its required properties
    :param dict __: unification with remaining detection methods (i.e. Integral Comparison)
    :return DegradationInfo: tuple with degradation info between pair of models:
        (deg. result, deg. location, deg. rate, confidence type and rate, etc.)
    """
    def compute_integral(model):
        """
        This function computes the integral under the curve of the given model.

        According to the kind of the given model, the function determines the
        calculating function, that subsequently calculates the value of integral
        from the given model.

        :param ModelRecord model: dictionary of model with its required properties
        :return float: the result of the integral
        """
        integral_method = compute_param_integral if model.b1 is not None \
            else compute_nparam_integral
        return integral_method(model)

    base_integral = compute_integral(base_model)
    targ_integral = compute_integral(targ_model)

    rel_error = tools.safe_division(targ_integral - base_integral, base_integral)

    change_info = classify_change(
        rel_error if np.isfinite(rel_error) else 0,
        _INTEGRATE_DIFF_NO_CHANGE, _INTEGRATE_DIFF_CHANGE
    )

    return {
        "change_info": change_info,
        "rel_error": round(rel_error if np.isfinite(rel_error) else 0, 2),
    }


def integral_comparison(base_profile, targ_profile, models_strategy='best-model'):
    """
    The wrapper of `integral comparison` detection method. Method calls the general method
    for running the detection between pairs of profile (baseline and target) and subsequently
    returns the information about detected changes.

    :param Profile base_profile: baseline profile against which we are checking the degradation
    :param Profile targ_profile: target profile corresponding to the checked minor version
    :param str models_strategy: detection model strategy for obtains the relevant kind of models
    :returns: tuple - degradation result (structure DegradationInfo)
    """
    for degradation_info in factory.run_detection_for_profiles(
            execute_analysis, base_profile, targ_profile, models_strategy
    ):
        yield degradation_info
