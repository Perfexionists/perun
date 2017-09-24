"""The module with supported regression models specification.

This module contains specification of supported regression model and support for their application.
The Models enum allows to specify which models should be computed and the mapping functions yields
the sections of _models dictionary representing the model properties.

"""

import math

import perun.postprocess.regression_analysis.generic as generic
import perun.postprocess.regression_analysis.specific as specific
import perun.postprocess.regression_analysis.extensions.plot_models as plot
import perun.utils.exceptions as exceptions


def get_supported_models():
    """Provides all currently supported models as a list of their names.

    The 'all' specifier is used in reverse mapping as it enables to easily specify all models

    Returns:
        list of str: the names of all supported models and 'all' specifier
    """
    return [key for key in sorted(_MODELS.keys())]


def get_supported_transformations(model_key):
    """Provides all currently supported transformations for given model as a list of their names.

    Arguments:
        model_key(str): model key (e.g. 'log') for which the transformations are gathered

    Returns:
        list of str: the names of all supported transformations for given model
    """
    return [t for t in _MODELS.get(model_key, {}).get('transformations', {}).keys()]


def get_transformation_data_for(regression_model, transformation):
    """Provides transformation dictionary from _MODELS for specific transformation and model.

    Arguments:
        regression_model(str): the regression model in which to search for transformation
        transformation(str): transformation name (key in _MODELS transformation, e.g. plot_model)
                             that identify the desired transformation dictionary

    Returns:
        dict: the transformation dictionary
    """
    # Get the model key first
    key = map_model_to_key(regression_model)
    if key is None:
        # Model does not exist
        raise exceptions.InvalidModelException(regression_model)

    # Now get the transformations
    if transformation not in get_supported_transformations(key):
        # Model does not support requested transformation
        raise exceptions.InvalidTransformationException(regression_model, transformation)
    return _MODELS[key]['transformations'][transformation]


def map_keys_to_models(regression_models_keys):
    """The mapping generator which provides the sections of _MODELS dictionary according to
    specified model keys list.

    Arguments:
        regression_models_keys(tuple): the list of Models values
    Raises:
        InvalidModelException: if specified model does not have a properties record in _MODELS
                               dictionary
    Return:
        iterable: the generator object which yields models records one by one as a dictionary

    """
    # Convert single value to list
    if not isinstance(regression_models_keys, tuple):
        regression_models_keys = tuple(regression_models_keys)

    # Get all models
    if not regression_models_keys or 'all' in regression_models_keys:
        for model in sorted(_MODELS.keys()):
            if model != 'all':
                yield _MODELS[model].copy()
    # Specific models
    else:
        for model in regression_models_keys:
            if model not in _MODELS.keys():
                raise exceptions.InvalidModelException(model)
            else:
                yield _MODELS[model].copy()


def map_model_to_key(model):
    """ The mapping function which takes model name and provides the _MODELS key containing
        the model dictionary.

    Arguments:
        model(str): the model name to map

    Returns:
        str:  the _MODELS key containing the model data
    """
    # Collect all models in _MODELS as a dict of model: key
    elements = {_MODELS[m].get('model'): m for m in _MODELS.keys()}
    # Check the key validity
    if model is not None and model in elements:
        return elements[model]
    return None


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
        ],
        'transformations': {
            'plot_model': {
                'computation': plot.model_plot_computation,
                'y_pts_func': plot.linear_model_plot
            }
        }
    },
    'log': {
        'model': 'logarithmic',
        'fx': math.log10,
        'fy': lambda y: y,
        'fa': lambda a: a,
        'fb': lambda b: b,
        'data_gen': generic.generic_regression_data,
        'computation': generic.generic_compute_regression,
        'func_list': [
            generic.generic_regression_coefficients,
            generic.generic_regression_error
        ],
        'transformations': {
            'plot_model': {
                'computation': plot.model_plot_computation,
                'y_pts_func': plot.generic_model_plot,
                'fp': math.log10
            }
        }
    },
    'quad': {
        'model': 'quadratic',
        'fx': lambda x: x ** 2,
        'fy': lambda y: y,
        'fa': lambda a: a,
        'fb': lambda b: b,
        'data_gen': generic.generic_regression_data,
        'computation': generic.generic_compute_regression,
        'func_list': [
            generic.generic_regression_coefficients,
            specific.quad_regression_error
        ],
        'transformations': {
            'plot_model': {
                'computation': plot.model_plot_computation,
                'y_pts_func': plot.generic_model_plot,
                'fp': lambda p: p ** 2
            }
        }
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
        ],
        'transformations': {
            'plot_model': {
                'computation': plot.model_plot_computation,
                'y_pts_func': plot.power_model_plot
            }
        }
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
        ],
        'transformations': {
            'plot_model': {
                'computation': plot.model_plot_computation,
                'y_pts_func': plot.exp_model_plot
            }
        }
    }
}
