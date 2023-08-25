""" Module for regression analysis transformations. Serves as a simple interface for higher-level
    modules (e.g. profile/converters).

"""

from typing import Any

import perun.postprocess.regression_analysis.tools as tools
import perun.postprocess.regression_analysis.regression_models as regression_models


def coefficients_to_points(
        model: str,
        coeffs: list[dict],
        x_start: int,
        x_end: int,
        **_: Any
) -> dict:
    """ Transform computed coefficients from regression analysis into points, which can be
        plotted as a function / curve.

    :param str model: the model name
    :param list coeffs: the model coefficients
    :param int or float x_start: the left bound of the x interval
    :param int or float x_end: the right bound of the x interval
    :raises DictionaryKeysValidationFailed: if some dictionary checking fails
    :raises TypeError: if the required function arguments are not in the unpacked dictionary input
    :returns dict: dictionary with 'plot_x' and 'plot_y' arrays
    """
    # Get the transformation data from the regression models
    data = regression_models.get_transformation_data_for(model, 'plot_model')

    # Validate the transformation data dictionary
    tools.validate_dictionary_keys(data, ['computation'], [])

    # Add the coefficients and interval values safely to the data dictionary
    for coefficient in coeffs:
        data.update({
            coefficient.get('name', 'invalid_coeff'): coefficient.get('value', 0)
        })
    data.update({
        'x_start': x_start,
        'x_end': x_end
    })

    # Call the transformation function and check results
    data = data['computation'](**data)
    # Check that the transformation was successful
    tools.validate_dictionary_keys(data, ['plot_x', 'plot_y'], [])

    # return the computed points
    return data
