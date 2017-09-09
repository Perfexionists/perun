"""The module with supported regression models specification.

This module contains specification of supported regression model and support for their application.
The Models enum allows to specify which models should be computed and the mapping functions yields
the sections of _models dictionary representing the model properties.

"""

import math

import perun.postprocess.regression_analysis.generic as generic
import perun.postprocess.regression_analysis.specific as specific
import perun.utils.exceptions as exceptions


def get_supported_models():
    """Provides all currently supported models as a list of their names.

    The 'all' specifier is used in reverse mapping as it enables to easily specify all models

    Returns:
        list of str: the names of all supported models and 'all' specifier
    """
    return [key for key in sorted(_MODELS.keys())]


def map_to_models(regression_models):
    """The mapping generator which provides the sections of _MODELS dictionary according to
    specified models list.

    Arguments:
        regression_models(tuple): the list of Models values
    Raises:
        InvalidModelException: if specified model does not have a properties record in _MODELS
                               dictionary
    Return:
        iterable: the generator object which yields models records one by one as a dictionary

    """
    # Convert single value to list
    if not isinstance(regression_models, tuple):
        regression_models = tuple(regression_models)

    # Get all models
    if not regression_models or 'all' in regression_models:
        for model in sorted(_MODELS.keys()):
            if model != 'all':
                yield _MODELS[model].copy()
    # Specific models
    else:
        for model in regression_models:
            if model not in _MODELS.keys():
                raise exceptions.InvalidModelException(model)
            else:
                yield _MODELS[model].copy()

# Supported models properties
# Each model record contains the parameters required by the computational functions,
# the data generator and list of functions.
# The record can also contain optional parameters as needed.
_MODELS = {
    'all': {},  # key representing all models
    'linear': {
        'model': 'linear',
        'fx': lambda x: x,
        'fy': lambda y: y,
        'fa': lambda a: a,
        'fb': lambda b: b,
        'data_gen': generic.generic_regression_data,
        'computation': generic.generic_compute_regression,
        'func_list': [
            generic.generic_regression_coefficients,
            generic.generic_regression_error
        ]
    },
    'log': {
        'model': 'logarithmic',
        'fx': math.log10,
        'fy': lambda y: y,
        'fa': lambda a: a,
        'fb': lambda b: b,
        'fp': math.log10,
        'data_gen': generic.generic_regression_data,
        'computation': generic.generic_compute_regression,
        'func_list': [
            generic.generic_regression_coefficients,
            generic.generic_regression_error
        ]
    },
    'quad': {
        'model': 'quadratic',
        'fx': lambda x: x ** 2,
        'fy': lambda y: y,
        'fa': lambda a: a,
        'fb': lambda b: b,
        'fp': lambda p: p ** 2,
        'data_gen': generic.generic_regression_data,
        'computation': generic.generic_compute_regression,
        'func_list': [
            generic.generic_regression_coefficients,
            specific.quad_regression_error
        ]
    },
    'power': {
        'model': 'power',
        'fx': math.log10,
        'fy': math.log10,
        'fa': lambda a: 10 ** a,
        'fb': lambda b: b,
        'data_gen': generic.generic_regression_data,
        'computation': generic.generic_compute_regression,
        'func_list': [
            generic.generic_regression_coefficients,
            specific.power_regression_error
        ]
    },
    'exp': {
        'model': 'exponential',
        'fx': lambda x: x,
        'fy': math.log10,
        'fa': lambda a: 10 ** a,
        'fb': lambda b: 10 ** b,
        'data_gen': generic.generic_regression_data,
        'computation': generic.generic_compute_regression,
        'func_list': [
            generic.generic_regression_coefficients,
            specific.exp_regression_error
        ]
    }
}
