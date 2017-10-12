""" Extension for regression model coefficients transformation into array of points. The points
    array can be then used for model plotting as a series of lines forming a curved line.
"""

import perun.postprocess.regression_analysis.tools as tools
import numpy as np


# Default model curve smoothness specified as number of points generated from x interval
# The higher, the smoother are the curves
DEFAULT_SMOOTHNESS = 51


def model_plot_computation(data):
    """ The model plotting computation wrapper. Handles common operations regardless of model,
        uses 'y_pts_func' to compute y values, which can be model-specific

    Expects 'y_pts_func', 'x_interval_start', 'x_interval_end', 'b0' and 'b1' keys in the
    data dictionary.

    Updates the data dictionary with 'plot_x' and 'plot_y' lists containing the model points
    for plotting.

    Arguments:
        data(dict): the data dictionary with computed regression model
    Raises:
        DictionaryKeysValidationFailed: if the data dictionary is missing any of the keys
    Return:
        dict: the data dictionary updated with plotting points

    """
    # Validate the data dictionary
    tools.validate_dictionary_keys(data, ['y_pts_func', 'x_interval_start', 'x_interval_end'], [])

    # Split the x length into evenly distributed points
    data['plot_x'] = tools.linspace_safe(data['x_interval_start'], data['x_interval_end'],
                                         data.get('smoothness', DEFAULT_SMOOTHNESS))
    # Compute the function values for x_pts which are stored as 'plot_y'
    data = data['y_pts_func'](data)
    # Validate that the y function generated 'plot_y'
    tools.validate_dictionary_keys(data, ['plot_x', 'plot_y'], [])
    return data


def generic_model_plot(data):
    """ The generic function for plot_y points computation. This function computes the points
        for model plotting using the general formula.

    Expects 'plot_x', 'fp', 'b0' and 'b1' keys in the data dictionary.
    The 'fp' function modifies the value of point x according to the regression model.

    Updates the data dictionary with 'plot_y' lists containing the y values for plotting.

    Arguments:
        data(dict): the data dictionary with computed regression model
    Raises:
        DictionaryKeysValidationFailed: if the data dictionary is missing any of the keys
    Return:
        dict: the data dictionary updated with 'plot_y'

    """
    # Validate the data dictionary
    tools.validate_dictionary_keys(data, ['plot_x', 'fp', 'b0', 'b1'], [])

    # Compute the function value for each x point
    y_pts = []
    remove_list = []
    for idx, x_pt in enumerate(data['plot_x']):
        try:
            y_pts.append(data['fp'](x_pt))
        except ValueError:
            # Possible domain error
            remove_list.append(idx)
    if remove_list:
        data['plot_x'] = np.delete(data['plot_x'], remove_list)
    data['plot_y'] = np.array(data['b0'] + data['b1'] * np.array(y_pts))
    return data


def const_model_plot(data):
    """ The constant model specific version for plot_y points computation. This version is
        more efficient for the plotting computation than the generic one.

    Expects 'b0' key in the data dictionary.

    Updates the data dictionary with 'plot_y' lists containing the y values for plotting.

    Arguments:
        data(dict): the data dictionary with computed linear model
    Raises:
        DictionaryKeysValidationFailed: if the data dictionary is missing any of the keys
    Return:
        dict: the data dictionary updated with 'plot_y'

    """
    # Validate the data dictionary
    tools.validate_dictionary_keys(data, ['b0'], [])

    # Create constant array of b0 coefficient value
    data['plot_y'] = np.full((DEFAULT_SMOOTHNESS, ), data['b0'])
    return data


def linear_model_plot(data):
    """ The linear specific version for plot_y points computation. This version is slightly
        more efficient for the plotting computation than the generic one.

    Expects 'plot_x', 'b0' and 'b1' keys in the data dictionary.

    Updates the data dictionary with 'plot_y' lists containing the y values for plotting.

    Arguments:
        data(dict): the data dictionary with computed linear model
    Raises:
        DictionaryKeysValidationFailed: if the data dictionary is missing any of the keys
    Return:
        dict: the data dictionary updated with 'plot_y'

    """
    # Validate the data dictionary
    tools.validate_dictionary_keys(data, ['plot_x', 'b0', 'b1'], [])

    # Compute the function value for every x value
    data['plot_y'] = np.array(data['b0'] + data['b1'] * np.array(data['plot_x']))
    return data


def power_model_plot(data):
    """ The power specific version for plot_y points computation.

    Expects 'plot_x', 'b0' and 'b1' keys in the data dictionary.

    Updates the data dictionary with 'plot_y' lists containing the y values for plotting.

    Arguments:
        data(dict): the data dictionary with computed power model
    Raises:
        DictionaryKeysValidationFailed: if the data dictionary is missing any of the keys
    Return:
        dict: the data dictionary updated with 'plot_y'

    """
    # Validate the data dictionary
    tools.validate_dictionary_keys(data, ['plot_x', 'b0', 'b1'], [])

    # Compute the function value for every x value
    data['plot_y'] = np.array(data['b0'] * np.array(data['plot_x']) ** data['b1'])
    return data


def exp_model_plot(data):
    """ The exponential specific version for plot_y points computation.

    Expects 'plot_x', 'b0' and 'b1' keys in the data dictionary.

    Updates the data dictionary with 'plot_y' lists containing the y values for plotting.

    Arguments:
        data(dict): the data dictionary with computed exponential model
    Raises:
        DictionaryKeysValidationFailed: if the data dictionary is missing any of the keys
    Return:
        dict: the data dictionary updated with 'plot_y'

    """
    # Validate the data dictionary
    tools.validate_dictionary_keys(data, ['plot_x', 'b0', 'b1'], [])

    # Compute the function value for every x value
    data['plot_y'] = np.array(data['b0'] * data['b1'] ** np.array(data['plot_x']))
    return data
