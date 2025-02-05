"""Regression tools module. Contains utility functions used by the other regression modules."""

from __future__ import annotations

# Standard Imports
from operator import itemgetter
from typing import Any, Iterable, TYPE_CHECKING
import random

# Third-Party Imports
import numpy as np

# Perun Imports
from perun.utils import exceptions

if TYPE_CHECKING:
    import numpy.typing as npt
    import perun.profile.factory as profiles


# Minimum points count to perform the regression
MIN_POINTS_COUNT: int = 3
# R^2 value if computation failed
R_SQUARE_DEFAULT: float = 0.0
# Zero approximation to avoid zero division etc.
APPROX_ZERO: float = 0.000001


def validate_dictionary_keys(
    dictionary: dict[str, Any], required_keys: list[str], forbidden_keys: list[str]
) -> None:
    """Checks the dictionary for missing required keys and excess forbidden keys.

    :param dictionary: validated dictionary
    :param required_keys: keys that must be present in the inspected dictionary
    :param forbidden_keys: keys that must not be in the inspected dictionary
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


def check_points(x_len: int, y_len: int, threshold: int) -> None:
    """Checks the regression points for possible problems

    :param x_len: the count of x coordinates
    :param y_len: the count of y coordinates
    :param threshold: the minimum number of points
    :raises InvalidPointsException: if the points count is too low or their coordinates list have
        different lengths
    """
    if x_len < threshold or y_len < threshold or x_len != y_len:
        raise exceptions.InvalidPointsException(x_len, y_len, MIN_POINTS_COUNT)


def split_sequence(length: int, parts: int) -> Iterable[tuple[int, int]]:
    """Generator. Splits the given (collection) length into roughly equal parts and yields the part
       start and end indices pair one by one.

    :param length: the length to split
    :param parts: the number of parts
    :raises InvalidSequenceSplitException: if the result of split produces too few points
    :return: the generator object
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


def shuffle_points(x_pts: list[float], y_pts: list[float]) -> tuple[list[float], list[float]]:
    """Shuffles the x and y coordinates sequence to produce random points sequence.

    :param x_pts: the x coordinates list
    :param y_pts: the y coordinates list
    :raises InvalidPointsException: if the points count is too low or their coordinates list have
        different lengths
    :return: (x: the randomized x sequence, y: the randomized y sequence)
    """
    # Build one list to ensure the coordinates are paired after the shuffle
    check_points(len(x_pts), len(y_pts), MIN_POINTS_COUNT)
    points = list(zip(x_pts, y_pts))
    random.shuffle(points)
    res_x_pts, res_y_pts = zip(*points)
    return list(res_x_pts), list(res_y_pts)


def sort_points(x_pts: list[float], y_pts: list[float]) -> tuple[list[float], list[float]]:
    """Sorts the x and y_pts coordinates sequence by x values in the ascending order.

    :param x_pts: the x coordinates list
    :param y_pts: the y_pts coordinates list
    :raises InvalidPointsException: if the points count is too low or their coordinates list have
        different lengths
    :return: (x: the sorted x sequence, y_pts: the sorted y_pts sequence)
    """
    # Build one list to ensure the coordinates are paired after the sorting
    check_points(len(x_pts), len(y_pts), MIN_POINTS_COUNT)
    points = list(zip(x_pts, y_pts))
    points.sort(key=itemgetter(0))
    res_x_pts, res_y_pts = zip(*points)
    return list(res_x_pts), list(res_y_pts)


def split_model_interval(start: int, end: int, steps: int) -> npt.NDArray[np.floating[Any]]:
    """Splits the interval defined by its edges to #steps points in a safe manner, i.e. no zero
        points in the array, which prevents zero division errors.

    :param start: the start of interval
    :param end: the end of interval
    :param steps: number of points to split the interval into
    :return: the numpy array containing points
    """
    # Slice the interval to points
    x_pts = np.linspace(start, end, steps)
    # Replace all zeros by zero approximation to prevent zero division errors
    # Result of linspace is array, not tuple, with these arguments
    x_pts[np.abs(x_pts) < APPROX_ZERO] = APPROX_ZERO
    return x_pts


def as_plot_x_dict(plot_x: Any) -> dict[str, Any]:
    """Returns the argument as dictionary with given key

    :param plot_x: object that contains plot_x data
    :return: dictionary with key 'plot_x' set to plot_x
    """
    return dict(plot_x=plot_x)


def as_plot_y_dict(plot_y: Any) -> dict[str, Any]:
    """Returns the argument as dictionary with given key

    :param plot_y: object that contains plot_y data
    :return: dictionary with key 'plot_y' set to plot_y
    """
    return {"plot_y": plot_y}


def add_models_to_profile(
    profile: profiles.Profile, models: list[dict[str, Any]]
) -> profiles.Profile:
    """
    Add newly generated models from analysis by postprocessor to relevant profile.

    :param profile: profile to add the results to
    :param models: analysis executed by the individual postprocessor
    """
    # Store the results into the original profile
    if "models" not in profile.keys():
        profile["models"] = models
    else:
        profile["models"].extend(models)
    return profile
