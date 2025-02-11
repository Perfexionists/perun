"""The module contains the method for detection with using linear regression.

This module contains method for classification the performance change between two profiles
according to computed metrics and models from these profiles, based on the linear regression.

"""

from __future__ import annotations

# Standard Imports
from typing import Any, Iterable, TYPE_CHECKING

# Third-Party Imports
from scipy import stats

# Perun Imports
from perun import check as check
from perun.check.methods import fast_check
from perun.check.methods.abstract_base_checker import AbstractBaseChecker
from perun.utils.common import common_kit
from perun.utils.structs.common_structs import DegradationInfo, ModelRecord, ClassificationMethod

if TYPE_CHECKING:
    import numpy
    import numpy.typing as npt

    from perun.profile.factory import Profile


class LinearRegression(AbstractBaseChecker):
    def check(
        self, baseline_profile: Profile, target_profile: Profile, **_: Any
    ) -> Iterable[DegradationInfo]:
        """Temporary function, which call the general function and subsequently returns the
        information about performance changes to calling function.

        :param baseline_profile: base against which we are checking the degradation
        :param target_profile: profile corresponding to the checked minor version
        :param _: unification with other detection methods (unused in this method)
        :returns: tuple (degradation result, degradation location, degradation rate, confidence)
        """

        return check.general_detection(
            baseline_profile, target_profile, ClassificationMethod.LinearRegression
        )


def exec_linear_regression(
    uid: str,
    baseline_x_pts: npt.NDArray[numpy.float64] | list[float],
    lin_abs_error: npt.NDArray[numpy.float64] | list[float],
    threshold: int,
    linear_diff_b1: float,
    baseline_model: ModelRecord,
    target_model: ModelRecord,
    baseline_profile: Profile,
) -> str:
    """Function executes the classification of performance change between two profiles with using
    function from scipy module, concretely linear regression and regression analysis. If that fails
    classification using linear regression, so it will be used regression analysis to the result of
    absolute error. The absolute error is regressed in the all approach used in this method. This
    error is calculated from the linear models from both profiles.

    :param uid: uid for which we are computing the linear regression
    :param baseline_x_pts: values of the independent variables from both profiles
    :param lin_abs_error: the value absolute error computed from the linear models obtained
        from both profiles
    :param threshold: the appropriate value for distinction individual state of detection
    :param linear_diff_b1: difference coefficients b1 from both linear models
    :param baseline_model: the best model from the baseline profile
    :param target_model: the best model from the target profile
    :param baseline_profile: baseline against which we are checking the degradation
    :returns: string (classification of the change)
    """

    # executing the linear regression
    diff_b0 = target_model.b0 - baseline_model.b0
    gradient, intercept, r_value, _, _ = stats.linregress(baseline_x_pts, lin_abs_error)

    # check the first two types of change
    change_type = ""
    if baseline_model.type == "linear" or baseline_model.type == "constant":
        if (
            common_kit.abs_in_absolute_range(gradient, threshold)
            and isinstance(diff_b0, float)
            and common_kit.abs_in_relative_range(diff_b0, intercept, 0.05)
            and abs(diff_b0 - intercept) < 0.000000000001
        ):
            change_type = "constant"
        elif common_kit.abs_in_relative_range(linear_diff_b1, gradient, 0.3) and r_value**2 > 0.95:
            change_type = "linear"
    else:
        if (
            common_kit.abs_in_absolute_range(gradient, threshold)
            and isinstance(diff_b0, float)
            and common_kit.abs_in_relative_range(diff_b0, intercept, 0.05)
        ):
            change_type = "constant"
        elif common_kit.abs_in_relative_range(linear_diff_b1, gradient, 0.3) and r_value**2 > 0.95:
            change_type = "linear"

    std_err_profile = fast_check.exec_fast_check(
        uid, baseline_profile, baseline_x_pts, lin_abs_error
    )
    # obtaining the models (linear and quadratic) from the new regressed profile
    quad_err_model = check.get_filtered_best_models_of(
        std_err_profile,
        group="param",
        model_filter=check.create_filter_by_model("quadratic"),
    )
    linear_err_model = check.get_filtered_best_models_of(
        std_err_profile,
        group="param",
        model_filter=check.create_filter_by_model("linear"),
    )

    # check the last quadratic type of change
    if (
        quad_err_model[uid].r_square > 0.90
        and abs(quad_err_model[uid].r_square - linear_err_model[uid].r_square) > 0.01
    ):
        change_type = "quadratic"

    # We did not classify the change
    if not change_type:
        std_err_model = check.get_filtered_best_models_of(std_err_profile, group="param")
        change_type = std_err_model[uid].type

    return change_type
