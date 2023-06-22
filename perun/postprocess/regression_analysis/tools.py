"""Regression tools module. Contains utility functions used by the other regression modules.

"""

from random import shuffle
from operator import itemgetter
import numpy as np

from typing import Mapping, Any

import perun.utils.exceptions as exceptions


# Minimum points count to perform the regression
MIN_POINTS_COUNT = 3
# R^2 value if computation failed
R_SQUARE_DEFAULT = 0.0
# Zero approximation to avoid zero division etc.
APPROX_ZERO = 0.000001


def validate_dictionary_keys(
        dictionary: Mapping[str, Any], required_keys: list, forbidden_keys: list
):
    """Checks the dictionary for missing required keys and excess forbidden keys.

    :param dict dictionary: validated dictionary
    :param list of str required_keys: keys that must be present in the inspected dictionary
    :param list of str forbidden_keys: keys that must not be in the inspected dictionary
    :raises DictionaryKeysValidationFailed: if the dictionary inspection fails
    """
    missing_keys, excess_keys = [], []

    # Check all the required keys
    for key in required_keys:
        if key not in dictionary:
            missing_keys.append(key)
    # Check all the forbidden keys
    for key in forbidden_keys:
        if key in dictionary:
            excess_keys.append(key)

    # Raise exception if needed
    if missing_keys or excess_keys:
        raise exceptions.DictionaryKeysValidationFailed(dictionary, missing_keys, excess_keys)


def check_points(x_len, y_len, threshold):
    """Checks the regression points for possible problems

    :param int x_len: the count of x coordinates
    :param int y_len: the count of y coordinates
    :param int threshold: the minimum number of points
    :raises InvalidPointsException: if the points count is too low or their coordinates list have
        different lengths
    """
    if x_len < threshold or y_len < threshold or x_len != y_len:
        raise exceptions.InvalidPointsException(x_len, y_len, MIN_POINTS_COUNT)


def split_sequence(length, parts):
    """Generator. Splits the given (collection) length into roughly equal parts and yields the part
       start and end indices pair one by one.

    :param int length: the length to split
    :param int parts: the number of parts
    :raises InvalidSequenceSplitException: if the result of split produces too few points
    :returns iterable: the generator object
    """
    # Check if the split would produce meaningful values
    if length / parts < 2.0:
        raise exceptions.InvalidSequenceSplitException(parts, length / parts)

    # Get the quotient and remainder
    quot, rem = divmod(length, parts)
    for i in range(parts):
        # Compute the start and end index
        start, end = i * quot + min(i, rem), (i + 1) * quot + min(i + 1, rem)
        yield start, end


def shuffle_points(x_pts, y_pts):
    """Shuffles the x and y coordinates sequence to produce random points sequence.

    :param list x_pts: the x coordinates list
    :param list y_pts: the y coordinates list
    :raises InvalidPointsException: if the points count is too low or their coordinates list have
        different lengths
    :returns tuple: (x: the randomized x sequence, y: the randomized y sequence)
    """
    # Build one list to ensure the coordinates are paired after the shuffle
    check_points(len(x_pts), len(y_pts), MIN_POINTS_COUNT)
    points = list(zip(x_pts, y_pts))
    shuffle(points)
    x_pts, y_pts = zip(*points)
    return x_pts, y_pts


def sort_points(x_pts, y_pts):
    """Sorts the x and y_pts coordinates sequence by x values in the ascending order.

    :param list x_pts: the x coordinates list
    :param list y_pts: the y_pts coordinates list
    :raises InvalidPointsException: if the points count is too low or their coordinates list have
        different lengths
    :returns tuple: (x: the sorted x sequence, y_pts: the sorted y_pts sequence)
    """
    # Build one list to ensure the coordinates are paired after the sorting
    check_points(len(x_pts), len(y_pts), MIN_POINTS_COUNT)
    points = list(zip(x_pts, y_pts))
    points.sort(key=itemgetter(0))
    x_pts, y_pts = zip(*points)
    return x_pts, y_pts


def split_model_interval(start, end, steps):
    """ Splits the interval defined by it's edges to #steps points in a safe manner, i.e. no zero
        points in the array, which prevents zero division errors.

    :param int or float start: the start of interval
    :param int or float end: the end of interval
    :param int steps: number of points to split the interval into
    :returns ndarray: the numpy array containing points
    """
    # Slice the interval to points
    x_pts = np.linspace(start, end, steps)
    # Replace all zeros by zero approximation to prevent zero division errors
    # Result of linspace is array, not tuple, with these arguments
    x_pts[np.abs(x_pts) < APPROX_ZERO] = APPROX_ZERO
    return x_pts


def safe_division(dividend, divisor):
    """Safe division of divident by operand

    :param number dividend: upper operand of the division
    :param number divisor: lower operand of the division, may be zero
    :return: safe value after division of approximated zero
    """
    try:
        return dividend / divisor
    except (ZeroDivisionError, ValueError):
        return dividend / APPROX_ZERO


def as_plot_x_dict(plot_x):
    """Returns the argument as dictionary with given key

    :param object plot_x: object that contains plot_x data
    :return: dictionary with key 'plot_x' set to plot_x
    """
    return dict(plot_x=plot_x)


def as_plot_y_dict(plot_y):
    """Returns the argument as dictionary with given key

    :param object plot_y: object that contains plot_y data
    :return: dictionary with key 'plot_y' set to plot_y
    """
    return dict(plot_y=plot_y)


def add_models_to_profile(profile, models):
    """
    Add newly generated models from analysis by postprocessor to relevant profile.

    :param Profile profile: profile to add the analysis
    :param list models: analysis executed by the individual postprocessor
    :return: method has no return value
    """
    # Store the results into the original profile
    if 'models' not in profile.keys():
        profile['models'] = models
    else:
        profile['models'].extend(models)
    return profile
