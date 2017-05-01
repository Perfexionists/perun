"""Module with model-specific functions.

Not all models or their computation parts can be calculated using the generic functions.
This module contains the required specific versions for the models computation.

"""


import regression_analysis.tools as tools
import numpy as np


_approx_zero = 0.000001


def quad_regression_error(data):
    """The quadratic specific function for error computation.

    Expects 'x', 'y', 'y_sum', 'y_sq_sum', 'len', 'coeffs' keys in the data dictionary.
    Updates the dictionary with 'r_square' value representing the quadratic model error.

    Arguments:
        data(dict): the data dictionary with intermediate results and coefficients
    Raises:
        DataFormatMissingArgument: if the data dictionary is missing any of the keys
        DataFormatInvalidCoeffs: if the data dictionary has incorrect number of coefficients
    Return:
        dict: the data dictionary updated with error value

    """
    tools.check_missing_arg(['x', 'y', 'y_sum', 'y_sq_sum', 'len', 'coeffs'], data)
    tools.check_coeffs(2, data)

    # Compute the sse with specific quadratic model formula
    sse = 0
    for x_pt, y_pt in zip(data['x'][:data['len']], data['y'][:data['len']]):
        sse += (y_pt - (data['coeffs'][1] + data['coeffs'][0] * (x_pt ** 2))) ** 2
    sst = data['y_sq_sum'] - (data['y_sum'] ** 2) / data['len']
    data['r_square'] = 1 - sse / sst
    return data


def power_regression_error(data):
    """The power specific function for error computation.

    Expects 'x', 'y', 'len', 'coeffs' keys in the data dictionary.
    Updates the dictionary with 'r_square' value representing the power model error.

    Arguments:
        data(dict): the data dictionary with intermediate results and coefficients
    Raises:
        DataFormatMissingArgument: if the data dictionary is missing any of the keys
        DataFormatInvalidCoeffs: if the data dictionary has incorrect number of coefficients
    Return:
        dict: the data dictionary updated with error value

    """
    tools.check_missing_arg(['x', 'y', 'len', 'coeffs'], data)
    tools.check_coeffs(2, data)

    sse = 0.0
    y_sum, y_square_sum = 0.0, 0.0
    for x_pt, y_pt in zip(data['x'][:data['len']], data['y'][:data['len']]):
        # Computes the actual y and y square sums without the 'fy' modification
        y_sum += y_pt
        y_square_sum += y_pt ** 2
        # Compute the y and y_hat difference
        try:
            sse += (y_pt - (data['coeffs'][1] * (x_pt ** data['coeffs'][0]))) ** 2
        except ZeroDivisionError:
            # In case of power failure skip the calculation step
            continue
    sst = y_square_sum - (y_sum ** 2) / data['len']
    data['r_square'] = 1 - sse / sst
    return data


def exp_regression_error(data):
    """The exponential specific function for error computation.

    Expects 'x', 'y', 'len', 'coeffs' keys in the data dictionary.
    Updates the dictionary with 'r_square' value representing the exponential model error.

    Arguments:
        data(dict): the data dictionary with intermediate results and coefficients
    Raises:
        DataFormatMissingArgument: if the data dictionary is missing any of the keys
        DataFormatInvalidCoeffs: if the data dictionary has incorrect number of coefficients
    Return:
        dict: the data dictionary updated with error value

    """
    tools.check_missing_arg(['x', 'y', 'len', 'coeffs'], data)
    tools.check_coeffs(2, data)

    sse = 0
    y_sum, y_square_sum = 0.0, 0.0
    for x_pt, y_pt in zip(data['x'][:data['len']], data['y'][:data['len']]):
        # Computes the actual y and y square sums without the 'fy' modification
        y_sum += y_pt
        y_square_sum += y_pt**2
        # Compute the y and y_hat difference
        sse += (y_pt - (data['coeffs'][1] * (data['coeffs'][0] ** x_pt))) ** 2
    sst = y_square_sum - (y_sum ** 2) / data['len']
    data['r_square'] = 1 - sse / sst
    return data


def linear_plot_data(data):
    """The linear specific version for plotting points computation.

    This version is slightly more efficient for the plotting computation than the generic one.
    Expects 'x_min', 'x_max' and 'coeffs' keys in the data dictionary.
    Updates the data dictionary with 'plot_x' and 'plot_y' lists containing the plotting points

    Arguments:
        data(dict): the data dictionary with computed linear model
    Raises:
        DataFormatMissingArgument: if the data dictionary is missing any of the keys
        DataFormatInvalidCoeffs: if the data dictionary has incorrect number of coefficients
    Return:
        dict: the data dictionary updated with plotting points

    """
    tools.check_missing_arg(['x_min', 'x_max', 'coeffs'], data)
    tools.check_coeffs(2, data)

    # Split the x points into evenly distributed parts
    x = np.linspace(data['x_min'], data['x_max'], tools.PLOT_DATA_POINTS)
    # Compute the function value for every x value
    y = np.array(data['coeffs'][1] + data['coeffs'][0] * np.array(x))
    data['plot_x'] = x
    data['plot_y'] = y
    return data


def power_plot_data(data):
    """The power specific version for plotting points computation.

    Expects 'x_min', 'x_max' and 'coeffs' keys in the data dictionary.
    Updates the data dictionary with 'plot_x' and 'plot_y' lists containing the plotting points

    Arguments:
        data(dict): the data dictionary with computed power model
    Raises:
        DataFormatMissingArgument: if the data dictionary is missing any of the keys
        DataFormatInvalidCoeffs: if the data dictionary has incorrect number of coefficients
    Return:
        dict: the data dictionary updated with plotting points

    """
    tools.check_missing_arg(['x_min', 'x_max', 'coeffs'], data)
    tools.check_coeffs(2, data)

    # Split the x points into evenly distributed parts
    if data['x_min'] == 0:
        # Zero value might cause division by zero, approximate the zero
        x = np.linspace(_approx_zero, data['x_max'], tools.PLOT_DATA_POINTS)
    else:
        x = np.linspace(data['x_min'], data['x_max'], tools.PLOT_DATA_POINTS)
    # Compute the function value for every x value
    y = np.array(data['coeffs'][1] * np.array(x) ** data['coeffs'][0])
    data['plot_x'] = x
    data['plot_y'] = y
    return data


def exp_plot_data(data):
    """The exponential specific version for plotting points computation.

    Expects 'x_min', 'x_max' and 'coeffs' keys in the data dictionary.
    Updates the data dictionary with 'plot_x' and 'plot_y' lists containing the plotting points

    Arguments:
        data(dict): the data dictionary with computed exponential model
    Raises:
        DataFormatMissingArgument: if the data dictionary is missing any of the keys
        DataFormatInvalidCoeffs: if the data dictionary has incorrect number of coefficients
    Return:
        dict: the data dictionary updated with plotting points

    """
    tools.check_missing_arg(['x_min', 'x_max', 'coeffs'], data)
    tools.check_coeffs(2, data)

    # Split the x points into evenly distributed parts
    x = np.linspace(data['x_min'], data['x_max'], tools.PLOT_DATA_POINTS)
    # Compute the function value for every x value
    y = np.array(data['coeffs'][1] * data['coeffs'][0] ** np.array(x))
    data['plot_x'] = x
    data['plot_y'] = y
    return data
