"""
Module with computational method of moving average and
auxiliary methods at executing of this method.
"""
from __future__ import annotations

# Standard Imports
from typing import Callable, Iterator, Any, cast
import dataclasses

# Third-Party Imports
import click
import numpy as np
import pandas as pd
import sklearn.metrics

# Perun Imports
from perun.postprocess.regression_analysis import tools


@dataclasses.dataclass()
class DecayParamInfo:
    __slots__ = ["condition", "err_msg"]
    condition: Callable[[float], bool]
    err_msg: str


# required precision for moving average models when the window width was not entered
_MIN_R_SQUARE: float = 0.88
# increase of the window width value in each loop, if it has not been reached the required precision
_WINDOW_WIDTH_INCREASE: float = 0.15
# starting window width as the part of the length from the whole current interval
_INTERVAL_LENGTH: float = 0.05


def get_supported_decay_params() -> list[str]:
    """Provides all names of currently supported parameters to specify
    the relationship to determine the smoothing parameter at Exponential
    Moving Average.

    :returns list of str: the names of all supported parameters
    """
    return list(_DECAY_PARAMS_INFO.keys())


def compute_window_width_change(window_width: int, r_square: float) -> int:
    """
    Computation of window width change based on the difference of required and current
    coefficient of determination (R^2) and possible change of the window width.

    The minimal value of the resulting change cannot be less than 1.
    The maximal value of the resulting change cannot be greater than 90% of current window_width.
    The new value of the window with cannot be less than 1.
    The formula to determine the change of the window width depends on the three values:
        - difference between coefficient of determinations: required_R^2 - current_R^2
        - possible change of the window width (minimal width is equal to 1): window_width - 1
        - value of the increase constant of the window width: WINDOW_WIDTH_INCREASE
    The resulting change of the window width is the product of multiplication of these values.

    :param int window_width: current window width from the last run of computation
    :param float r_square: coefficient of determination from the current moving average model
    :return int: new value of window width for next run of iterative computation
    """
    window_change = _WINDOW_WIDTH_INCREASE * (window_width - 1) * (_MIN_R_SQUARE - r_square)
    return max(1, window_width - max(1, int(min(0.9 * window_width - 1, window_change))))


