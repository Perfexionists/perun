"""Module with functions used for derived models computation.

Some models may depend on results of regression models computed previously by
standard regression analysis. Derived computations are more of a heuristics used
for special cases.

"""
from __future__ import annotations

# Standard Imports
import math
from typing import Any, Iterable

# Third-Party Imports

# Perun Imports
from perun.postprocess.regression_analysis import tools


def derived_const(
    analysis: list[dict[str, Any]], const_ref: dict[str, Any], **_: Any
) -> Iterable[dict[str, Any]]:
    """The computation of a constant model based on a linear regression model.

    Current implementation is based on an assumption that linear model with
    very small b1 (slope) coefficient and small R^2 coefficient is similar
    to the constant model and can be used in estimation of its parameters.

    We use a slope threshold value that produces modification coefficient
    based on a deviation from the threshold. Two scenarios may happen:

    1. slope is bigger than threshold
     - compute the multiple of the slopes divided by 10 and add 1 if
       the multiple is below 1, then use this as a modification coefficient
     - divide the 1 - (linear)R^2 by the coefficient

    2. slope is smaller than threshold
     - subtract the slope from the threshold, multiply it by the inverted
       value of the threshold and add 1
     - multiply the 1 - (linear)R^2 by the coefficient

    :param list of dict analysis: computed regression models
    :param dict const_ref: the constant model template from _MODELS dictionary
    :returns iterable: generator which produces constant model for every computed linear model
    """
    # Filter the required models from computed regression models
    analysis = _filter_by_models(analysis, const_ref["required"])
    # Set to default threshold if value is invalid
    const_ref["b1_threshold"] = max(_DEFAULT_THRESHOLD, const_ref["b1_threshold"])

    # Compute const model for every linear
    for result in analysis:
        # Check the keys in the result dictionary
        tools.validate_dictionary_keys(
            result,
            [
                "r_square",
                "coeffs",
                "y_sum",
                "pts_num",
                "x_start",
                "tss",
                "x_end",
                "uid",
                "method",
            ],
            [],
        )

        # Duplicate the constant model template
        const = const_ref.copy()

        y_start = result["coeffs"][0]
        y_end = y_start + result["coeffs"][1] * result["x_end"]
        angle = math.atan2(abs(y_end - y_start), abs(result["x_end"] - result["x_start"]))
        slope_change = angle / 90
        if slope_change > const["b1_threshold"]:
            r = result["r_square"] * (1 - slope_change)
        else:
            r = 1 - result["r_square"]

        # Truncate the r value if needed
        r = 1 if r > 1 else (0 if r < 0 else r)

        # Build the const model record
        const["r_square"] = r
        const["x_start"] = result["x_start"]
        const["x_end"] = result["x_end"]
        const["coeffs"] = [result["y_sum"] / result["pts_num"], 0]
        const["uid"] = result["uid"]
        const["method"] = result["method"]

        yield const


def _filter_by_models(analysis: list[dict[str, Any]], models: list[str]) -> list[dict[str, Any]]:
    """Filters regression results by computed models.

    :param list of dict analysis: the computed regression models
    :param list of str models: the list of models to filter from the analysis
    :returns list: the filtered analysis results
    """
    # Filter the required models from the analysis list
    return list(filter(lambda m: "model" in m and m["model"] in models, analysis))


# Use default threshold value if the provided is invalid
_DEFAULT_THRESHOLD = 0.01
