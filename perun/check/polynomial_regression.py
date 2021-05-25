"""The module contains the method for detection with using polynomial regression.

This module contains method for classification the perfomance change between two profiles
according to computed metrics and models from these profiles, based on the polynomial regression.
"""

import numpy as np

from typing import Any, Iterable
from nptyping import NDArray

import perun.check.general_detection as detect

from perun.profile.factory import Profile
from perun.utils.structs import DegradationInfo

THRESHOLD = 100000000


def polynomial_regression(
        baseline_profile: Profile, target_profile: Profile, **_: Any
) -> Iterable[DegradationInfo]:
    """Temporary function, which call the general function and subsequently returns the
    information about performance changes to calling function.

    :param dict baseline_profile: baseline against which we are checking the degradation
    :param dict target_profile: profile corresponding to the checked minor version
    :param dict _: unification with other detection methods (unused in this method)
    :returns: tuple (degradation result, degradation location, degradation rate, confidence)
    """

    return detect.general_detection(
        baseline_profile, target_profile, detect.ClassificationMethod.PolynomialRegression
    )


def exec_polynomial_regression(baseline_x_pts: NDArray, lin_abs_error: NDArray) -> str:
    """The function executes the classification of performance change between two profiles with
    using function from numpy module, concretely polyfit. Our effort is well-fit interleaving of
    the data by polynomials of the certain degrees can pretty accurately classify how big change
    has occurred between profiles

    :param np_array baseline_x_pts: the value absolute error computed from the linear models
        obtained from both profiles
    :param integer lin_abs_error: values of the independent variables from both profiles
    :returns: string (classification of the change)
    """
    degree = 0
    # executing the polynomial regression
    polynom = np.polyfit(baseline_x_pts, lin_abs_error, 0, None, True)
    for degree in range(0, 4):
        if polynom[1][0] < THRESHOLD:
            break
        polynom = np.polyfit(baseline_x_pts, lin_abs_error, degree+1, None, True)

    # classification the degree of changes
    return {
        0: 'constant',
        1: 'linear',
        2: 'quadratic '
    }.get(degree, "unknown")
