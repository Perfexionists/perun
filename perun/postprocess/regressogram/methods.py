"""
Module with regressogram computational method and auxiliary methods at executing of this method.
"""
from __future__ import annotations

# Standard Imports
from typing import Iterator, Any
import inspect

# Third-Party Imports
import numpy as np
import numpy.lib.histograms as numpy_bucket_selectors
import scipy.stats
import sklearn.metrics

# Perun Imports
from perun.postprocess.regression_analysis import tools

# required arguments at regressogram post-processor
_REQUIRED_KEYS = ["bucket_method", "statistic_function"]


def get_supported_nparam_methods() -> list[str]:
    """Provides all currently supported computational methods, to
    estimate the optimal number of buckets, as a list of their names.

    :returns list of str: the names of all supported methods
    """
    return _METHODS


def get_supported_selectors() -> list[str]:
    """Provides all currently supported computational methods, to
    estimate the optimal number of buckets, as a list of their names.

    :returns list of str: the names of all supported methods
    """
    return list(_BUCKET_SELECTORS.keys())


def compute_regressogram(
    data_gen: Iterator[tuple[list[float], list[float], str]], config: dict[str, Any]
) -> list[dict[str, Any]]:
    """
    The regressogram wrapper to execute the analysis on the individual chunks of resources.

    :param iter data_gen: the generator object with collected data (data provider generators)
    :param dict config: the perun and option context
    :return: list of dict: the computation results
    """
    # checking the presence of specific keys in individual methods
    tools.validate_dictionary_keys(config, _REQUIRED_KEYS, [])

    # list of result of the analysis
    analysis = []
    for x_pts, y_pts, uid in data_gen:
        # Check whether the user gives as own number of buckets or select the method to its estimate
        buckets = (
            config["bucket_number"] if config.get("bucket_number") else config["bucket_method"]
        )
        result = regressogram(x_pts, y_pts, config["statistic_function"], buckets)
        result.update(
            {
                "uid": uid,
                "model": "regressogram",
                "per_key": config["per_key"],
                "of_key": config["of_key"],
            }
        )
        # add partial result to the result list - create output dictionaries
        analysis.append(result)
    return analysis


def regressogram(
    x_pts: list[float], y_pts: list[float], statistic_function: str, buckets: str | int
) -> dict[str, Any]:
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
    if isinstance(buckets, int):
        buckets_num = buckets
    else:
        if len(inspect.signature(_BUCKET_SELECTORS[buckets]).parameters):
            # This is workaround for backward compatibility between numpy 1.15.1 and 1.16.X+
            # In that version, new bucket selector method is introduced that requires additional,
            # parameter, however, our supported methods do not use this parameter at all.
            buckets_num = _BUCKET_SELECTORS[buckets](np.array(x_pts), None)
        else:
            buckets_num = _BUCKET_SELECTORS[buckets](np.array(x_pts))

    # Compute a binned statistic for the given data
    bucket_stats, bucket_edges, bucket_numbers = scipy.stats.binned_statistic(
        x_pts, y_pts, statistic_function, max(1, buckets_num)
    )
    # Replace the NaN in empty buckets with 0 for plotting
    bucket_stats = np.nan_to_num(bucket_stats)
    # Create output dictionaries
    return {
        "buckets_method": "user" if isinstance(buckets, int) else buckets,
        "statistic_function": statistic_function,
        "bucket_stats": bucket_stats.tolist(),
        "x_start": np.min(bucket_edges),
        "x_end": np.max(bucket_edges),
        "y_start": min(y_pts),
        "r_square": sklearn.metrics.r2_score(
            y_pts, [bucket_stats[bucket_number - 1] for bucket_number in bucket_numbers]
        ),
    }


# Code for calculating number of buckets for regressogram can be got from SciPy:
# https://docs.scipy.org/doc/numpy/reference/generated/numpy.histogram_bin_edges.html#numpy.histogram_bucket_edges

# supported methods to choose bucket sizes for regressogram
# Note: Here, we ignore the type, as these are private/protected internal functions, yet we wish to use them ourselves
# without the need to call their main wrapper (histogram)
_BUCKET_SELECTORS = {
    "auto": numpy_bucket_selectors._hist_bin_auto,  # type: ignore
    "doane": numpy_bucket_selectors._hist_bin_doane,  # type: ignore
    "fd": numpy_bucket_selectors._hist_bin_fd,  # type: ignore
    "rice": numpy_bucket_selectors._hist_bin_rice,  # type: ignore
    "scott": numpy_bucket_selectors._hist_bin_scott,  # type: ignore
    "sqrt": numpy_bucket_selectors._hist_bin_sqrt,  # type: ignore
    "sturges": numpy_bucket_selectors._hist_bin_sturges,  # type: ignore
}

# supported non-parametric methods
_METHODS = ["regressogram", "moving_average", "kernel_regression"]
