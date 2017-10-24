""" Module for regression analysis transformations. Serves as a simple interface for higher-level
    modules (e.g. profile/converters).

"""

from perun.postprocess.regression_analysis.regression_models import get_transformation_data_for
import perun.postprocess.regression_analysis.tools as tools


def coefficients_to_points(model, coeffs, x_interval_start, x_interval_end, **_):
    """ Transform computed coefficients from regression analysis into points, which can be
        plotted as a function / curve.

    Arguments:
        model(str): the model name
        coeffs(list): the model coefficients
        x_interval_start(int or float): the left bound of the x interval
        x_interval_end(int or float): the right bound of the x interval
    Raises:
        DictionaryKeysValidationFailed: if some dictionary checking fails
        TypeError: if the required function arguments are not in the unpacked dictionary input
    Return:
        dict: dictionary with 'plot_x' and 'plot_y' arrays
    """
    # Get the transformation data from the regression models
    data = get_transformation_data_for(model, 'plot_model')

    # Validate the transformation data dictionary
    tools.validate_dictionary_keys(data, ['computation'], [])

    # Add the coefficients and interval values safely to the data dictionary
    for coefficient in coeffs:
        data.update({
            coefficient.get('name', 'invalid_coeff'): coefficient.get('value', 0)
        })
    data.update({
        'x_interval_start': x_interval_start,
        'x_interval_end': x_interval_end
    })

    # Call the transformation function and check results
    data = data['computation'](**data)
    # Check that the transformation was successful
    tools.validate_dictionary_keys(data, ['plot_x', 'plot_y'], [])

    # return the computed points
    return data
