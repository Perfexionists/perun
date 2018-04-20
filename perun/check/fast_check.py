"""The module contains the method for detection with using regression analysis.

This module contains method for classification the perfomance change between two profiles
according to computed metrics and models from these profiles, based on the regression analysis.

"""

import copy
import numpy as np

import perun.check as check
import perun.logic.runner as runner
import perun.check.general_detection as detect

def fast_check(baseline_profile, target_profile):
    """Temporary function, which call the general function and subsequently returns the 
    information about performance changes to calling function.

    :param dict baseline_profile: baseline against which we are checking the degradation
    :param dict target_profile: profile corresponding to the checked minor version    
    :returns: tuple (degradation result, degradation location, degradation rate, confidence)
    """
    
    return detect.general_detection(baseline_profile, target_profile, 2)

def exec_fast_check(baseline_profile, baseline_x_pts, abs_error):
    """The function executes the classification of performance change between two profiles with 
    using regression analysis. The type of the best model from the regressed profile, which 
    contains the value absolute error, computed from the best models of both profile, is returned
    such as the degree of the changes.

    :param dict baseline_profile: baseline against which we are checking the degradation
    :param np_array baseline_x_pts: the value absolute error computed from the linear models obtained from both profiles
    :param integer abs_error: values of the independent variables from both profiles
    :returns: string (classification of the change)
    """

    # creating the new profile
    std_err_profile = copy.deepcopy(baseline_profile)
    del std_err_profile['global']['models']    

    # executing the regression analysis
    i = 0
    for x, y in zip(np.nditer(baseline_x_pts), np.nditer(abs_error)):
        std_err_profile['global']['resources'][i]['structure-unit-size'] = x
        std_err_profile['global']['resources'][i]['amount'] = y
        i += 1
        
    std_err_profile = runner.run_postprocessor_on_profile(std_err_profile, 'regression_analysis', {
        "regression_models": [],
        "steps": 3,
        "method": "full"
    }, True)
    std_err_model = check.general_detection.get_best_models_of(std_err_profile)
    return std_err_model