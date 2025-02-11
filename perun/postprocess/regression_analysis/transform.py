"""Module for regression analysis transformations. Serves as a simple interface for higher-level
modules (e.g. profile/converters).

"""

from __future__ import annotations

# Standard Imports
from typing import Any

# Third-Party Imports

# Perun Imports
from perun.postprocess.regression_analysis import regression_models, tools


def coefficients_to_points(
    model: str, coeffs: list[dict[str, Any]], x_start: int, x_end: int, **_: Any
) -> dict[str, Any]:
    """Transform computed coefficients from regression analysis into points, which can be
        plotted as a function / curve.

    :param model: the model name
    :param coeffs: the model coefficients
    :param x_start: the left bound of the x interval
    :param x_end: the right bound of the x interval
    :raises DictionaryKeysValidationFailed: if some dictionary checking fails
    :raises TypeError: if the required function arguments are not in the unpacked dictionary input
    :return: dictionary with 'plot_x' and 'plot_y' arrays
    """
    # Get the transformation data from the regression models
    data = regression_models.get_transformation_data_for(model, "plot_model")

    # Validate the transformation data dictionary
    tools.validate_dictionary_keys(data, ["computation"], [])

    # Add the coefficients and interval values safely to the data dictionary
    for coefficient in coeffs:
        data.update({coefficient.get("name", "invalid_coeff"): coefficient.get("value", 0)})
    data.update({"x_start": x_start, "x_end": x_end})

    # Call the transformation function and check results
    data = data["computation"](**data)
    # Check that the transformation was successful
    tools.validate_dictionary_keys(data, ["plot_x", "plot_y"], [])

    # return the computed points
    return data
