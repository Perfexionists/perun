"""
The module contains the methods, that executes the computational logic of
`integral_comparison` detection method.
"""

import numpy as np
import scipy.integrate as integrate

from typing import Dict, List, Any, Iterable

import perun.check.factory as factory
import perun.check.nonparam_helpers as nparam_helpers
import perun.postprocess.regression_analysis.regression_models as regression_models
import perun.postprocess.regression_analysis.tools as tools
import perun.utils.structs

from perun.profile.factory import Profile
from perun.utils.structs import DegradationInfo, ModelRecord

__author__ = 'Simon Stupinsky'

# acceptable value of relative error between compared profiles to detect NO_CHANGE state
_INTEGRATE_DIFF_NO_CHANGE = .10
# an upper limit of relative error to detect changes between compared profiles
# - the difference between these two values represents the state of uncertain changes - MAYBE
_INTEGRATE_DIFF_CHANGE = .25


def compute_param_integral(model: perun.utils.structs.ModelRecord) -> float:
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
    coeffs = (model.b0, model.b1, model.b2,) if model.type == 'quadratic' else (model.b0, model.b1)
    return integrate.quad(formula, model.x_start, model.x_end, args=coeffs)[0]


def compute_nparam_integral(x_pts: List[float], y_pts: List[float]) -> float:
    """
    Computation of integral of non-parametric model.

    A method performs integration of y(x) using samples along the given interval
    from `x_start` to `x_end`. A method divided the `x`-interval according to the
    length of `y`-interval and then execute the computation with using `scipy`
    package.

    :param list x_pts: list of x-coordinates from non-parametric model
    :param list y_pts: list of y-coordinates from non-parametric model
    :return float: the value of integral computed using samples
    """
    return integrate.simps(y_pts, x_pts)


def execute_analysis(
        uid: str,
        baseline_model: ModelRecord,
        target_model: ModelRecord,
        target_profile: Profile,
        **_: Any
) -> Dict[str, Any]:
    """
    A method performs the primary analysis for pair of models.

    A method executes the comparison of a pair of models. Method computes the integral from
    model values a subsequently is computed the relative error of target model against to
    baseline model. From a value of relative error is determined the change between these
    models with using of the threshold value. At the end is returned the dictionary
    with relevant information about the detected change.

    :param str uid: unique identification of given models (not used in this detection method)
    :param ModelRecord baseline_model: dictionary of baseline model with its required properties
    :param ModelRecord target_model: dictionary of target_model with its required properties
    :param Profile target_profile: target profile for the analysis
    :param dict kwargs: unification with remaining detection methods (i.e. Integral Comparison)
    :return DegradationInfo: tuple with degradation info between pair of models:
        (deg. result, deg. location, deg. rate, confidence type and rate, etc.)
    """
    x_pts, baseline_y_pts, target_y_pts = nparam_helpers.preprocess_nonparam_models(
        uid, baseline_model, target_profile, target_model
    )

    baseline_integral = compute_param_integral(baseline_model) if baseline_model.b1 is not None else \
        compute_nparam_integral(x_pts, baseline_y_pts)
    target_integral = compute_param_integral(target_model) if target_model.b1 is not None else \
        compute_nparam_integral(x_pts, target_y_pts)

    rel_error = tools.safe_division(float(target_integral - baseline_integral), float(baseline_integral))

    change_info = nparam_helpers.classify_change(
        rel_error if np.isfinite(rel_error) else 0,
        _INTEGRATE_DIFF_NO_CHANGE, _INTEGRATE_DIFF_CHANGE
    )

    return {
        "change_info": change_info,
        "rel_error": round(rel_error if np.isfinite(rel_error) else 0, 2),
    }


def integral_comparison(
        baseline_profile: Profile, target_profile: Profile, models_strategy: str = 'best-model'
) -> Iterable[DegradationInfo]:
    """
    The wrapper of `integral comparison` detection method. Method calls the general method
    for running the detection between pairs of profile (baseline and target) and subsequently
    returns the information about detected changes.

    :param Profile baseline_profile: baseline profile against which we are checking the degradation
    :param Profile target_profile: target profile corresponding to the checked minor version
    :param str models_strategy: detection model strategy for obtains the relevant kind of models
    :returns: tuple - degradation result (structure DegradationInfo)
    """
    for degradation_info in factory.run_detection_with_strategy(
            execute_analysis, baseline_profile, target_profile, models_strategy
    ):
        yield degradation_info
