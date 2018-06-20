"""The module contains the method for detection with using linear regression.

This module contains method for classification the perfomance change between two profiles
according to computed metrics and models from these profiles, based on the linear regression.

"""
import scipy.stats as stats

import perun.check.general_detection as detect
import perun.check as check
import perun.check.fast_check as fast_check


def linear_regression(baseline_profile, target_profile):
    """Temporary function, which call the general function and subsequently returns the
    information about performance changes to calling function.

    :param dict baseline_profile: baseline against which we are checking the degradation
    :param dict target_profile: profile corresponding to the checked minor version
    :returns: tuple (degradation result, degradation location, degradation rate, confidence)
    """

    return detect.general_detection(baseline_profile, target_profile, 1)

def exec_linear_regression(baseline_x_pts, lin_abs_error, THRESHOLD, linear_diff_b1, baseline_model, target_model, baseline_profile):
    """Function executes the classification of performance change between two profiles with using function
    from scipy module, concretely linear regression and regression analysis. If that fails classification
    using linear regression, so it will be used regression analysis to the result of absolute error. The
    absolute error is regressed in the all approach used in this method. This error is calculated from
    the linear models from both profiles.

    :param np_array baseline_x_pts: values of the independent variables from both profiles
    :param np_array lin_abs_error: the value absolute error computed from the linear models obtained from both profiles
    :param integer THRESHOLD: the appropriate value for distinction individual state of detection
    :param integer linear_diff_b1: difference coefficients b1 from both linear models
    :param dict baseline_model: the best model from the baseline profile
    :param dict target_model: the best model from the target profile
    :param dict baseline_profile: baseline against which we are checking the degradation
    :returns: string (classification of the change)
    """

    # executing the linear regression
    diff_b0 = target_model[1][2] - baseline_model[1][2]
    gradient, intercept, r_value, _, _ = stats.linregress(baseline_x_pts, lin_abs_error)

    # check the first two types of change
    change_type = ''
    if (baseline_model[1][0] == 'linear' or baseline_model[1][0] == 'constant'):
        if (-abs(THRESHOLD) <= abs(gradient) <= abs(THRESHOLD) and abs(0.95*intercept) <= abs(diff_b0) <= abs(1.05*intercept) and abs(diff_b0 - intercept) < 0.000000000001):
            change_type = 'CONSTANT '
        elif (abs(0.70*gradient) <= abs(linear_diff_b1) <= abs(1.30*gradient) and r_value**2 > 0.95):
            change_type = 'LINEAR '
    else:
        if (-abs(THRESHOLD) <= abs(gradient) <= abs(THRESHOLD) and abs(0.95*intercept) <= abs(diff_b0) <= abs(1.05*intercept)):
            change_type = 'CONSTANT '
        elif (abs(0.70*gradient) <= abs(linear_diff_b1) <= abs(1.30*gradient) and r_value**2 > 0.95):
            change_type = 'LINEAR '

    std_err_profile = fast_check.exec_fast_check(baseline_profile, baseline_x_pts, lin_abs_error, True)
    # obtaining the models (linear and quadratic) from the new regressed profile
    quad_err_model = check.general_detection.get_best_models_of(std_err_profile, 'quadratic')
    linear_err_model = check.general_detection.get_best_models_of(std_err_profile, 'linear')

    # check the last quadratic type of change
    if (quad_err_model[baseline_model[0]][1] > 0.90 and abs(quad_err_model[baseline_model[0]][1] - linear_err_model[baseline_model[0]][1]) > 0.01):
        change_type = 'QUADRATIC '

    if change_type == '':
        std_err_model = check.general_detection.get_best_models_of(std_err_profile)
        change_type = std_err_model[baseline_model[0]][0] + ' '

    return change_type