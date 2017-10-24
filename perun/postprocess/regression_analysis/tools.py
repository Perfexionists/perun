"""Regression tools module. Contains utility functions used by the other regression modules.

"""

from random import shuffle
from operator import itemgetter
import numpy as np

import perun.utils.exceptions as exceptions


# Minimum points count to perform the regression
MIN_POINTS_COUNT = 3
# R^2 value if computation failed
R_SQUARE_DEFAULT = 0.0
# Zero approximation to avoid zero division etc.
APPROX_ZERO = 0.000001


def validate_dictionary_keys(dictionary, required_keys, forbidden_keys):
    """Checks the dictionary for missing required keys and excess forbidden keys.

    Arguments:
        dictionary(dict): the inspected dictionary
        required_keys(list of str): keys that must be present in the inspected dictionary
        forbidden_keys(list of str): keys that must not be in the inspected dictionary
    Raises:
        DictionaryKeysValidationFailed: if the dictionary inspection fails
    Returns:
        None

    """
    missing_keys, excess_keys = [], []

    # Check the dictionary first
    if not isinstance(dictionary, dict):
        raise exceptions.DictionaryKeysValidationFailed(dictionary, [], [])
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

    Arguments:
        x_len(int): the count of x coordinates
        y_len(int): the count of y coordinates
        threshold(int): the minimum number of points
    Raises:
        InvalidPointsException: if the points count is too low or their coordinates list have
                                different lengths
    Returns:
        None
    """
    if x_len < threshold or y_len < threshold or x_len != y_len:
        raise exceptions.InvalidPointsException(x_len, y_len, MIN_POINTS_COUNT)


def check_coeffs(coeffs_count, collection):
    """Checks the coefficients count in the collection.

    Arguments:
        coeffs_count(int): the expected count of coefficients
        collection(dict): the dictionary with coefficients member 'coeffs'
    Raises:
        InvalidCoeffsException: if the expected coefficients count does not match the actual
    """
    if 'coeffs' not in collection or len(collection['coeffs']) != coeffs_count:
        exceptions.InvalidCoeffsException(coeffs_count)


def split_sequence(length, parts):
    """Generator. Splits the given (collection) length into roughly equal parts and yields the part
       start and end indices pair one by one.

    Arguments:
        length(int): the length to split
        parts(int): the number of parts
    Raises:
        InvalidSequenceSplitException: if the result of split produces too few points
    Returns:
        iterable: the generator object
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

    Arguments:
        x_pts(list): the x coordinates list
        y_pts(list): the y coordinates list
    Raises:
        InvalidPointsException: if the points count is too low or their coordinates list have
                                different lengths
    Returns:
        tuple:  x: the randomized x sequence
                y: the randomized y sequence
    """
    # Build one list to ensure the coordinates are paired after the shuffle
    check_points(len(x_pts), len(y_pts), MIN_POINTS_COUNT)
    points = list(zip(x_pts, y_pts))
    shuffle(points)
    x_pts, y_pts = zip(*points)
    return x_pts, y_pts


def sort_points(x_pts, y_pts):
    """Sorts the x and y_pts coordinates sequence by x values in the ascending order.

    Arguments:
        x_pts(list): the x coordinates list
        y_pts(list): the y_pts coordinates list
    Raises:
        InvalidPointsException: if the points count is too low or their coordinates list have
                                different lengths
    Returns:
        tuple:  x: the sorted x sequence
                y_pts: the sorted y_pts sequence
    """
    # Build one list to ensure the coordinates are paired after the sorting
    check_points(len(x_pts), len(y_pts), MIN_POINTS_COUNT)
    points = list(zip(x_pts, y_pts))
    points.sort(key=itemgetter(0))
    x_pts, y_pts = zip(*points)
    return x_pts, y_pts


def zip_points(x_pts, y_pts, len_start=0, len_end=-1):
    """Creates points pair (x, y) useful for iteration.

    Arguments:
        x_pts(list): list of x points
        y_pts(list): list of y points
        len_start(int): slicing start value
        len_end(int): slicing end value
    Returns:
        iterable: zip iterator object

    """
    return zip(x_pts[len_start:len_end], y_pts[len_start:len_end])


def split_model_interval(start, end, steps):
    """ Splits the interval defined by it's edges to #steps points in a safe manner, i.e. no zero
        points in the array, which prevents zero division errors.

    Arguments:
        start(int or float): the start of interval
        end(int or float): the end of interval
        steps(int): number of points to split the interval into

    Returns:
        ndarray: the numpy array containing points
    """
    # Slice the interval to points
    x_pts = np.linspace(start, end, steps)
    # Replace all zeros by zero approximation to prevent zero division errors
    # Result of linspace is array, not tuple, with these arguments
    x_pts[np.abs(x_pts) < APPROX_ZERO] = APPROX_ZERO
    return x_pts
