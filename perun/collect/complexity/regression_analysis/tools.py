"""Regression tools module. Contains utility functions used by the other regression modules.

"""


import regression_analysis.regression_exceptions as reg_except
from random import shuffle
from operator import itemgetter

# Minimum points count to perform the regression
MIN_POINTS_COUNT = 2
# Number of plotting points used by the visualization
PLOT_DATA_POINTS = 51


def check_excess_arg(arg_list, collection):
    """Checks if collection contains certain unexpected arguments

    Arguments:
        arg_list(list): list of arguments that should not be present in a collection
        collection(iterable): any iterable collection that will be checked
    Raises:
        DataFormatExcessArgument: if the collection contains any of the unexpected arguments
    Returns:
        None
    """
    for arg in arg_list:
        if arg in collection:
            raise reg_except.DataFormatExcessArgument(str(arg))


def check_missing_arg(arg_list, collection):
    """Checks if collection is missing required arguments

    Arguments:
        arg_list(list): list of arguments that should be present in a collection
        collection(iterable): any iterable collection that will be checked
    Raises:
        DataFormatMissingArgument: if the collection is missing any of the arguments
    Returns:
        None
    """
    for arg in arg_list:
        if arg not in collection:
            raise reg_except.DataFormatMissingArgument(str(arg))


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
        raise reg_except.InvalidPointsException(x_len, y_len)


def check_coeffs(coeffs_count, collection):
    """Checks the coefficients count in the collection.

    Arguments:
        coeffs_count(int): the expected count of coefficients
        collection(dict): the dictionary with coefficients member 'coeffs'
    Raises:
        DataFormatInvalidCoeffs: if the expected coefficients count does not match the actual
    """
    if 'coeffs' not in collection or len(collection['coeffs']) != coeffs_count:
        reg_except.DataFormatInvalidCoeffs(coeffs_count)


def split_sequence(length, parts):
    """Generator. Splits the given (collection) length into roughly equal parts and yields the part
       start and end indices pair one by one.

    Arguments:
        length(int): the length to split
        parts(int): the number of parts
    Returns:
        iterable: the generator object
    """
    # Check if the split would produce meaningful values
    if length / parts < 2.0:
        raise reg_except.InvalidSequenceSplit(length / parts)

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
