"""Module with model-specific functions.

Not all models or their computation parts can be calculated using the generic functions.
This module contains the required specific versions for the models computation.

"""


import perun.postprocess.regression_analysis.tools as tools


_approx_zero = 0.000001


def quad_regression_error(data):
    """The quadratic specific function for error computation.

    Expects 'x', 'y', 'y_sum', 'y_sq_sum', 'len', 'coeffs' keys in the data dictionary.
    Updates the dictionary with 'r_square' value representing the quadratic model error.

    Arguments:
        data(dict): the data dictionary with intermediate results and coefficients
    Raises:
        DictionaryKeysValidationFailed: in case the data format dictionary is incorrect
        InvalidCoeffsException: if the data dictionary has incorrect number of coefficients
    Return:
        dict: the data dictionary updated with error value

    """
    tools.validate_dictionary_keys(data, ['x', 'y', 'y_sum', 'y_sq_sum', 'len', 'coeffs'], [])
    tools.check_coeffs(2, data)

    # Compute the sse with specific quadratic model formula
    sse = 0
    for x_pt, y_pt in zip(data['x'][:data['len']], data['y'][:data['len']]):
        sse += (y_pt - (data['coeffs'][1] + data['coeffs'][0] * (x_pt ** 2))) ** 2
    sst = data['y_sq_sum'] - (data['y_sum'] ** 2) / data['len']
    # Account for possible zero division error
    try:
        data['r_square'] = 1 - sse / sst
    except ZeroDivisionError:
        data['r_square'] = 0.0
    return data


def power_regression_error(data):
    """The power specific function for error computation.

    Expects 'x', 'y', 'len', 'coeffs' keys in the data dictionary.
    Updates the dictionary with 'r_square' value representing the power model error.

    Arguments:
        data(dict): the data dictionary with intermediate results and coefficients
    Raises:
        DictionaryKeysValidationFailed: in case the data format dictionary is incorrect
        InvalidCoeffsException: if the data dictionary has incorrect number of coefficients
    Return:
        dict: the data dictionary updated with error value

    """
    tools.validate_dictionary_keys(data, ['x', 'y', 'len', 'coeffs'], [])
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
    # Account for possible zero division error
    try:
        data['r_square'] = 1 - sse / sst
    except ZeroDivisionError:
        data['r_square'] = 0.0
    return data


def exp_regression_error(data):
    """The exponential specific function for error computation.

    Expects 'x', 'y', 'len', 'coeffs' keys in the data dictionary.
    Updates the dictionary with 'r_square' value representing the exponential model error.

    Arguments:
        data(dict): the data dictionary with intermediate results and coefficients
    Raises:
        DictionaryKeysValidationFailed: in case the data format dictionary is incorrect
        InvalidCoeffsException: if the data dictionary has incorrect number of coefficients
    Return:
        dict: the data dictionary updated with error value

    """
    tools.validate_dictionary_keys(data, ['x', 'y', 'len', 'coeffs'], [])
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
    # Account for possible zero division error
    try:
        data['r_square'] = 1 - sse / sst
    except ZeroDivisionError:
        data['r_square'] = 0.0
    return data