def compute_moving_average(
    data_gen: Iterator[tuple[list[float], list[float], str]],
    configuration: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    The moving average wrapper to execute the analysis on the individual chunks of resources.

    :param iter data_gen: the generator object with collected data (data provider generators)
    :param dict configuration: the perun and option context
    :return: list of dict: the computation results
    """
    # checking the presence of specific keys in individual methods
    tools.validate_dictionary_keys(
        configuration, _METHOD_REQUIRED_KEYS[configuration["moving_method"]], []
    )

    # list of resulting models of the analysis
    moving_average_models = []
    for x_pts, y_pts, uid in data_gen:
        moving_average_model = moving_average(x_pts, y_pts, configuration)
        moving_average_model["uid"] = uid
        moving_average_model["model"] = "moving_average"
        # add partial result to the model result list - create output dictionaries
        moving_average_models.append(moving_average_model)
    return moving_average_models


def execute_computation(y_pts: list[float], config: dict[str, Any]) -> tuple[Any, float]:
    """
    The computation wrapper of supported methods of moving average approach.

    In this method is executing the main logic, or better said, are called the
    relevant methods to compute the supported methods of moving average, so Simple
    and Exponential Moving Averages. For computation of the Simple Moving average
    is used the method `rolling()` from the pandas module. Method `ewm()`, also
    from pandas, is used to compute Exponential Moving Average. Except for the
    calculation of moving average statistics, is in this method computing the
    coefficient of determination (R^2), using the method `r2_score` from
    sklearn package.

    For more details about these methods, you can see the Perun or Pandas documentation.

    :param list y_pts: the tuple of y-coordinates for computation
    :param dict config: the dict contains the needed parameters to compute the individual methods
    :return tuple: pandas.Series with the computed result, coefficient of determination float value
    """
    # computation of Simple Moving Average and Simple Moving Median
    if config["moving_method"] in ("sma", "smm"):
        bucket_stats: Any = pd.Series(data=y_pts).rolling(
            window=config["window_width"],
            min_periods=config["min_periods"],
            center=config["center"],
            win_type=config.get("window_type"),
        )
        # computation of the individual values based on the selected methods
        bucket_stats = (
            bucket_stats.median() if config["moving_method"] == "smm" else bucket_stats.mean()
        )
    # computation of Exponential Moving Average
    elif config["moving_method"] == "ema":
        decay_dict = {config["decay"]: config["window_width"]}
        bucket_stats = (
            pd.Series(data=y_pts)
            .ewm(
                com=decay_dict.get("com"),
                span=decay_dict.get("span"),
                alpha=decay_dict.get("alpha"),
                halflife=decay_dict.get("halflife"),
                min_periods=config["min_periods"] or config["window_width"],
            )
            .mean()
        )
    else:
        bucket_stats = pd.Series()
    # computation of the coefficient of determination (R^2)
    r_square = sklearn.metrics.r2_score(y_pts, np.nan_to_num(bucket_stats))
    return bucket_stats, r_square


def moving_average(
    x_pts: list[float], y_pts: list[float], configuration: dict[str, Any]
) -> dict[str, Any]:
    """
    Compute the moving average of a set of data.

    The main control method, that covers all actions needed at executing the
    analysis using the moving average approach. Based on the specified parameters
    obtains the result of the analysis, from which creates the relevant dictionary.
    This dictionary contains the whole set of helpful keys, and it is the result of
    the whole moving average analysis.

    :param list x_pts: the list of x points coordinates
    :param list y_pts: the list of y points coordinates
    :param dict configuration: the perun and option context with needed parameters
    :return dict: the output dictionary with result of analysis
    """
    # Sort the points to the right order for computation
    # Fixme: this is needed for type checking
    x_pts, y_pts = cast(tuple[list[float], list[float]], map(list, zip(*sorted(zip(x_pts, y_pts)))))

    # If has been specified the window width by user, then will be followed the direct computation
    if configuration.get("window_width"):
        bucket_stats, r_square = execute_computation(y_pts, configuration)
    # If we did not specify the window width, then will be followed the iterative computation
    else:
        bucket_stats, r_square, configuration["window_width"] = iterative_analysis(
            x_pts, y_pts, configuration
        )

    # Create output dictionaries
    return {
        "moving_method": configuration["moving_method"],
        "window_width": configuration["window_width"],
        "x_start": min(x_pts),
        "x_end": max(x_pts),
        "r_square": r_square,
        "bucket_stats": [float(value) for value in bucket_stats.values],
        "per_key": configuration["per_key"],
    }


def iterative_analysis(
    x_pts: list[float], y_pts: list[float], config: dict[str, Any]
) -> tuple[pd.Series[Any], float, int]:
    """
    Compute the iterative analysis of a set of data by moving average methods.

    In the case, when the user does not enter the value of window width, we try
    approximate this value. Our goal is to achieve the appropriate value of the
    `coefficient of determination` (:math:`R^2`), which guaranteed, that the resulting
    models will have the desired smoothness. In first step of iterative analysis is
    set the initial value of window width and then follows the interleaving of the
    given dataset, which runs until the value of `coefficient of determination`
    will not reach the required level.

    :param list x_pts: the list of x points coordinates
    :param list y_pts: the list of y points coordinates
    :param dict config: the perun and option context with needed parameters
    :return tuple: pandas.Series with the computed result -
        coefficient of determination float value - window width (int)
    """
    # set the initial value of window width by a few percents of the length of the interval
    # - minimal window width is equal to 1
    config["window_width"] = max(1, int(_INTERVAL_LENGTH * (max(x_pts) - min(x_pts))))
    r_square, window_new_change = 0.0, 1
    # executing the iterative analysis until the value of R^2 will not reach the required level
    bucket_stats: pd.Series[Any] = pd.Series()
    while r_square < _MIN_R_SQUARE and window_new_change:
        # obtaining new results from moving average analysis
        bucket_stats, r_square = execute_computation(y_pts, config)
        # check whether the window width is still changing
        new_window_width = compute_window_width_change(config["window_width"], r_square)
        window_new_change = config["window_width"] - new_window_width
        # computation of the new window width, if yet have not been achieved the desired smoothness
        config["window_width"] = new_window_width
    return bucket_stats, r_square, config["window_width"]


def validate_decay_param(
    _: click.Context, param: click.Option, value: tuple[str, int]
) -> tuple[str, int]:
    """
    Callback method for `decay` parameter at Exponential Moving Average.

    Method to execute the validation of value entered with `decay` parameter.
    According to name entered at this parameter the value must in the relevant
    range. In the case of successful validation the original value will be returned.
    In the case of unsuccessful validation will be raised the exception with the
    relevant warning message about the entered value out of the acceptable range.

    :param click.Context _: the current perun and option context
    :param click.Option param:  additive options from relevant commands decorator
    :param tuple value: the value of the parameter that invoked the callback method (name, value)
    :raises click.BadOptionsUsage: in the case when was entered the value from the invalid range
    :return float: returns value of the parameter after the executing successful validation
    """
    # calling the condition and then checking its validity
    # - value[0] contains the name of the selected `decay` method (e.g. com)
    # - value[1] contains the numeric value (e.g. 3)
    if _DECAY_PARAMS_INFO[value[0]].condition(value[1]):
        return value
    else:  # value out of acceptable range
        # obtaining the error message according to name of `decay` method
        err_msg = _DECAY_PARAMS_INFO[value[0]].err_msg
        raise click.BadOptionUsage(
            param.name or "",
            "Invalid value for %s: %d (must be %s)" % (value[0], value[1], err_msg),
        )


# dictionary contains the required keys to check before the access to these keys
# - required keys are divided according to individual supported methods
_METHOD_REQUIRED_KEYS: dict[str, list[str]] = {
    "sma": ["moving_method", "center", "window_type", "min_periods", "per_key"],
    "smm": ["moving_method", "center", "min_periods", "per_key"],
    "ema": ["decay", "min_periods", "per_key"],
}

# dictionary serves for validation values at `decay` parameter - validation of acceptable range
# - dictionary contains the recognized `decay` method names as key
# -- dictionary contains the validate condition and warning message as value
_DECAY_PARAMS_INFO: dict[str, DecayParamInfo] = {
    "com": DecayParamInfo(lambda value: value >= 0.0, ">= 0.0"),
    "span": DecayParamInfo(lambda value: value >= 1.0, ">= 1.0"),
    "halflife": DecayParamInfo(lambda value: value > 0.0, "> 0.0"),
    "alpha": DecayParamInfo(lambda value: 0 < value <= 1.0, "0.0 < alpha <= 1.0"),
}
