"""The module contains the method for detection with using regression analysis.

This module contains method for classification the perfomance change between two profiles
according to computed metrics and models from these profiles, based on the regression analysis.
"""

import copy
import numpy as np

import perun.logic.runner as runner
import perun.check.general_detection as detect


def fast_check(baseline_profile, target_profile):
    """Temporary function, which call the general function and subsequently returns the
    information about performance changes to calling function.

    :param dict baseline_profile: baseline against which we are checking the degradation
    :param dict target_profile: profile corresponding to the checked minor version
    :returns: tuple (degradation result, degradation location, degradation rate, confidence)
    """
    return detect.general_detection(
        baseline_profile, target_profile, detect.ClassificationMethod.FastCheck
    )


def exec_fast_check(uid, baseline_profile, baseline_x_pts, abs_error):
    """The function executes the classification of performance change between two profiles with
    using regression analysis. The type of the best model from the regressed profile, which
    contains the value absolute error, computed from the best models of both profile, is returned
    such as the degree of the changes.

    :param string uid: unique identifier of function for which we are creating the model
    :param Profile baseline_profile: baseline against which we are checking the degradation
    :param np_array baseline_x_pts: the value absolute error computed from the linear models
        obtained from both profiles
    :param integer abs_error: values of the independent variables from both profiles
    :returns: string (classification of the change)
    """
    # creating the new profile
    std_err_profile = copy.deepcopy(baseline_profile)
    std_err_profile['models'].clear()

    updated_data = {
        'structure-unit-size': [],
        'amount': []
    }
    # executing the regression analysis
    for i, (x, y) in enumerate(zip(np.nditer(baseline_x_pts), np.nditer(abs_error))):
        updated_data['structure-unit-size'].append(x)
        updated_data['amount'].append(y)
    # Nasty hack, though it should work
    std_err_profile._storage['resources'] = {
        uid: updated_data
    }
    std_err_profile._storage['resource_type_map'] = {
        uid: {
            'uid': uid
        }
    }

    # Fixme: Extract of and per key
    regression_analysis_params = {
        "regression_models": [],
        "steps": 3,
        "method": "full",
        "of_key": "amount",
        "per_key": "structure-unit-size"
    }
    _, std_err_profile = runner.run_postprocessor_on_profile(
        std_err_profile, 'regression_analysis', regression_analysis_params, skip_store=True
    )

    return std_err_profile
