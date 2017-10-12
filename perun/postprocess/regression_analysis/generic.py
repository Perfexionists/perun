"""Module with generic functions for regression analysis.

These generic functions are reusable parts of the regression computation.
All functions operate with one argument - the data dictionary that contains the required arguments.
All functions return the updated data dictionary.
This allows to extend and modify the computation process as long as all the functions follow
the given argument and return value conventions.

"""


import perun.postprocess.regression_analysis.tools as tools
from math import sqrt


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
    'len_sqrt', 'x_min' and 'x_max' keys.

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
            x_square_sum += x_tmp ** 2
            y_square_sum += y_tmp ** 2
            xy_sum += x_tmp * y_tmp

            # Check the min and max
            x_min, x_max = min(x_min, x_pt), max(x_max, x_pt)

        # Computation step is complete, save the data
        data['x_sum'] = x_sum
        data['y_sum'] = y_sum
        data['xy_sum'] = xy_sum
        data['x_sq_sum'] = x_square_sum
        data['y_sq_sum'] = y_square_sum
        data['len'] = part_end - skipped
        data['len_sqrt'] = sqrt(data['len'])
        data['x_min'] = x_min
        data['x_max'] = x_max
        yield data


def generic_regression_coefficients(data):
    """The generic function for coefficients computation.

    The function uses the general coefficient computation formula, which produces two coefficients
    based on the intermediate results from the data generator.
    Expects 'x_sum', 'y_sum', 'xy_sum', 'x_sq_sum', 'len', 'len_sqrt', 'fa', 'fb' keys in data
    dictionary. The 'fa' and 'fb' keys refer to the coefficients modification function (similar to
    the 'fx' and 'fy'), which is applied after the coefficients are computed.
    Updates the data dictionary with intermediate values 's_xx', 's_xy' and 'coeffs' key containing
    the coefficients list in descending order.

    The coefficients are computed using formula below:
        b0 = (SUM(y) - b1 * SUM(x)) / n

            for x, y in range <0, n - 1>

        b1 = S_xy / S_xx where

            S_xy = SUM(x * y) - (SUM(x) * SUM(y)) / n
            -> SUM(x * y) - (SUM(x) / sqrt(n)) * (SUM(y) / sqrt(n))
            S_xx = SUM(x^2) - SUM(x)^2 / n
            -> SUM(x^2) - (SUM(x) / sqrt(n))^2

            for x, y in range <0, n - 1>
            the formulas are transformed (->) to avoid computation with extremely big values,
            which can occur in models that use power of x / y values (e.g. quad, power ...)

    The coefficients are further modified using the 'fa' and 'fb':
        b0 = fa(b0)
        b1 = fb(b1)

        e.g. b1 = log10(b1)

    Arguments:
        data(dict): the data dictionary with intermediate results
    Raises:
        DictionaryKeysValidationFailed: in case the data format dictionary is incorrect
    Return:
        dict: the data dictionary updated with coefficients and intermediate results

    """
    tools.validate_dictionary_keys(
        data, ['fa', 'fb', 'x_sum', 'y_sum', 'xy_sum', 'x_sq_sum', 'len', 'len_sqrt'], [])

    # Compute the coefficients
    s_xy = data['xy_sum'] - (data['x_sum'] / data['len_sqrt']) * (data['y_sum'] / data['len_sqrt'])
    s_xx = data['x_sq_sum'] - ((data['x_sum'] / data['len_sqrt']) ** 2)
    try:
        b1 = s_xy / s_xx
    except ZeroDivisionError:
        b1 = s_xy / tools.APPROX_ZERO
    b0 = (data['y_sum'] - b1 * data['x_sum']) / data['len']

    # Apply the modification functions on the coefficients and save them
    data['coeffs'] = [data['fb'](b1), data['fa'](b0)]
    data['s_xy'] = s_xy
    data['s_xx'] = s_xx
    return data


def generic_regression_error(data):
    """The generic function for error (r^2) computation.

    Expects 's_xy', 's_xx', 'y_sum', 'y_sq_sum', 'len', 'len_sqrt', 'coeffs' keys in the data
    dictionary.
    Updates the dictionary with 'r_square' value representing the model error.

    This function computes the error using the general formula:
        r^2 = rss / tss where

            rss = (S_xy^2) / S_xx
            -> (S_xy / sqrt(S_xx))^2
            tss = SUM(y^2) - SUM(y)^2 / n
            -> SUM(y^2) - ((SUM(y) / sqrt(n)) ** 2)

            for x, y in range <0, n - 1> and S_xy, S_xx from coefficients computation

            the formulas are transformed (->) to avoid computation with extremely big values,
            which can occur in models that use power of x / y values (e.g. quad, power ...)

        RSS equals to the Regression sum of squares, alternatively Explained sum of squares.
        TSS corresponds to the Total sum of squares.

    Arguments:
        data(dict): the data dictionary with intermediate results and coefficients
    Raises:
        DictionaryKeysValidationFailed: in case the data format dictionary is incorrect
        InvalidCoeffsException: if the data dictionary has incorrect number of coefficients
    Return:
        dict: the data dictionary updated with error value

    """
    tools.validate_dictionary_keys(data, ['y_sum', 'y_sq_sum', 'len', 'coeffs'], [])
    tools.check_coeffs(2, data)

    # Compute the TSS
    tss = data['y_sq_sum'] - ((data['y_sum'] / data['len_sqrt']) ** 2)
    # Compute the RSS
    try:
        rss = (data['s_xy'] / sqrt(data['s_xx'])) ** 2
    except (ZeroDivisionError, ValueError):
        # s_xx or square root of s_xx is zero, approximate
        rss = (data['s_xy'] / tools.APPROX_ZERO) ** 2

    # Compute the r^2
    try:
        data['r_square'] = rss / tss
    except ZeroDivisionError:
        # Approximate 0 in TSS
        data['r_square'] = rss / tools.APPROX_ZERO

    return data
