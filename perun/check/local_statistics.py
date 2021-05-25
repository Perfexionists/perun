"""
The module contains the methods, that executes the computational logic of
`local_statistics` detection method.
"""

__author__ = 'Simon Stupinsky'

import numpy as np
import scipy.integrate as integrate

from typing import Dict, Tuple, List, Any, Iterable

import perun.check.factory as factory
import perun.check.nonparam_helpers as nparam_helpers
import perun.postprocess.regression_analysis.tools as tools

from perun.profile.factory import Profile
from perun.utils.structs import DegradationInfo, ModelRecord

# minimum count of points in the interval in which are computed statistics
_MIN_POINTS_IN_INTERVAL = 2
# density of dividing the whole interval into individual sub-intervals
# - the value 0.1 represents 10% points (from the summary count) in the sub-interval
_INTERVAL_DENSITY = 0.05
# acceptable percentage portion from the count of statistics they may change to detect NO_CHANGE
_STATS_FOR_NO_CHANGE = 0.2
# needed percentage portion from the count of statistics to detect CHANGE
# - the difference between these two values represents the state of uncertain changes - MAYBE
_STATS_FOR_CHANGE = 0.5
# the acceptable value of relative error computed from individual
# statistics between compared profiles to detect NO_CHANGE state
_STATS_DIFF_NO_CHANGE = .10
# an upper limit of relative error to detect changes between compared profiles
# - the difference between these two values represents the state of uncertain changes - MAYBE
_STATS_DIFF_CHANGE = .25


def compute_window_stats(
        x_pts: List[float], y_pts: List[float]
) -> Tuple[Dict[str, np.ndarray], np.ndarray]:
    """
    The method computes the local statistics from the given points.

    A method performs all needed logic to compute local statistics on the
    individual sub-intervals. A method divides given points into relevant sub-intervals
    according to a summary count of points and other requirements (such as minimal
    count of points in sub-interval). Subsequently, it computes the individual
    statistical metrics (mean, median, min, max, etc.) from the whole set of
    sub-intervals. A method returns the dictionary contains the computed statistical
    metrics and array which includes the edges of sub-intervals.

    :param list x_pts: array with values of x-coordinates
    :param list y_pts: array with values of y-coordinates
    :return tuple: (dictionary with computed statistics, edges of individual sub-intervals)
    """
    def reshape_array(array: np.ndarray) -> np.ndarray:
        """
        The method reshapes the given array into several
        smaller arrays according to the given count.

        :param np.ndarray array: array with points to reshape
        :return np.ndarray: the reshaped array according to the given options
        """
        # check whether the array contains the sufficient number of points to reshape
        if array.size % n:
            # adding the NaN (empty) values needed for reshaping the array
            array = np.concatenate((array, np.full(n - (array.size % n), np.nan)))
        return array.reshape(-1, n)

    # calculating the count of the points within the sub-intervals
    n = int(_INTERVAL_DENSITY * min(len(y_pts), len(x_pts)))
    # list -> np.ndarray
    x_array = np.asarray(x_pts)
    y_array = np.asarray(y_pts)
    # save the maximum value from x-coordinates (end of the interval)
    max_x = np.max(x_array)
    # default axis along which the statistical metrics are computed (matrix 1x1)
    axis = 0
    # check whether the intervals will contain the minimal count of points
    if n >= _MIN_POINTS_IN_INTERVAL:
        # set vertical axes along which the statistical metrics are computed (matrix e.g. 4x4)
        axis = 1
        # reshape both arrays into 'n' smaller arrays on which will be computed statistical metrics
        y_array = reshape_array(y_array)
        x_array = reshape_array(x_array)
        # obtain the first and last point from the sub-intervals - edges of the intervals
        x_edges = np.delete(x_array, range(1, x_array[0].size - 1), 1)
        # replace the right edge of the last sub-interval with the saved maximum of whole interval:
        # - (10, NaN) -> (10, 10)
        x_edges[np.isnan(np.delete(x_array, range(1, x_array[0].size - 1), 1))] = max_x
    # compute the statistical metrics on the whole interval of x-coordinates
    else:
        # obtain the edges of the whole interval
        x_edges = np.delete(x_array, range(1, x_array.size - 1)).reshape(1, -1)

    # compute the all statistical metrics on the specified intervals
    return {
        # integral
        'int': np.atleast_1d(integrate.simps(y_array, x_array, axis=axis)),
        # average/mean
        'avg': np.atleast_1d(np.nanmean(y_array, axis=axis)),
        # median/2.percentile
        'med': np.atleast_1d(np.nanmedian(y_array, axis=axis)),
        # maximum
        'max': np.atleast_1d(np.nanmax(y_array, axis=axis)),
        # minimum
        'min': np.atleast_1d(np.nanmin(y_array, axis=axis)),
        # summary value
        'sum': np.atleast_1d(np.nansum(y_array, axis=axis)),
        # 1.percentile
        'per_q1': np.atleast_1d(np.nanpercentile(y_array, 25, axis=axis)),
        # 3.percentile
        'per_q2': np.atleast_1d(np.nanpercentile(y_array, 75, axis=axis)),
    }, x_edges


