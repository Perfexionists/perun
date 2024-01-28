"""Module with generic functions for regression analysis.

These generic functions are reusable parts of the regression computation.

All functions operate on the data / model dictionaries, which are unpacked during the function call
 - this allows more readable function specifications and easier function calls.

All functions return or yield some form of data dictionary, which is then appended to the base
data dictionary.

This allows to extend and modify the computation process as long as all the functions follow
the given argument and return value conventions.

"""
from __future__ import annotations

# Standard Imports
from typing import Any, Iterable, Callable
import math

# Third-Party Imports

# Perun Imports
from perun.postprocess.regression_analysis import tools
from perun.utils.common import common_kit


def generic_compute_regression(
    data_gen: Iterable[dict[str, Any]],
    func_list: list[Callable[..., dict[str, Any]]],
    **model: Any,
) -> Iterable[dict[str, Any]]:
    """The core of the computation process.

    Computes the regression model according to the provided sequence of generator ('data_gen')
    and function list (func_list).

    :param iterable data_gen: generator object which provide computation values (sum of x etc.)
    :param list func_list: list of functions which are applied in order to the data from generator
    :param dict model: the regression model dictionary from regression_model (e.g. the 'linear'
        section)
    :raises GenericRegressionExceptionBase: the derived exceptions as used in the generator or
        function list
    :raises TypeError: if the required function arguments are not in the unpacked dictionary input
    :returns iterable: generator object which produces regression model computation steps in a data
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


def generic_regression_data(
    x_pts: list[float],
    y_pts: list[float],
    f_x: Callable[[float], float],
    f_y: Callable[[float], float],
    steps: int,
    **_: Any,
) -> Iterable[dict[str, float]]:
    """The generic data generator.

    Produces the sums of x, y, square x, square y and x * y values. Also provides the x min/max
    values and the number of points.

    'f_x' and 'f_y' refer to the x and y values modification for the sums (e.g. log10 for x values
    => sum of log10(x) values).

    The 'steps' allows to split the points sequence into parts (for iterative computation),
    where each part continues the computation (the part contains results from the previous).

    Yielded data dictionary contains 'x_sum', 'y_sum', 'xy_sum', 'x_sq_sum', 'y_sq_sum', 'pts_num',
    'num_sqrt', 'x_start' and 'x_end' keys.

    :param list x_pts: the list of x data points
    :param list y_pts: the list of y data points
    :param function f_x: function object for modification of x values (e.g. log10, **2, etc.) as
        specified by the model formula
    :param function f_y: function object for modification of y values (e.g. log10, **2, etc.) as
        specified by the model formula
    :param int steps: splits the data generation into specified steps
    :raises GenericRegressionExceptionBase: the derived exceptions
    :raises TypeError: if the required function arguments are not in the unpacked dictionary input
    :returns iterable: generator object which produces intermediate results for each computation
        step in a data dictionary
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
            x_square_sum += x_tmp**2
            y_square_sum += y_tmp**2
            xy_sum += x_tmp * y_tmp

            # Check the min and max
            x_min, x_max = min(x_min, x_pt), max(x_max, x_pt)

        # Computation step is complete, save the data
        pts_num = part_end - skipped
        data = dict(
            x_sum=x_sum,
            y_sum=y_sum,
            xy_sum=xy_sum,
            x_sq_sum=x_square_sum,
            y_sq_sum=y_square_sum,
            pts_num=pts_num,
            num_sqrt=math.sqrt(pts_num),
            x_start=x_min,
            x_end=x_max,
        )
        yield data


def generic_regression_coefficients(
    f_a: Callable[[float], float],
    f_b: Callable[[float], float],
    x_sum: float,
    y_sum: float,
    xy_sum: float,
    x_sq_sum: float,
    pts_num: int,
    num_sqrt: float,
    **_: Any,
) -> dict[str, list[float] | float]:
    """The generic function for coefficients computation.

    The function uses the general coefficient computation formula, which produces two coefficients
    based on the intermediate results from the data generator.

    The 'f_a' and 'f_b' refer to the coefficients modification function (similar to the 'f_x' and
    'f_y', e.g. 10**x for b0 coefficient => 10**(b0) coefficient value), which is applied after
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
            the formulas are transformed (->) to avoid computation with huge values,
            which can occur in models that use power of x / y values (e.g. power ...)

    The coefficients are further modified using the 'f_a' and 'f_b':
        b0 = f_a(b0)
        b1 = f_b(b1)

        e.g. b1 = log10(b1)

    :param function f_a: function object for modification of b0 coefficient (e.g. 10**x) as
        specified by the model formula
    :param function f_b: function object for modification of b1 coefficient (e.g. 10**x) as
        specified by the model formula
    :param float x_sum: sum of x points values
    :param float y_sum: sum of y points values
    :param float xy_sum: sum of x*y values
    :param float x_sq_sum: sum of x^2 values
    :param int pts_num: number of summed points
    :param float num_sqrt: square root of pts_num
    :raises TypeError: if the required function arguments are not in the unpacked dictionary input
    :returns dict: data dictionary with coefficients and intermediate results
    """
    # Compute the coefficients
    s_xy = xy_sum - common_kit.safe_division(x_sum, num_sqrt) * common_kit.safe_division(
        y_sum, num_sqrt
    )
    s_xx = x_sq_sum - (common_kit.safe_division(x_sum, num_sqrt) ** 2)

    b_1 = common_kit.safe_division(s_xy, s_xx)
    b_0 = common_kit.safe_division(y_sum - b_1 * x_sum, pts_num)

    # Apply the modification functions on the coefficients and save them
    return {"coeffs": [f_a(b_0), f_b(b_1)], "s_xy": s_xy, "s_xx": s_xx}


def generic_regression_error(
    s_xy: float, s_xx: float, y_sum: float, y_sq_sum: float, num_sqrt: float, **_: Any
) -> dict[str, float]:
    """The generic function for error (r^2) computation.

    Returns data dictionary with 'r_square' value representing the model error.

    This function computes the error using the general formula:
        r^2 = rss / tss where

            rss = (S_xy^2) / S_xx
            -> (S_xy / sqrt(S_xx))^2
            tss = SUM(y^2) - SUM(y)^2 / n
            -> SUM(y^2) - ((SUM(y) / sqrt(n)) ** 2)

            for x, y in range <0, n - 1> and S_xy, S_xx from coefficients computation

            the formulas are transformed (->) to avoid computation with huge values,
            which can occur in models that use power of x / y values (e.g. quad, power ...)

        RSS equals to the Regression sum of squares, alternatively Explained sum of squares.
        TSS corresponds to the Total sum of squares.

    :param float s_xy: intermediate value from coefficients computation
    :param float s_xx: intermediate value from coefficients computation
    :param float y_sum: sum of y values
    :param float y_sq_sum: sum of y^2 values
    :param float num_sqrt: square root of number of points summed
    :raises TypeError: if the required function arguments are not in the unpacked dictionary input
    :returns dict: data dictionary with error value, tss and rss results
    """
    # Compute the TSS
    tss = y_sq_sum - (common_kit.safe_division(y_sum, num_sqrt) ** 2)

    # Compute the RSS
    rss = common_kit.safe_division(s_xy, math.sqrt(s_xx)) ** 2

    # Compute the r^2
    r_square = common_kit.safe_division(rss, tss)

    # Save the data
    data = dict(rss=rss, tss=tss, r_square=r_square)

    return data
