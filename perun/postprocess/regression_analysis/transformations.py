""" Module for regression analysis transformations. Serves as a simple interface for higher-level
    modules (e.g. profile/converters).

"""

from perun.postprocess.regression_analysis.regression_models import get_transformation_data_for
import perun.postprocess.regression_analysis.tools as tools


def coefficients_to_points(model):
    """ Transform computed coefficients from regression analysis into points, which can be
        plotted as a function / curve.

    Arguments:
        model(dict): the models dictionary from profile

    Return:
        dict: updated models dictionary with 'plot_x' and 'plot_y' lists
    """
    # Validate model validity
    tools.validate_dictionary_keys(
        model, ['model', 'coeffs', 'x_interval_start', 'x_interval_end'], [])

    # Get the transformation data from the regression models
    data = get_transformation_data_for(model['model'], 'plot_model')

    # Validate the transformation data dictionary
    tools.validate_dictionary_keys(data, ['computation'], [])

    # Add the coefficients and interval values safely to the data dictionary
    # In case of missing key, the DictionaryKeysValidationFailed exception will be raised
    for coefficient in model.get('coeffs', []):
        data.update({
            coefficient.get('name', 'invalid_coeff'): coefficient.get('value', 0)
        })
    data.update({
        'x_interval_start': model['x_interval_start'],
        'x_interval_end': model['x_interval_end']
    })

    # Call the transformation function and check results
    data = data['computation'](data)
    tools.validate_dictionary_keys(data, ['plot_x', 'plot_y'], [])

    # return the computed points
    model.update({
        'plot_x': data['plot_x'],
        'plot_y': data['plot_y']
    })
    return model
