"""Module with generic functions for regression analysis.

These generic functions are reusable parts of the regression computation.
All functions operate with one argument - the data dictionary that contains the required arguments.
All functions return the updated data dictionary.
This allows to extend and modify the computation process as long as all the functions follow
the given argument and return value conventions.

"""


import perun.postprocess.regression_analysis.tools as tools


def generic_compute_regression(input_data):
    """The core of the computation process.

    Computes the regression model according to the provided sequence of generator ('data_gen')
    and function list (func_list).

    Arguments:
        input_data(dict): the regression model dictionary from regression_model
        (e.g. the 'linear' section)
    Raises:
        GenericRegressionExceptionBase: the derived exceptions as used in the generator
                                        or function list
        DictionaryKeysValidationFailed: in case the data format dictionary is incorrect
    Return:
        iterable: generator object which produces regression model computation steps in a data
                  dictionary

    """
    # Get intermediate results from data generator
    for data in input_data['data_gen']:
        # Apply every function on the model data to compute all needed values
        for func in input_data['func_list']:
            data = func(data)
        yield data


def generic_regression_data(data):
    """The generic data generator.

    Produces the sums of x, y, square x, square y and x * y values. Also provides the x min/max
    values and the number of points.
    Expects 'x', 'y', 'fx', 'fy' and 'steps' keys in data dictionary. 'fx' and 'fy' refer to the x
    and y values modification for the sums (e.g. log10 for x values => sum of log10(x) values).
    The steps key allows to split the points sequence into parts (for iterative computation),
    where each part continues the computation (the part contains results from the previous).
    Updates the data dictionary with 'x_sum', 'y_sum', 'xy_sum', 'x_sq_sum', 'y_sq_sum', 'len',
    'x_min' and 'x_max' keys.

    Arguments:
        data(dict): the initialized data dictionary
    Raises:
        GenericRegressionExceptionBase: the derived exceptions
        DictionaryKeysValidationFailed: in case the data format dictionary is incorrect
    Return:
        iterable: generator object which produces intermediate results for each computation step
                  in a data dictionary

    """
    tools.validate_dictionary_keys(data, ['x', 'y', 'fx', 'fy', 'steps'], [])

    # We also need the min and max values
    x_min = data['x'][0]
    x_max = data['x'][0]

    # Compute the sums of x, y, x^2, y^2 and x*y
    x_sum, y_sum, x_square_sum, y_square_sum, xy_sum = 0.0, 0.0, 0.0, 0.0, 0.0
    # Split the computation into specified steps
    for part_start, part_end in tools.split_sequence(len(data['x']), data['steps']):
        skipped = 0
        for x_pt, y_pt in zip(data['x'][part_start:part_end], data['y'][part_start:part_end]):

            # Account for possible domain errors with fx and fy functions, simply skip the point
            try:
                x_tmp = data['fx'](x_pt)
                y_tmp = data['fy'](y_pt)
            except ValueError:
                skipped += 1
                continue

            # Compute the intermediate results
            x_sum += x_tmp
            y_sum += y_tmp
            x_square_sum += data['fx'](x_pt) ** 2
            y_square_sum += data['fy'](y_pt) ** 2
            xy_sum += data['fx'](x_pt) * data['fy'](y_pt)

            # Check the min and max
            x_min, x_max = min(x_min, x_pt), max(x_max, x_pt)

        # Computation step is complete, save the data
        data['x_sum'] = x_sum
        data['y_sum'] = y_sum
        data['xy_sum'] = xy_sum
        data['x_sq_sum'] = x_square_sum
        data['y_sq_sum'] = y_square_sum
        data['len'] = part_end - skipped
        data['x_min'] = x_min
        data['x_max'] = x_max
        yield data


def generic_regression_coefficients(data):
    """The generic function for coefficients computation.

    The function uses the general coefficient computation formula, which produces two coefficients
    based on the intermediate results from the data generator.
    Expects 'x_sum', 'y_sum', 'xy_sum', 'x_sq_sum', 'len', 'fa', 'fb' keys in data dictionary. The
    'fa' and 'fb' keys refer to the coefficients modification function (similar to the 'fx' and
    'fy'), which is applied after the coefficients are computed.
    Updates the data dictionary with 'coeffs' key containing the coefficients list in descending
    order.

    Arguments:
        data(dict): the data dictionary with intermediate results
    Raises:
        DictionaryKeysValidationFailed: in case the data format dictionary is incorrect
    Return:
        dict: the data dictionary updated with coefficients

    """
    tools.validate_dictionary_keys(data,
                                   ['fa', 'fb', 'x_sum', 'y_sum', 'xy_sum', 'x_sq_sum', 'len'], [])

    # Compute the coefficients
    s_xy = data['xy_sum'] - data['x_sum'] * data['y_sum'] / data['len']
    s_xx = data['x_sq_sum'] - (data['x_sum'] ** 2) / data['len']
    b1 = s_xy / s_xx
    b0 = (data['y_sum'] - b1 * data['x_sum']) / data['len']

    # Apply the modification functions on the coefficients and save them
    data['coeffs'] = []
    data['coeffs'].append(data['fb'](b1))
    data['coeffs'].append(data['fa'](b0))
    return data


def generic_regression_error(data):
    """The generic function for error (r^2) computation.

    This function computes the error using the general formula.
    Expects 'x', 'y', 'y_sum', 'y_sq_sum', 'len', 'coeffs' keys in the data dictionary.
    Updates the dictionary with 'r_square' value representing the model error.

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

    # Compute the error
    sse = data['y_sq_sum'] - data['coeffs'][1] * data['y_sum'] - data['coeffs'][0] * data['xy_sum']
    sst = data['y_sq_sum'] - (data['y_sum'] ** 2) / data['len']
    data['r_square'] = tools.r_square_safe(sse, sst)
    return data
