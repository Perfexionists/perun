"""The module with supported regression models specification.

This module contains specification of supported regression model and support for their application.
The _MODELS dict allows to specify which models should be computed and the mapping functions yields
the sections of _MODELS dictionary representing the model properties.

"""

import math

import perun.postprocess.regression_analysis.generic as generic
import perun.postprocess.regression_analysis.specific as specific
import perun.postprocess.regression_analysis.derived as derived
import perun.postprocess.regression_analysis.extensions.plot_models as plot
import perun.utils.exceptions as exceptions


def get_supported_models():
    """Provides all currently supported models as a list of their names.

    The 'all' specifier is used in reverse mapping as it enables to easily specify all models

    Returns:
        list of str: the names of all supported models and 'all' specifier
    """
    # Disable quadratic model, but allow to process already existing profiles with quad model
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
    elements = {_MODELS[m].get('model'): m for m in _MODELS}
    # Check the key validity
    if model is not None and model in elements:
        return elements[model]
    return None


def filter_derived(regression_models_keys):
    """Filtering of the selected models to standard and derived models.

    Arguments:
        regression_models_keys(tuple of str): the models to be computed
    Returns:
        tuple, tuple: the derived models and standard models in separated tuples
    """
    # Convert single value to list
    if not isinstance(regression_models_keys, tuple):
        regression_models_keys = tuple(regression_models_keys)

    # Get all models
    if not regression_models_keys or 'all' in regression_models_keys:
        regression_models_keys = list(filter(lambda m: m != 'all', _MODELS.keys()))

    # Split the models into derived and non-derived
    der, normal = [], []
    for model in regression_models_keys:
        if model not in _MODELS.keys():
            raise exceptions.InvalidModelException(model)
        if 'derived' in _MODELS[model]:
            der.append(model)
        else:
            normal.append(model)

    # Add models that are required by derived models if not already present
    for model in der:
        if 'required' in _MODELS[model] and _MODELS[model]['required'] not in normal:
            # Check if the model exists
            if _MODELS[model]['required'] not in _MODELS.keys():
                raise exceptions.InvalidModelException(model)
            normal.append(_MODELS[model]['required'])
    return tuple(der), tuple(normal)


# Supported models properties
# Each model record contains the parameters required by the computational functions,
# the data generator and list of functions.
# The record can also contain optional parameters as needed.
# Keys description:
# - model: full name of the regression model
# - f_x: function that modifies x values in model computation according to formulae
# - f_y: function that modifies y values in model computation according to formulae
# - f_a: function that modifies b0 (a) coefficient in model computation according to formulae
# - f_b: function that modifies b1 (b) coefficient in model computation according to formulae
# - data_gen: function that generates intermediate values from points for model computation
# - computation: core function that controls the model computation
# - func_list: functions that are applied to the 'data_gen'erated values
# -------------------------------------------------------------------------------------
# Transformations: section for extensions and transformations of the resulting models
# - plot_model: section for transformations of model properties to points which can be plotted
# -- computation: core function that controls the transformation process
# -- model_x: function that produces x coordinates of points
# -- model_y: function that produces y coordinates of points
# -- m_fx: function that modifies x coordinates according to formulae
# -- formula: function with formula for y coordinates computation
_MODELS = {
    'all': {},  # key representing all models
    'constant': {
        'model': 'constant',
        'f_x': 0,
        'derived': derived.derived_const,
        'required': 'linear',
        'b1_threshold': 0.001,
        'transformations': {
            'plot_model': {
                'computation': plot.model_plot_computation,
                'model_x': plot.generic_plot_x_pts,
                'model_y': plot.generic_plot_y_pts,
                'formula': lambda b0, b1, x: b0 + b1 * x
            }
        }
    },
    'linear': {
        'model': 'linear',
        'f_x': lambda x: x,
        'f_y': lambda y: y,
        'f_a': lambda a: a,
        'f_b': lambda b: b,
        'data_gen': generic.generic_regression_data,
        'computation': generic.generic_compute_regression,
        'func_list': [
            generic.generic_regression_coefficients,
            generic.generic_regression_error
        ],
        'transformations': {
            'plot_model': {
                'computation': plot.model_plot_computation,
                'model_x': plot.generic_plot_x_pts,
                'model_y': plot.generic_plot_y_pts,
                'formula': lambda b0, b1, x: b0 + b1 * x
            }
        }
    },
    'logarithmic': {
        'model': 'logarithmic',
        'f_x': math.log,
        'f_y': lambda y: y,
        'f_a': lambda a: a,
        'f_b': lambda b: b,
        'data_gen': generic.generic_regression_data,
        'computation': generic.generic_compute_regression,
        'func_list': [
            generic.generic_regression_coefficients,
            generic.generic_regression_error
        ],
        'transformations': {
            'plot_model': {
                'computation': plot.model_plot_computation,
                'model_x': plot.generic_plot_x_pts,
                'model_y': plot.generic_plot_y_pts,
                'm_fx': math.log,
                'formula': lambda b0, b1, x: b0 + b1 * x
            }
        }
    },
    # Should not be used for new profiles, the quadratic model can be achieved using the power model
    'quadratic': {
        'model': 'quadratic',
        'data_gen': specific.specific_quad_data,
        'computation': generic.generic_compute_regression,
        'func_list': [
            specific.specific_quad_coefficients,
            specific.specific_quad_error
        ],
        'transformations': {
            'plot_model': {
                'computation': plot.model_plot_computation,
                'model_x': plot.generic_plot_x_pts,
                'model_y': plot.quad_plot_y_pts,
                'formula': lambda b0, b1, b2, x: b0 + b1 * x + b2 * (x ** 2)
            }
        }
    },
    'power': {
        'model': 'power',
        'f_x': math.log10,
        'f_y': math.log10,
        'f_a': lambda a: 10 ** a,
        'f_b': lambda b: b,
        'data_gen': generic.generic_regression_data,
        'computation': generic.generic_compute_regression,
        'func_list': [
            generic.generic_regression_coefficients,
            generic.generic_regression_error
        ],
        'transformations': {
            'plot_model': {
                'computation': plot.model_plot_computation,
                'model_x': plot.generic_plot_x_pts,
                'model_y': plot.generic_plot_y_pts,
                'formula': lambda b0, b1, x: b0 * x ** b1
            }
        }
    },
    'exponential': {
        'model': 'exponential',
        'f_x': lambda x: x,
        'f_y': math.log10,
        'f_a': lambda a: 10 ** a,
        'f_b': lambda b: 10 ** b,
        'data_gen': generic.generic_regression_data,
        'computation': generic.generic_compute_regression,
        'func_list': [
            generic.generic_regression_coefficients,
            generic.generic_regression_error
        ],
        'transformations': {
            'plot_model': {
                'computation': plot.model_plot_computation,
                'model_x': plot.generic_plot_x_pts,
                'model_y': plot.generic_plot_y_pts,
                'formula': lambda b0, b1, x: b0 * b1 ** x
            }
        }
    }
}
