"""
Module with regressogram computational method and auxiliary methods at executing of this method.
"""

import numpy as np
import numpy.lib.function_base as np_bin_selectors
from click import BadParameter
from scipy import stats
from sklearn import metrics

from perun.postprocess.regression_analysis.tools import validate_dictionary_keys

# required arguments at regressogram post-processor
_REQUIRED_KEYS = ['bins', 'statistic']


def compute(data_gen, configuration):
    """
    The regressogram wrapper to execute the analysis on the individual chunks of resources.

    :param iter data_gen: the generator object with collected data (data provider generators)
    :param dict configuration: the perun and option context
    :return: list of dict: the computation results
    """
    # checking the presence of specific keys in individual methods
    validate_dictionary_keys(configuration, _REQUIRED_KEYS, [])

    # list of result of the analysis
    analysis = []
    for chunk in data_gen:
        result = regressogram(chunk[0], chunk[1], configuration['statistic'], configuration['bins'])
        result['uid'] = chunk[2]
        result['method'] = 'regressogram'
        # add partial result to the result list - create output dictionaries
        analysis.append(result)
    return analysis


def regressogram(x_pts, y_pts, statistic, bins):
    """
    Compute the regressogram (binning approach) of a set of data.

    We can view regressogram it as:
        regressogram = regression + histogram

    Regressogram is a piecewise constant regression function estimator. The x-observation
    (independent variable) is covered by disjoint bins, and the value of a regressogram in
    a bin is the mean/median of y-values (dependent variable) for the x-values inside that bin.

    If the 'statistic' contains the int, then this number defines the number of bins. If the
    'statistic' contains the string from the keys of <_BIN_SELECTORS>, then will be use the chosen
    method to calculate the optimal bin width and consequently the number of bins.

    :param list x_pts: the list of x points coordinates
    :param list y_pts: the list of x points coordinates
    :param str statistic: the statistic to compute
    :param str/int bins: the number of bins to calculate or the name of computational method
    :return dict: the output dictionary with result of analysis
    """
    # Check whether the bins is given by number or by name of method to its compute
    bins_cnt = bins if isinstance(bins, int) else _BIN_SELECTORS[bins](np.array(x_pts))
    # Compute a binned statistic for the given data
    bin_stats, bin_edges, bin_numbers = stats.binned_statistic(x_pts, y_pts, statistic, max(1, bins_cnt))
    # Replace the NaN in empty bins with 0 for plotting
    bin_stats = np.nan_to_num(bin_stats)
    # Create output dictionaries
    return {
        'bins_method': 'user' if isinstance(bins, int) else bins,
        'statistics': statistic,
        'bin_stats': bin_stats.tolist(),
        'x_interval_start': np.min(bin_edges),
        'x_interval_end': np.max(bin_edges),
        'y_interval_start': min(y_pts),
        'r_square': metrics.r2_score(y_pts, [bin_stats[bin_number - 1] for bin_number in bin_numbers])
    }


def step(graph, x_pts, y_pts, graph_params):
    """
    Render step lines according to given coordinates and other parameters.

    :param charts.Graph graph: the scatter plot
    :param x_pts: the x-coordinates for the points of the line
    :param y_pts: the y-coordinates for the points of the line
    :param dict graph_params: contains the specification of parameters for graph (color, line_width, legend)
    :returns charts.Graph: the modified graph with model of step function
    """
    xx = np.sort(list(x_pts) + list(x_pts))
    xx = xx[:-1]
    yy = list(y_pts) + list(y_pts)
    yy[::2] = y_pts
    yy[1::2] = y_pts
    yy = yy[1:]
    graph.line(xx, yy, color=graph_params.get('color'), line_width=graph_params.get('line_width'),
               legend=graph_params.get('legend'))
    return graph


def choose_bin_sizes(ctx, param, value):
    """
    Processing of '--bins/-b' parameter that represents the number of bins or method for its computation.

    If 'bins' is an int, it defines the number of bins.
    If 'bins' is a string, it defines the method, that will use to compute the optimal number of bins.
    If 'bins' is a string  but is not included in keys of <_BIN_SELECTORS>, then it's the error.

    :param click.Context ctx: internal object that holds state relevant for the script execution at every single level
    :param click.Option param: additive options from commands decorator
    :param int/str value: the number of bins to calculate or the name of computational method
    :raises click.BadParameter: in case the name of the method is unsupported
    :return int: the number of bins selected by user or computed by given method
    """
    if value.isdigit():
        return int(value)
    elif value in _BIN_SELECTORS:
        return value
    else:
        raise BadParameter(
            '\nError: Invalid value for "--bins": invalid choice: {} '
            '(choose from scott, sqrt, sturges, fd, auto, doane, rice) or integer'.format(value))


# Code for calculating number of bins for regressogram can be got from SciPy:
# https://docs.scipy.org/doc/numpy/reference/generated/numpy.histogram_bin_edges.html#numpy.histogram_bin_edges

# supported methods to choose bin sizes for regressogram
_BIN_SELECTORS = {
    'auto': np_bin_selectors._hist_bin_auto,
    'doane': np_bin_selectors._hist_bin_doane,
    'fd': np_bin_selectors._hist_bin_fd,
    'rice': np_bin_selectors._hist_bin_rice,
    'scott': np_bin_selectors._hist_bin_scott,
    'sqrt': np_bin_selectors._hist_bin_sqrt,
    'sturges': np_bin_selectors._hist_bin_sturges,
}
