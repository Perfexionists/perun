"""The module contains the method for detection with using polynomial regression.

This module contains method for classification the perfomance change between two profiles
according to computed metrics and models from these profiles, based on the polynomial regression.

"""

import numpy as np

import perun.check.general_detection as detect

THRESHOLD = 100000000

def polynomial_regression(baseline_profile, target_profile):
    """Temporary function, which call the general function and subsequently returns the
    information about performance changes to calling function.

    :param dict baseline_profile: baseline against which we are checking the degradation
    :param dict target_profile: profile corresponding to the checked minor version
    :returns: tuple (degradation result, degradation location, degradation rate, confidence)
    """

    return detect.general_detection(baseline_profile, target_profile)

def exec_polynomial_regression(baseline_x_pts, lin_abs_error):
    """The function executes the classification of performance change between two profiles with
    using function from numpy module, concretely polyfit. Our effort is well-fit interleaving of
    the data by polynomials of the certain degrees can pretty accurately classify how big change
    has occurred between profiles

    :param np_array baseline_x_pts: the value absolute error computed from the linear models obtained from both profiles
    :param integer lin_abs_error: values of the independent variables from both profiles
    :returns: string (classification of the change)
    """
    # executing the polynomial regression
    polynom = np.polyfit(baseline_x_pts, lin_abs_error, 0, None, True)
    for degree in range(0, 4):
        if polynom[1][0] >= THRESHOLD:
            polynom = np.polyfit(baseline_x_pts, lin_abs_error, degree+1, None, True)
        else:
            break

    # classification the degree of changes
    if degree == 0:
        change_type = 'CONSTANT '
    elif degree == 1:
        change_type = 'LINEAR '
    elif degree == 2:
        change_type = 'QUADRATIC '
    else:
        change_type = 'UNKOWN '
    return change_type