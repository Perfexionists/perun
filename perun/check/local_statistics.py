"""
The module contains the methods, that executes the computational logic of
`local_statistics` detection method.
"""

__author__ = 'Simon Stupinsky'

import numpy as np
import scipy.integrate as integrate

import perun.check.factory as factory
import perun.check.general_detection as methods
import perun.check.integral_comparison as check_helpers
import perun.postprocess.regression_analysis.data_provider as data_provider
import perun.postprocess.regression_analysis.tools as tools
import perun.postprocess.regressogram.methods as rg_methods
import perun.utils.log as log


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


def compute_window_stats(x_pts, y_pts):
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
    def reshape_array(array):
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
    x_pts = np.asarray(x_pts)
    y_pts = np.asarray(y_pts)
    # save the maximum value from x-coordinates (end of the interval)
    max_x = np.max(x_pts)
    # default axis along which the statistical metrics are computed (matrix 1x1)
    axis = 0
    # check whether the intervals will contain the minimal count of points
    if n >= _MIN_POINTS_IN_INTERVAL:
        # set vertical axes along which the statistical metrics are computed (matrix e.g. 4x4)
        axis = 1
        # reshape both arrays into 'n' smaller arrays on which will be computed statistical metrics
        y_pts = reshape_array(y_pts)
        x_pts = reshape_array(x_pts)
        # obtain the first and last point from the sub-intervals - edges of the intervals
        x_edges = np.delete(x_pts, range(1, x_pts[0].size - 1), 1)
        # replace the right edge of the last sub-interval with the saved maximum of whole interval:
        # - (10, NaN) -> (10, 10)
        x_edges[np.isnan(np.delete(x_pts, range(1, x_pts[0].size - 1), 1))] = max_x
    # compute the statistical metrics on the whole interval of x-coordinates
    else:
        # obtain the edges of the whole interval
        x_edges = np.delete(x_pts, range(1, x_pts.size - 1)).reshape(1, -1)

    # compute the all statistical metrics on the specified intervals
    return {
        # integral
        'int': np.atleast_1d(integrate.simps(y_pts, x_pts, axis=axis)),
        # average/mean
        'avg': np.atleast_1d(np.nanmean(y_pts, axis=axis)),
        # median/2.percentile
        'med': np.atleast_1d(np.nanmedian(y_pts, axis=axis)),
        # maximum
        'max': np.atleast_1d(np.nanmax(y_pts, axis=axis)),
        # minimum
        'min': np.atleast_1d(np.nanmin(y_pts, axis=axis)),
        # summary value
        'sum': np.atleast_1d(np.nansum(y_pts, axis=axis)),
        # 1.percentile
        'per_q1': np.atleast_1d(np.nanpercentile(y_pts, 25, axis=axis)),
        # 3.percentile
        'per_q2': np.atleast_1d(np.nanpercentile(y_pts, 75, axis=axis)),
    }, x_edges


def classify_stats_diff(base_stats, targ_stats):
    """
    The method performs the classification of computed statistical metrics.

    A method analyses the computed statistical metrics in the given lists. Between
    the pair of metrics is computed the relative error and subsequently according to
    its value is determined the change state. The resulting change on the individual
    sub-interval is determined by the final score of change, that is computed during
    the iteration over all metrics. Finally, a method determines the change states
    and computes the average relative error.

    :param dict base_stats: contains the metrics on relevant sub-intervals from baseline model
    :param dict targ_stats: contains the metrics on relevant sub-intervals from target model
    :return tuple: (change states on individual sub-intervals, average relative error)
    """
    # create vectorized functions which take a np.arrays as inputs and perform actions over it
    compare_diffs = np.vectorize(compare_diff_values)
    classify_change = np.vectorize(check_helpers.classify_change)
    # initialize np.arrays about the size of sub-intervals from given stats
    change_score = np.full_like(base_stats.get(list(base_stats.keys())[0]), 0)
    rel_error = np.full_like(base_stats.get(list(targ_stats.keys())[0]), 0)
    # iteration over each metric in the given stats
    for base_stat in base_stats.items():
        # compute difference between the metrics from both models
        diff_values = np.subtract(targ_stats[base_stat[0]], base_stat[1])
        # compute the relative error of current processed metric
        new_rel_error = np.nan_to_num(
            np.true_divide(diff_values, base_stat[1], where=base_stat[1] != 0)
        )
        # compute the sum of the partial relative errors computed from the individual metrics
        rel_error = np.add(rel_error, new_rel_error)
        # update the change_score according to the value of current computed relative error
        change_score = compare_diffs(change_score, new_rel_error)

    change_states = classify_change(
        change_score, _STATS_FOR_NO_CHANGE, _STATS_FOR_CHANGE, len(base_stats.keys())
    )
    return np.atleast_1d(change_states), \
        np.atleast_1d(np.divide(rel_error, len(base_stats.keys())))


def compare_diff_values(change_score, rel_error):
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


def unify_regressogram(base_model, targ_model, targ_profile):
    """
    The method unifies the regressograms into the same count of buckets.

    A method unifies the target regressogram model with the regressogram model
    from the baseline profile. It set the options for new post-processing of
    target model according to the options at baseline model and then call the
    method to compute the new regressogram models. This method returns the new
    regressogram model, which has the same 'uid' as the given models.

    :param dict base_model: baseline regressogram model with all its parameters
    :param dict targ_model: target regressogram model with all its parameters
    :param Profile targ_profile: target profile corresponding to the checked minor version
    :return dict: new regressogram model with the required 'uid'
    """
    log.cprint('Target regressogram model will be post-processed again.\n', 'yellow')
    # set needed parameters for regressogram post-processors
    mapper_keys = {
        'per_key': targ_model['resource_keys'][0],
        'of_key': targ_model['resource_keys'][1]
    }
    config = {
        'statistic_function': targ_model['statistic_function'],
        'bucket_number': len(base_model['bucket_stats']),
        'bucket_method': None,
    }
    config.update(mapper_keys)
    # compute new regressogram models with the new parameters needed to unification
    new_regressogram_models = rg_methods.compute_regressogram(
        data_provider.data_provider_mapper(targ_profile, **mapper_keys), config
    )

    # match the regressogram model with the right 'uid'
    return [model for model in new_regressogram_models if model['uid'] == targ_model['uid']][0]


