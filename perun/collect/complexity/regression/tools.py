""" Module for various utility structures and functions used by the whole regression analyzer """

import collections
import sys
from operator import itemgetter

# Stores the general data about particular regression model
RegressionData = collections.namedtuple('RegressionData', [
    'points',       # the points used to construct the regression model as a list of pairs (x, y)
    'x_max',        # maximal x value in points
    'x_min',        # minimal x value in points
    'y_max',        # maximal y value in points
    'y_min',        # minimal y value in points
    'chunks'        # independent parts of the model, each one could have own best fitting regression model
])


def new_regression_data(points=None, x_max=0, x_min=0, y_max=0, y_min=0, chunks=None):
    """ Constructs new RegressionData namedtuple with default values

    Arguments:
        points(list): the points used to construct the regression model, list of pairs (x, y)
        x_max(float): maximal x value in points
        x_min(float): minimal x value in points
        y_max(float): maximal y value in points
        y_min(float): minimal y value in points
        chunks(list): independent parts of the model, each one could have own best fitting regression model

    Returns:
        namedtuple: the created RegressionData namedtuple
    """
    if chunks is None:
        chunks = []
    return RegressionData(points=points, x_max=x_max, x_min=x_min, y_max=y_max, y_min=y_min, chunks=chunks)


def process_profile_data(points):
    """ Creates corresponding RegressionData namedtuple to the acquired profiling data

    Arguments:
        points(list): the profiling data as a list of pairs (x, y)

    Returns:
        namedtuple: RegressionData corresponding to the given points
    """
    # Store the points as tuple list and sort them by the x value
    points = sorted(points, key=itemgetter(0))
    # Get the points edge values and build the regression data tuple
    return new_regression_data(points, points[-1][0], points[0][0], max(points, key=itemgetter(1))[1],
                               min(points, key=itemgetter(1))[1])


def split_to_chunks(points, parts=1):
    """ Splits the given points into approximately same-sized parts

    Arguments:
        points(list): input data as points in form of tuple list (x, y), sorted in ascending order
        parts(int): parts count

    Returns:
        generator: each subsequent call of the returned generator yields next points part
    """
    # Unable to split the points more, create generator that returns the whole points list
    if len(points) <= 2:
        return (points for _ in range(1))

    # Convert to positive int
    parts = int(abs(parts))
    # Fit the number of parts between <1, points_count / 2>
    if parts < 1:
        parts = 1
    if parts > (len(points) / 2):
        print('Warning: too many regression parts, reducing to minimum.', file=sys.stderr)
        parts = int(len(points) / 2)

    # Produce the lists of points
    quot, rem = divmod(len(points), parts)
    return (points[i * quot + min(i, rem):(i + 1) * quot + min(i + 1, rem)] for i in range(parts))
