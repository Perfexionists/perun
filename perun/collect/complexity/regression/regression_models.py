"""The module with supported regression models specification.

This module contains specification of supported regression model and support for their application.
The Models enum allows to specify which models should be computed and the mapping functions yields
the sections of _models dictionary representing the model properties.

"""


import regression_analysis.generic as generic
import regression_analysis.specific as specific
import regression_analysis.regression_exceptions as reg_except
import enum
import math


class Models(enum.Enum):
    """The list of all currently supported models.

    The 'all' element covers all of the supported models at once (for convenient specification in method usage)

    """
    all = 'all'
    linear = 'linear'
    log = 'logarithmic'
    quad = 'quadratic'
    pow = 'power'
    exp = 'exponential'


def map_to_models(models_list):
    """The mapping generator which provides the sections of _models dictionary according to specified models list.

    Arguments:
        models_list(list): the list of Models values
    Raises:
        InvalidModelType: if specified model does not have a properties record in _models dictionary
    Return:
        iterable: the generator object which yields models records one by one as a dictionary

    """
    # Convert single value to list
    if type(models_list) is not list:
        models_list = [models_list]

    # Get all models
    if not models_list or Models.all in models_list:
        for name, member in Models.__members__.items():
            if member.name != 'all':
                yield _models[member.value].copy()
    # Specific models
    else:
        for member in models_list:
            if member not in Models:
                raise reg_except.InvalidModelType(member)
            else:
                yield _models[member.value].copy()

# Supported models properties
# Each model record contains the parameters required by the computational functions, the data generator
# and list of functions.
# The record can also contain optional parameters as needed.
_models = {
    'linear': {
        'name': 'linear',
        'fx': lambda x: x,
        'fy': lambda y: y,
        'fa': lambda a: a,
        'fb': lambda b: b,
        'data_gen': generic.generic_regression_data,
        'computation': generic.generic_compute_regression,
        'func_list': [
            generic.generic_regression_coefficients,
            generic.generic_regression_error,
            specific.linear_plot_data
        ],
        'func_iter': [
            generic.generic_regression_coefficients,
            generic.generic_regression_error
        ]
    },
    'logarithmic': {
        'name': 'logarithmic',
        'fx': lambda x: math.log10(x),
        'fy': lambda y: y,
        'fa': lambda a: a,
        'fb': lambda b: b,
        'fp': lambda p: math.log10(p),
        'data_gen': generic.generic_regression_data,
        'computation': generic.generic_compute_regression,
        'func_list': [
            generic.generic_regression_coefficients,
            generic.generic_regression_error,
            generic.generic_plot_data
        ],
        'func_iter': [
            generic.generic_regression_coefficients,
            generic.generic_regression_error
        ]
    },
    'quadratic': {
        'name': 'quadratic',
        'fx': lambda x: x ** 2,
        'fy': lambda y: y,
        'fa': lambda a: a,
        'fb': lambda b: b,
        'fp': lambda p: p ** 2,
        'data_gen': generic.generic_regression_data,
        'computation': generic.generic_compute_regression,
        'func_list': [
            generic.generic_regression_coefficients,
            specific.quad_regression_error,
            generic.generic_plot_data
        ],
        'func_iter': [
            generic.generic_regression_coefficients,
            specific.quad_regression_error
        ]
    },
    'power': {
        'name': 'power',
        'fx': lambda x: math.log10(x),
        'fy': lambda y: math.log10(y),
        'fa': lambda a: 10 ** a,
        'fb': lambda b: b,
        'data_gen': generic.generic_regression_data,
        'computation': generic.generic_compute_regression,
        'func_list': [
            generic.generic_regression_coefficients,
            specific.power_regression_error,
            specific.power_plot_data
        ],
        'func_iter': [
            generic.generic_regression_coefficients,
            specific.power_regression_error
        ]
    },
    'exponential': {
        'name': 'exponential',
        'fx': lambda x: x,
        'fy': lambda y: math.log10(y),
        'fa': lambda a: 10 ** a,
        'fb': lambda b: 10 ** b,
        'data_gen': generic.generic_regression_data,
        'computation': generic.generic_compute_regression,
        'func_list': [
            generic.generic_regression_coefficients,
            specific.exp_regression_error,
            specific.exp_plot_data
        ],
        'func_iter': [
            generic.generic_regression_coefficients,
            specific.exp_regression_error
        ]
    }
}