def classify_stats_diff(
        baseline_stats: Dict[str, np.ndarray], target_stats: Dict[str, np.ndarray]
) -> Tuple[np.ndarray, np.ndarray]:
    """
    The method performs the classification of computed statistical metrics.

    A method analyses the computed statistical metrics in the given lists. Between
    the pair of metrics is computed the relative error and subsequently according to
    its value is determined the change state. The resulting change on the individual
    sub-interval is determined by the final score of change, that is computed during
    the iteration over all metrics. Finally, a method determines the change states
    and computes the average relative error.

    :param dict baseline_stats: contains the metrics on relevant sub-intervals from baseline model
    :param dict target_stats: contains the metrics on relevant sub-intervals from target model
    :return tuple: (change states on individual sub-intervals, average relative error)
    """
    # create vectorized functions which take a np.arrays as inputs and perform actions over it
    compare_diffs = np.vectorize(compare_diff_values)
    classify_change = np.vectorize(nparam_helpers.classify_change)
    stat_no = len(baseline_stats.keys())
    stat_size = baseline_stats.get(list(baseline_stats.keys())[0])

    # initialize np.arrays about the size of sub-intervals from given stats
    change_score = np.full_like(stat_size, 0)
    rel_error = np.full_like(stat_size, 0)
    # iteration over each metric in the given stats
    for baseline_stat_key, baseline_stat_value in baseline_stats.items():
        # compute difference between the metrics from both models
        diff_values = np.subtract(target_stats[baseline_stat_key], baseline_stat_value)
        # compute the relative error of current processed metric
        new_rel_error = np.nan_to_num(np.true_divide(
            diff_values, baseline_stat_value, out=np.zeros_like(diff_values),
            where=baseline_stat_value != 0
        ))
        # compute the sum of the partial relative errors computed from the individual metrics
        rel_error = np.add(rel_error, new_rel_error)
        # update the change_score according to the value of current computed relative error
        change_score = compare_diffs(change_score, new_rel_error)

    change_states = classify_change(
        change_score, _STATS_FOR_NO_CHANGE, _STATS_FOR_CHANGE, stat_no
    )
    return np.atleast_1d(change_states), np.atleast_1d(np.divide(rel_error, stat_no))


def compare_diff_values(change_score: float, rel_error: float) -> float:
    """
    The method updates change score according to the value of relative error.

    A method compare the current value of relative error with a predetermined
    thresholds and determines the new value of change score. The possible change
    states change this score as follows:

        * if REL_ERROR > 0 then change_state=1
        ** else REL_ERROR <= 0 then change_state=-1

        | -> if REL_ERROR <= NO_CHANGE_THRESHOLD then change_score=change_score
        || -> elif REL_ERROR <= CHANGE_THRESHOLD then change_score=change_score+(0.5*change_state)
        ||| -> else REL_ERROR > CHANGE_THRESHOLD then change_state=change_score+(1.0*change_state)

    :param np.ndarray change_score: array contains the values of relative error for sub-intervals
    :param float rel_error: current value of relative error
    :return np.ndarray: update array with new values of change score
    """
    if abs(rel_error) <= _STATS_DIFF_NO_CHANGE:
        change_score += 0
    elif abs(rel_error) <= _STATS_DIFF_CHANGE:
        change_score += -.5 if rel_error < 0 else .5
    else:
        change_score += -1 if rel_error < 0 else 1

    return change_score


def execute_analysis(
        uid: str,
        baseline_model: ModelRecord,
        target_model: ModelRecord,
        target_profile: Profile,
        **_: Any
) -> Dict[str, Any]:
    """
    A method performs the primary analysis for pair of models.

    The method executes the analysis between the pair of models. In the beginning, the method checks
    the length of both models. Subsequently, it computes the individual statistics from both given
    models. From these results are computed the relative error on the individual sub-intervals,
    which values then determine the resulting change. The method returns the information about
    detected changes on all analysed sub-intervals commonly with the overall change between
    compared models.

    :param str uid: unique identification of both analysed models
    :param dict baseline_model: baseline model with all its parameters for comparison
    :param dict target_model: target model with all its parameters for comparison
    :param Profile target_profile: target model for the comparison
    :param dict kwargs: dictionary with baseline and target profiles
    :return:
    """
    original_x_pts, baseline_y_pts, target_y_pts = nparam_helpers.preprocess_nonparam_models(
        uid, baseline_model, target_profile, target_model
    )

    baseline_stats, _ = compute_window_stats(original_x_pts, baseline_y_pts)
    target_stats, x_pts = compute_window_stats(original_x_pts, target_y_pts)
    change_info, partial_rel_error = classify_stats_diff(baseline_stats, target_stats)

    x_pts = np.append(x_pts, [x_pts[0]], axis=1) if x_pts.size == 1 else x_pts
    x_pts_even = x_pts[:, 0::2].reshape(-1, x_pts.size // 2)[0].round(2)
    x_pts_odd = x_pts[:, 1::2].reshape(-1, x_pts.size // 2)[0].round(2)
    partial_intervals = np.array((change_info, partial_rel_error, x_pts_even, x_pts_odd)).T

    change_info = nparam_helpers.classify_change(
        tools.safe_division(np.sum(partial_rel_error), partial_rel_error.size),
        _STATS_DIFF_NO_CHANGE, _STATS_DIFF_CHANGE
    )

    return {
        'change_info': change_info,
        'rel_error': round(
            tools.safe_division(np.sum(partial_rel_error), partial_rel_error.size), 2
        ),
        'partial_intervals': partial_intervals
    }


def local_statistics(
        baseline_profile: Profile, target_profile: Profile, models_strategy: str = 'best-model'
) -> Iterable[DegradationInfo]:
    """
    The wrapper of `local_statistics` detection method. Method calls the general method
    for running the detection between pairs of profile (baseline and target) and subsequently
    returns the information about detected changes.

    :param Profile baseline_profile: base against which we are checking the degradation
    :param Profile target_profile: profile corresponding to the checked minor version
    :param str models_strategy: detection model strategy for obtains the relevant kind of models
    :returns: tuple - degradation result
    """
    for degradation_info in factory.run_detection_with_strategy(
            execute_analysis, baseline_profile, target_profile, models_strategy
    ):
        yield degradation_info
