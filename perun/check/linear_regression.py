"""The module contains the method for detection with using linear regression.

This module contains method for classification the perfomance change between two profiles
according to computed metrics and models from these profiles, based on the linear regression.

"""
import scipy.stats as stats
import nptyping as npt

from typing import Any, Iterable

import perun.utils as utils
import perun.check.general_detection as detect
import perun.check.fast_check as fast_check
import perun.utils.structs

from perun.profile.factory import Profile
from perun.utils.structs import DegradationInfo


def linear_regression(
        baseline_profile: Profile, target_profile: Profile, **_: Any
) -> Iterable[DegradationInfo]:
    """Temporary function, which call the general function and subsequently returns the
    information about performance changes to calling function.

    :param dict baseline_profile: base against which we are checking the degradation
    :param dict target_profile: profile corresponding to the checked minor version
    :param dict _: unification with other detection methods (unused in this method)
    :returns: tuple (degradation result, degradation location, degradation rate, confidence)
    """

    return detect.general_detection(
        baseline_profile, target_profile, detect.ClassificationMethod.LinearRegression
    )


def exec_linear_regression(
        uid: str,
        baseline_x_pts: npt.NDArray, lin_abs_error: npt.NDArray,
        threshold: int, linear_diff_b1: int,
        baseline_model: perun.utils.structs.ModelRecord, target_model: perun.utils.structs.ModelRecord,
        baseline_profile: Profile
) -> str:
    """Function executes the classification of performance change between two profiles with using
    function from scipy module, concretely linear regression and regression analysis. If that fails
    classification using linear regression, so it will be used regression analysis to the result of
    absolute error. The absolute error is regressed in the all approach used in this method. This
    error is calculated from the linear models from both profiles.

    :param str uid: uid for which we are computing the linear regression
    :param np_array baseline_x_pts: values of the independent variables from both profiles
    :param np_array lin_abs_error: the value absolute error computed from the linear models obtained
        from both profiles
    :param integer threshold: the appropriate value for distinction individual state of detection
    :param integer linear_diff_b1: difference coefficients b1 from both linear models
    :param ModelRecord baseline_model: the best model from the baseline profile
    :param ModelRecord target_model: the best model from the target profile
    :param dict baseline_profile: baseline against which we are checking the degradation
    :returns: string (classification of the change)
    """

    # executing the linear regression
    diff_b0 = target_model.b0 - baseline_model.b0
    gradient, intercept, r_value, _, _ = stats.linregress(baseline_x_pts, lin_abs_error)

    # check the first two types of change
    change_type = ''
    if baseline_model.type == 'linear' or baseline_model.type == 'constant':
        if utils.abs_in_absolute_range(gradient, threshold) \
                and utils.abs_in_relative_range(diff_b0, intercept, 0.05) \
                and abs(diff_b0 - intercept) < 0.000000000001:
            change_type = 'constant'
        elif utils.abs_in_relative_range(linear_diff_b1, gradient, 0.3) \
                and r_value**2 > 0.95:
            change_type = 'linear'
    else:
        if utils.abs_in_absolute_range(gradient, threshold) \
                and utils.abs_in_relative_range(diff_b0, intercept, 0.05):
            change_type = 'constant'
        elif utils.abs_in_relative_range(linear_diff_b1, gradient, 0.3) \
                and r_value**2 > 0.95:
            change_type = 'linear'

    std_err_profile = fast_check.exec_fast_check(
        uid, baseline_profile, baseline_x_pts, lin_abs_error
    )
    # obtaining the models (linear and quadratic) from the new regressed profile
    quad_err_model = detect.get_filtered_best_models_of(
        std_err_profile, group='param', model_filter=detect.create_filter_by_model('quadratic')
    )
    linear_err_model = detect.get_filtered_best_models_of(
        std_err_profile, group='param', model_filter=detect.create_filter_by_model('linear')
    )

    # check the last quadratic type of change
    if quad_err_model[uid].r_square > 0.90 \
            and abs(quad_err_model[uid].r_square - linear_err_model[uid].r_square) > 0.01:
        change_type = 'quadratic'

    # We did not classify the change
    if not change_type:
        std_err_model = detect.get_filtered_best_models_of(std_err_profile, group='param')
        change_type = std_err_model[uid].type

    return change_type
