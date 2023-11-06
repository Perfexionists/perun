"""The module contains the method for detection with using regression analysis.

This module contains method for classification the perfomance change between two profiles
according to computed metrics and models from these profiles, based on the regression analysis.
"""
from __future__ import annotations

import copy
import numpy as np

from typing import Any, Iterable, TYPE_CHECKING

import perun.logic.runner as runner
import perun.check.general_detection as detect

from perun.utils.structs import DegradationInfo

if TYPE_CHECKING:
    from perun.profile.factory import Profile


def fast_check(
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
        baseline_profile, target_profile, detect.ClassificationMethod.FastCheck
    )


def exec_fast_check(
    uid: str,
    baseline_profile: Profile,
    baseline_x_pts: Iterable[float],
    abs_error: Iterable[float],
) -> Profile:
    """For the values specified in the abs_error points, constructs a profile and performs
    a regression analysis inferring set of models.

    :param string uid: unique identifier of function for which we are creating the model
    :param Profile baseline_profile: baseline against which we are checking the degradation
    :param np_array baseline_x_pts: the value absolute error computed from the linear models
        obtained from both profiles
    :param integer abs_error: values of the independent variables from both profiles
    :returns: string (classification of the change)
    """
    # creating the new profile
    std_err_profile = copy.deepcopy(baseline_profile)
    std_err_profile["models"].clear()

    updated_data: dict[str, list[float]] = {"structure-unit-size": [], "amount": []}
    # executing the regression analysis
    for x_pts, y_pts in zip(baseline_x_pts, abs_error):
        if not np.isnan(y_pts):
            updated_data["structure-unit-size"].append(float(x_pts))
            updated_data["amount"].append(float(y_pts))
    # Nasty hack, though it should work
    std_err_profile._storage["resources"] = {uid: updated_data}
    std_err_profile._storage["resource_type_map"] = {uid: {"uid": uid}}
    # Fixme: Extract of and per key
    regression_analysis_params = {
        "regression_models": [],
        "steps": 3,
        "method": "full",
        "of_key": "amount",
        "per_key": "structure-unit-size",
    }
    _, result_std_err_profile = runner.run_postprocessor_on_profile(
        std_err_profile,
        "regression_analysis",
        regression_analysis_params,
        skip_store=True,
    )

    return result_std_err_profile
