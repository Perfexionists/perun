"""Regression tools module. Contains utility functions used by the other regression modules.

"""


import perun.utils.exceptions as exceptions
from random import shuffle
from operator import itemgetter

# Minimum points count to perform the regression
MIN_POINTS_COUNT = 3


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
    if type(dictionary) is not dict:
        raise exceptions.DictionaryKeysValidationFailed(dictionary, [], [])
    # Check all the required keys
    for key in required_keys:
        if key not in dictionary:
            missing_keys += key
    # Check all the forbidden keys
    for key in forbidden_keys:
        if key in dictionary:
            excess_keys += key

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
        InvalidPointsException: if the points count is too low or their coordinates list have different lengths
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
        raise exceptions.InvalidSequenceSplitException(length / parts)

    # Get the quotient and remainder
    quot, rem = divmod(length, parts)
    for i in range(parts):
        # Compute the start and end index
        start, end = i * quot + min(i, rem), (i + 1) * quot + min(i + 1, rem)
        yield start, end


def shuffle_points(x, y):
    """Shuffles the x and y coordinates sequence to produce random points sequence.

    Arguments:
        x(list): the x coordinates list
        y(list): the y coordinates list
    Raises:
        InvalidPointsException: if the points count is too low or their coordinates list have different lengths
    Returns:
        tuple:  x: the randomized x sequence
                y: the randomized y sequence
    """
    # Build one list to ensure the coordinates are paired after the shuffle
    check_points(len(x), len(y), MIN_POINTS_COUNT)
    points = list(zip(x, y))
    shuffle(points)
    x, y = zip(*points)
    return x, y


def sort_points(x, y):
    """Sorts the x and y coordinates sequence by x values in the ascending order.

    Arguments:
        x(list): the x coordinates list
        y(list): the y coordinates list
    Raises:
        InvalidPointsException: if the points count is too low or their coordinates list have different lengths
    Returns:
        tuple:  x: the sorted x sequence
                y: the sorted y sequence
    """
    # Build one list to ensure the coordinates are paired after the sorting
    check_points(len(x), len(y), MIN_POINTS_COUNT)
    points = list(zip(x, y))
    points.sort(key=itemgetter(0))
    x, y = zip(*points)
    return x, y
