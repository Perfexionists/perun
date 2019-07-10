"""
Module with regressogram computational method and auxiliary methods at executing of this method.
"""
import numpy as np
import numpy.lib.function_base as numpy_bucket_selectors
import scipy.stats
import sklearn.metrics

import perun.postprocess.regression_analysis.tools as tools

# required arguments at regressogram post-processor
_REQUIRED_KEYS = ['bucket_method', 'statistic_function']


def get_supported_methods():
    """Provides all currently supported computational methods, to
    estimate the optimal number of buckets, as a list of their names.

    :returns list of str: the names of all supported methods
    """
    return list(_BUCKET_SELECTORS.keys())


def compute_regressogram(data_gen, configuration):
    """
    The regressogram wrapper to execute the analysis on the individual chunks of resources.

    :param iter data_gen: the generator object with collected data (data provider generators)
    :param dict configuration: the perun and option context
    :return: list of dict: the computation results
    """
    # checking the presence of specific keys in individual methods
    tools.validate_dictionary_keys(configuration, _REQUIRED_KEYS, [])

    # list of result of the analysis
    analysis = []
    for x_pts, y_pts, uid in data_gen:
        # Check whether the user gives as own number of buckets or select the method to its estimate
        buckets = configuration['bucket_number'] if configuration.get('bucket_number') \
            else configuration['bucket_method']
        result = regressogram(x_pts, y_pts, configuration['statistic_function'], buckets)
        result['uid'] = uid
        result['method'] = 'regressogram'
        # add partial result to the result list - create output dictionaries
        analysis.append(result)
    return analysis


def regressogram(x_pts, y_pts, statistic_function, buckets):
    """
    Compute the regressogram (binning approach) of a set of data.

    We can view regressogram it as:
        regressogram = regression + histogram

    Regressogram is a piecewise constant regression function estimator. The x-observation is covered
    by disjoint buckets, and the value of a regressogram in a bucket is the mean/median of y-values
    for the x-values inside that bucket.

    If the 'statistic_function' contains the int, then this number defines the number of buckets.
    If the 'statistic_function' contains the string from the keys of <_BIN_SELECTORS>, then will be
    use the chosen method to calculate the optimal bucket width and consequently the number of
    buckets.

    :param list x_pts: the list of x points coordinates
    :param list y_pts: the list of y points coordinates
    :param str statistic_function: the statistic_function to compute
    :param str/int buckets: the number of buckets to calculate or the name of computational method
    :return dict: the output dictionary with result of analysis
    """
    # Check whether the buckets is given by number or by name of method to its compute
    buckets_num = buckets if isinstance(buckets, int) \
        else _BUCKET_SELECTORS[buckets](np.array(x_pts))
    # Compute a binned statistic for the given data
    bucket_stats, bucket_edges, bucket_numbers = scipy.stats.binned_statistic(
        x_pts, y_pts, statistic_function, max(1, buckets_num)
    )
    # Replace the NaN in empty buckets with 0 for plotting
    bucket_stats = np.nan_to_num(bucket_stats)
    # Create output dictionaries
    return {
        'buckets_method': 'user' if isinstance(buckets, int) else buckets,
        'statistic_function': statistic_function,
        'bucket_stats': bucket_stats.tolist(),
        'x_start': np.min(bucket_edges),
        'x_end': np.max(bucket_edges),
        'y_start': min(y_pts),
        'r_square': sklearn.metrics.r2_score(
            y_pts, [bucket_stats[bucket_number - 1] for bucket_number in bucket_numbers]
        )
    }


def render_step_function(graph, x_pts, y_pts, graph_params):
    """
    Render step lines according to given coordinates and other parameters.

    :param charts.Graph graph: the scatter plot
    :param x_pts: the x-coordinates for the points of the line
    :param y_pts: the y-coordinates for the points of the line
    :param dict graph_params: contains the specification of parameters for graph
        (color, line_width, legend)
    :returns charts.Graph: the modified graph with model of step function
    """
    x_x = np.sort(list(x_pts) + list(x_pts))
    x_x = x_x[:-1]
    y_y = list(y_pts) + list(y_pts)
    y_y[::2] = y_pts
    y_y[1::2] = y_pts
    y_y = y_y[1:]
    graph.line(x_x, y_y, color=graph_params.get('color'), line_width=graph_params.get('line_width'),
               legend=graph_params.get('legend'))
    return graph


# Code for calculating number of buckets for regressogram can be got from SciPy:
# https://docs.scipy.org/doc/numpy/reference/generated/numpy.histogram_bin_edges.html#numpy.histogram_bucket_edges

# supported methods to choose bucket sizes for regressogram
_BUCKET_SELECTORS = {
    'auto': numpy_bucket_selectors._hist_bin_auto,
    'doane': numpy_bucket_selectors._hist_bin_doane,
    'fd': numpy_bucket_selectors._hist_bin_fd,
    'rice': numpy_bucket_selectors._hist_bin_rice,
    'scott': numpy_bucket_selectors._hist_bin_scott,
    'sqrt': numpy_bucket_selectors._hist_bin_sqrt,
    'sturges': numpy_bucket_selectors._hist_bin_sturges,
}
