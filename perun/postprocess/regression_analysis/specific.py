"""Module with model-specific computation functions.

Not all models or their computation parts can be calculated using the generic functions.
This module contains the required specific versions for the models computation.

"""
from __future__ import annotations

# Standard Imports
from typing import Any, Iterable

# Third-Party Imports

# Perun Imports
from perun.postprocess.regression_analysis import tools
from perun.utils.common import common_kit


def specific_quad_data(
    x_pts: list[float], y_pts: list[float], steps: int, **_: Any
) -> Iterable[dict[str, Any]]:
    """The quadratic data generator.

    Produces the sums of x, y, square x, x^3, x^4, square y, x * y and x^2 * y values.
    Also provides the x min/max values and the number of points.

    The 'steps' allows to split the points sequence into parts (for iterative computation),
    where each part continues the computation (the part contains results from the previous).

    Yielded data dictionary contains 'x_sum', 'y_sum', 'xy_sum', 'x_sq_sum', 'y_sq_sum',
    x_cube_sum, x4_sum, x_sq_y_sum, 'pts_num', 'x_start' and 'x_end' keys.

    :param list x_pts: the list of x data points
    :param list y_pts: the list of y data points
    :param int steps: splits the data generation into specified steps
    :raises GenericRegressionExceptionBase: the derived exceptions
    :raises TypeError: if the required function arguments are not in the unpacked dictionary input
    :returns iterable: generator object which produces intermediate results for each computation
        step in a data dictionary
    """
    # We also need the min and max values
    x_min = x_pts[0]
    x_max = x_pts[0]

    # Compute the sums of x, y, y^2, x^2, x^3, x^4, x * y and x^2 * y
    x_sum, y_sum, x_square_sum, x_cube_sum = 0.0, 0.0, 0.0, 0.0
    x4_sum, xy_sum, x_square_y_sum, y_square_sum = 0.0, 0.0, 0.0, 0.0
    # Split the computation into specified steps
    for part_start, part_end in tools.split_sequence(len(x_pts), steps):
        skipped = 0
        for x_pt, y_pt in zip(x_pts[part_start:part_end], y_pts[part_start:part_end]):
            # Compute the intermediate results
            x_sum += x_pt
            y_sum += y_pt
            y_square_sum += y_pt**2
            x_square_sum += x_pt**2
            x_cube_sum += x_pt**3
            x4_sum += x_pt**4
            xy_sum += x_pt * y_pt
            x_square_y_sum += (x_pt**2) * y_pt

            # Check the min and max
            x_min, x_max = min(x_min, x_pt), max(x_max, x_pt)

        # Computation step is complete, save the data
        pts_num = part_end - skipped
        data = {
            "x_sum": x_sum,
            "y_sum": y_sum,
            "xy_sum": xy_sum,
            "x_sq_sum": x_square_sum,
            "y_sq_sum": y_square_sum,
            "x_cube_sum": x_cube_sum,
            "x4_sum": x4_sum,
            "x_sq_y_sum": x_square_y_sum,
            "pts_num": pts_num,
            "x_start": x_min,
            "x_end": x_max,
        }
        yield data


def specific_quad_coefficients(
    x_sum: float,
    y_sum: float,
    xy_sum: float,
    x_sq_sum: float,
    x_cube_sum: float,
    x4_sum: float,
    x_sq_y_sum: float,
    pts_num: int,
    **_: Any,
) -> dict[str, list[float]]:
    """The quadratic specific function for coefficients computation.

    The function uses the specific coefficient computation formula, which produces three
    coefficients based on the intermediate results from the data generator.

    Returns the data dictionary with 'coeffs' containing the coefficients list in ascending order.

    The coefficients are computed using formula below:
        b0 = (SUM(y) - b1 * SUM(x) - b2 * SUM(x^2)) / n

            for x, y in range <0, n - 1>

        b1 = (S_xy * S_x2x2 - S_x2y * S_xx2) / (S_xx * S_x2x2 - S_xx2 * s_xx2),
        b2 = (S_x2y * S_xx - S_xy * s_xx2) / (S_xx * S_x2x2 - S_xx2 * S_xx2) where

            S_xx = SUM(x^2) - SUM(x)^2 / n
            S_xy = SUM(x * y) - (SUM(x) * SUM(y) / n)
            S_xx2 = SUM(x^3) - (SUM(x^2) * SUM(x) / n)
            S_x2y = SUM(x^2 * y) - (SUM(x^2) * SUM(y) / n)
            S_x2x2 = SUM(x^4) - (SUM(x^2)^2 / n)


    :param float x_sum: sum of x points values
    :param float y_sum: sum of y points values
    :param float xy_sum: sum of x*y values
    :param float x_sq_sum: sum of x^2 values
    :param float x_cube_sum: sum of x^3 values
    :param float x4_sum: sum of x^4 values
    :param float x_sq_y_sum: sum of x^2 * y values
    :param int pts_num: number of summed points
    :raises TypeError: if the required function arguments are not in the unpacked dictionary input
    :returns dict: data dictionary with coefficients and intermediate results
    """
    # Compute the intermediate values
    s_xx = x_sq_sum - (x_sum**2 / pts_num)
    s_xy = xy_sum - (x_sum * y_sum / pts_num)
    s_xx2 = x_cube_sum - (x_sq_sum * x_sum / pts_num)
    s_x2y = x_sq_y_sum - (x_sq_sum * y_sum / pts_num)
    s_x2x2 = x4_sum - ((x_sq_sum**2) / pts_num)
    det_m = s_xx * s_x2x2 - s_xx2**2

    # Compute the coefficients
    b_2 = (s_x2y * s_xx - s_xy * s_xx2) / det_m
    b_1 = (s_xy * s_x2x2 - s_x2y * s_xx2) / det_m
    b_0 = (y_sum - b_1 * x_sum - b_2 * x_sq_sum) / pts_num

    # Apply the modification functions on the coefficients and save them
    data = dict(coeffs=[b_0, b_1, b_2])
    return data


def specific_quad_error(
    coeffs: list[float],
    y_sum: float,
    y_sq_sum: float,
    xy_sum: float,
    x_sq_y_sum: float,
    pts_num: int,
    **_: Any,
) -> dict[str, float]:
    """The quadratic specific function for error (r^2) computation.

    Returns data dictionary with 'r_square' value representing the model error.

    This function computes the error using this specific formula:
        r^2 = 1 - sse / tss where

            rss = SUM(y^2) - b0 * SUM(y) - b1 * SUM(x * y) - b2 * SUM(x^2 * y)
            sse = SUM(y^2) - SUM(y)^2 / n

            for x, y in range <0, n - 1>

        SSE equals to the Residual sum of squares, alternatively sum of squared error.
        TSS corresponds to the Total sum of squares.

    :param list coeffs: list of computed coefficients in ascending order
    :param float y_sum: sum of y values
    :param float y_sq_sum: sum of y^2 values
    :param float xy_sum: sum of x*y values
    :param float x_sq_y_sum: sum of x^2 * y values
    :param int pts_num: number of summed points
    :raises TypeError: if the required function arguments are not in the unpacked dictionary input
    :returns dict: data dictionary with error value, tss and sse results
    """
    # Compute the TSS
    tss = y_sq_sum - ((y_sum**2) / pts_num)
    # Compute the RSS
    sse = y_sq_sum - coeffs[0] * y_sum - coeffs[1] * xy_sum - coeffs[2] * x_sq_y_sum

    # Compute the r^2
    r_square = 1 - common_kit.safe_division(sse, tss)

    # Save the data
    data = dict(sse=sse, tss=tss, r_square=r_square)

    return data
