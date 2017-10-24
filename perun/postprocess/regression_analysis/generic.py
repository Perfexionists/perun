"""Module with generic functions for regression analysis.

These generic functions are reusable parts of the regression computation.

All functions operate on the data / model dictionaries, which are unpacked during the function call
 - this allows more readable function specifications and easier function calls.

All functions return or yield some form of data dictionary, which is then appended to the base
data dictionary.

This allows to extend and modify the computation process as long as all the functions follow
the given argument and return value conventions.

"""

from math import sqrt
import perun.postprocess.regression_analysis.tools as tools


def generic_compute_regression(data_gen, func_list, **model):
    """The core of the computation process.

    Computes the regression model according to the provided sequence of generator ('data_gen')
    and function list (func_list).

    Arguments:
        data_gen(iterable): generator object which provide computation values (sum of x etc.)
        func_list(list): list of functions which are applied in order to the data from generator
        model(dict): the regression model dictionary from regression_model
        (e.g. the 'linear' section)
    Raises:
        GenericRegressionExceptionBase: the derived exceptions as used in the generator
                                        or function list
        TypeError: if the required function arguments are not in the unpacked dictionary input
    Return:
        iterable: generator object which produces regression model computation steps in a data
                  dictionary

    """
    # Get intermediate results from data generator
    for data in data_gen:
        # Update the data with model dictionary
        data.update(model)
        # Apply every function on the model data to compute all needed values
        for func in func_list:
            result = func(**data)
            data.update(result)
        yield data


def generic_regression_data(x_pts, y_pts, f_x, f_y, steps, **_):
    """The generic data generator.

    Produces the sums of x, y, square x, square y and x * y values. Also provides the x min/max
    values and the number of points.

    'f_x' and 'f_y' refer to the x and y values modification for the sums (e.g. log10 for x values
    => sum of log10(x) values).

    The 'steps' allows to split the points sequence into parts (for iterative computation),
    where each part continues the computation (the part contains results from the previous).

    Yielded data dictionary contains 'x_sum', 'y_sum', 'xy_sum', 'x_sq_sum', 'y_sq_sum', 'pts_num',
    'num_sqrt', 'x_interval_start' and 'x_interval_end' keys.

    Arguments:
        x_pts(list): the list of x data points
        y_pts(list): the list of y data points
        f_x(function): function object for modification of x values (e.g. log10, **2, etc.) as
                       specified by the model formula
        f_y(function): function object for modification of y values (e.g. log10, **2, etc.) as
                       specified by the model formula
        steps(int): splits the data generation into specified steps
    Raises:
        GenericRegressionExceptionBase: the derived exceptions
        TypeError: if the required function arguments are not in the unpacked dictionary input
    Return:
        iterable: generator object which produces intermediate results for each computation step
                  in a data dictionary

    """
    # We also need the min and max values
    x_min = x_pts[0]
    x_max = x_pts[0]

    # Compute the sums of x, y, x^2, y^2 and x*y
    x_sum, y_sum, x_square_sum, y_square_sum, xy_sum = 0.0, 0.0, 0.0, 0.0, 0.0
    # Split the computation into specified steps
    for part_start, part_end in tools.split_sequence(len(x_pts), steps):
        skipped = 0
        for x_pt, y_pt in zip(x_pts[part_start:part_end], y_pts[part_start:part_end]):

            # Account for possible domain errors with f_x and f_y functions, simply skip the point
            try:
                x_tmp = f_x(x_pt)
                y_tmp = f_y(y_pt)
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
        pts_num = part_end - skipped
        data = dict(
            x_sum=x_sum, y_sum=y_sum, xy_sum=xy_sum, x_sq_sum=x_square_sum,
            y_sq_sum=y_square_sum, pts_num=pts_num, num_sqrt=sqrt(pts_num),
            x_interval_start=x_min, x_interval_end=x_max
        )
        yield data


def generic_regression_coefficients(
        f_a, f_b, x_sum, y_sum, xy_sum, x_sq_sum, pts_num, num_sqrt, **_):
    """The generic function for coefficients computation.

    The function uses the general coefficient computation formula, which produces two coefficients
    based on the intermediate results from the data generator.

    The 'f_a' and 'f_b' refer to the coefficients modification function (similar to the 'f_x' and
    'f_y', e.g. 10**x for b0 coefficient => 10**(b0) coefficient value)), which is applied after
    the coefficients are computed.

    Returns the data dictionary with intermediate values 's_xx', 's_xy' and 'coeffs' key containing
    the coefficients list in ascending order.

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
            which can occur in models that use power of x / y values (e.g. power ...)

    The coefficients are further modified using the 'f_a' and 'f_b':
        b0 = f_a(b0)
        b1 = f_b(b1)

        e.g. b1 = log10(b1)

    Arguments:
        f_a(function): function object for modification of b0 coefficient (e.g. 10**x) as
                       specified by the model formula
        f_b(function): function object for modification of b1 coefficient (e.g. 10**x) as
                       specified by the model formula
        x_sum(float): sum of x points values
        y_sum(float): sum of y points values
        xy_sum(float): sum of x*y values
        x_sq_sum(float): sum of x^2 values
        pts_num(int): number of summed points
        num_sqrt(float): square root of pts_num
    Raises:
        TypeError: if the required function arguments are not in the unpacked dictionary input
    Return:
        dict: data dictionary with coefficients and intermediate results

    """
    # Compute the coefficients
    s_xy = xy_sum - (x_sum / num_sqrt) * (y_sum / num_sqrt)
    s_xx = x_sq_sum - ((x_sum / num_sqrt) ** 2)
    try:
        b1 = s_xy / s_xx
    except ZeroDivisionError:
        b1 = s_xy / tools.APPROX_ZERO
    b0 = (y_sum - b1 * x_sum) / pts_num

    # Apply the modification functions on the coefficients and save them
    data = dict(coeffs=[f_a(b0), f_b(b1)], s_xy=s_xy, s_xx=s_xx)
    return data


def generic_regression_error(s_xy, s_xx, y_sum, y_sq_sum, num_sqrt, **_):
    """The generic function for error (r^2) computation.

    Returns data dictionary with 'r_square' value representing the model error.

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
        s_xy(float): intermediate value from coefficients computation
        s_xx(float): intermediate value from coefficients computation
        y_sum(float): sum of y values
        y_sq_sum(float): sum of y^2 values
        num_sqrt(float): square root of number of points summed
    Raises:
        TypeError: if the required function arguments are not in the unpacked dictionary input
    Return:
        dict: data dictionary with error value, tss and rss results

    """
    # Compute the TSS
    tss = y_sq_sum - ((y_sum / num_sqrt) ** 2)
    # Compute the RSS
    try:
        rss = (s_xy / sqrt(s_xx)) ** 2
    except (ZeroDivisionError, ValueError):
        # s_xx or square root of s_xx is zero, approximate
        rss = (s_xy / tools.APPROX_ZERO) ** 2

    # Compute the r^2
    try:
        r_square = rss / tss
    except ZeroDivisionError:
        # Approximate 0 in TSS
        r_square = rss / tools.APPROX_ZERO

    # Save the data
    data = dict(rss=rss, tss=tss, r_square=r_square)

    return data