def execute_analysis(base_model, targ_model, param=False, **kwargs):
    """
    A method performs the primary analysis for pair of models.

    The method executes the analysis between the pair of models. In the beginning, the method checks
    the length of both models. Subsequently, it computes the individual statistics from both given
    models. From these results are computed the relative error on the individual sub-intervals,
    which values then determine the resulting change. The method returns the information about
    detected changes on all analysed sub-intervals commonly with the overall change between
    compared models.

    :param dict base_model: baseline model with all its parameters for comparison
    :param dict targ_model: target model with all its parameters for comparison
    :param bool param: flag to resolution parametric and non-parametric models
    :param dict kwargs: baseline and target profiles
    :return:
    """
    x_pts, base_y_pts, targ_y_pts = process_models(
        base_model, kwargs.get('targ_profile'), targ_model, param
    )

    base_stats, _ = compute_window_stats(x_pts, base_y_pts)
    targ_stats, x_pts = compute_window_stats(x_pts, targ_y_pts)
    change_info, partial_rel_error = classify_stats_diff(base_stats, targ_stats)

    x_pts = np.append(x_pts, [x_pts[0]], axis=1) if x_pts.size == 1 else x_pts
    x_pts_even = x_pts[:, 0::2].reshape(-1, x_pts.size // 2)[0]
    x_pts_odd = x_pts[:, 1::2].reshape(-1, x_pts.size // 2)[0]
    partial_intervals = np.array((change_info, partial_rel_error, x_pts_even, x_pts_odd)).T

    change_info = check_helpers.classify_change(
        tools.safe_division(np.sum(partial_rel_error), partial_rel_error.size),
        _STATS_DIFF_NO_CHANGE, _STATS_DIFF_CHANGE
    )

    return {
        'change_info': change_info,
        'rel_error': str(
            '{0:.2f}'.format(
                tools.safe_division(np.sum(partial_rel_error), partial_rel_error.size)) + 'x'
        ),
        'partial_intervals': partial_intervals
    }


def process_models(base_model, targ_profile, targ_model, param):
    """
    Method prepare models to execute the computation of statistics between them.

    This method in the case of parametric model obtains their functional values directly
    from coefficients these models. In the case of non-parametric models method checks it
    interval length and potentially edit the interval to the same length. In the case of
    regressogram model method unifies two regressogram models according to the length of
    the shorter interval. The method returns the values of both model (baseline and target)
    and the common interval on which are defined these models.

    :param dict/BestModelRecord base_model:  baseline model with all its parameters for processing
    :param Profile targ_profile: target profile against which contains the given target model
    :param dict/BestModelRecord targ_model: target model with all its parameters for processing
    :param bool param: the flag for resolution the parametric and non-parametric models
    :return: tuple with values of both models and their relevant x-interval
    """
    if param:
        x_pts, base_y_pts = methods.get_function_values(base_model)
        _, targ_y_pts = methods.get_function_values(targ_model)
    else:
        base_model, targ_model = check_nparam_models(base_model, targ_model)
        y_pts_len = len(base_model['bucket_stats'])
        x_pts = np.linspace(base_model['x_start'], base_model['x_end'], num=y_pts_len)
        if base_model['method'] == 'regressogram' and\
                len(base_model['bucket_stats']) != len(targ_model['bucket_stats']):
            targ_model = unify_regressogram(base_model, targ_model, targ_profile)
        base_y_pts = base_model['bucket_stats']
        targ_y_pts = targ_model['bucket_stats']

    return x_pts, base_y_pts, targ_y_pts


def check_nparam_models(base_model, targ_model):
    """
    The method check the length of the model values.

    A method compares the length of the model values. If the lengths are not
    equal, then the analysis will not execute and the warning will print for
    the user. When the lengths are not equal at regressogram model, then a
    warning is printed and the target model will unify with the baseline model
    in the next steps.

    :param dict base_model: baseline model with all its parameters
    :param dict targ_model: target model with all its parameters
    :return bool: True if the length are equal, else False (exception at regressogram models)
    """
    base_len = len(base_model['bucket_stats'])
    targ_len = len(targ_model['bucket_stats'])
    if base_len != targ_len:
        log.warn(
            '{0}: {1} models with different length ({2} != {3}) are slicing'
            .format(base_model['uid'], base_model['method'], base_len, targ_len)
        )
        base_model['bucket_stats'] = base_model['bucket_stats'][:min(base_len, targ_len)]
        targ_model['bucket_stats'] = targ_model['bucket_stats'][:min(base_len, targ_len)]
    return base_model, targ_model


def local_statistics(base_profile, targ_profile):
    """
    The wrapper of `local_statistics` detection method. Method calls the general method
    for running the detection between pairs of profile (baseline and target) and subsequently
    returns the information about detected changes.

    :param Profile base_profile: base against which we are checking the degradation
    :param Profile targ_profile: profile corresponding to the checked minor version
    :returns: tuple - degradation result
    """
    for degradation_info in factory.run_detection_for_all_models(
            execute_analysis, base_profile, targ_profile
    ):
        yield degradation_info
