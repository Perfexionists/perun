""" Module for linear regression model computations. """

import collections
import tools


# Stores data about specific best fitting line
LineData = collections.namedtuple('LineData', [
    'points',           # the points used for the linear regression
    'x_sum',            # the sum of x values in points
    'y_sum',            # the sum of y values in points
    'x_square_sum',     # the sum of x^2 values
    'y_square_sum',     # the sum of y^2 values
    'xy_sum',           # the sum of x*y values
    'b0',               # the y-intercept of the line
    'b1',               # the slope value of the line
    'r_square',         # the coefficient of determination value
    'sse'               # the error sum of squares value
])


def new_line_data(points=None, x_sum=0, y_sum=0, x_square_sum=0, y_square_sum=0, xy_sum=0,
                  b0=0, b1=0, r_square=0, sse=0):
    """ Constructs new LineData namedtuple with default values

    Arguments:
        points(list): the points used for the linear regression, points should be sorted in ascending order
        x_sum(float): the sum of x values in points
        y_sum(float): the sum of y values in points
        x_square_sum(float): the sum of x^2 values
        y_square_sum(float): the sum of y^2 values
        xy_sum(float): the sum of x*y values
        b0(float): the y-intercept of the line
        b1(float): the slope value of the line
        r_square(float): the coefficient of determination value
        sse(float): the error sum of squares value

    Returns:
        namedtuple: the created LineData namedtuple
    """
    return LineData(points=points, x_sum=x_sum, y_sum=y_sum, x_square_sum=x_square_sum, y_square_sum=y_square_sum,
                    xy_sum=xy_sum, b0=b0, b1=b1, r_square=r_square, sse=sse)


def fit_lines(points, parts=1):
    """ Fits the linear model at the given points, which can be divided into more parts

    Arguments:
        points(list): the data points as a list of (x, y) tuples
        parts(int): the number of parts to divide the points into

    Returns:
        namedtuple: the RegressionData namedtuple with computed regression data or None if number of points is < 2
    """
    # Too few points
    if len(points) < 2:
        return None
    # Create the regression data
    reg_data = tools.process_profile_data(points)
    chunks = tools.split_to_chunks(reg_data.points, parts)

    # Fit the lines
    for chunk in chunks:
        line = compute_line_fit(chunk)
        reg_data.chunks.append(line)

    return reg_data


def compute_line_fit(points):
    """ Computes the best fitting line using the least squares method

    Arguments:
        points(list): input data as points in form of tuple list (x, y)

    Returns:
        namedtuple: the LineData named tuple with regression data
        None: if the number of points is lower than 2
    """
    # Too few points
    if len(points) < 2:
        return None
    # Prepare the line regression intermediate results
    line_data = _compute_line_points_data(points)
    # Compute the actual line
    line_data = _compute_line_coefficients(line_data)
    # Compute the error and determination coefficient
    line_data = _compute_line_determination(line_data)
    return line_data


def _compute_line_points_data(points):
    """ Computes the intermediate values used for linear regression

    Arguments:
        points(list): input data as points in form of tuple list (x, y)

    Returns:
        namedtuple: the LineData named tuple with intermediate results
        None: if the number of points is lower than 2
    """
    # Too few points
    if len(points) < 2:
        return None
    # Compute the sums of x, y, x^2, y^2 and x*y
    x_sum, y_sum, x_square_sum, y_square_sum, xy_sum = 0, 0, 0, 0, 0
    for x, y in points:
        x_sum += x
        y_sum += y
        x_square_sum += x ** 2
        y_square_sum += y ** 2
        xy_sum += x * y

    # Create new line data tuple to store the computations into
    line_data = new_line_data(points, x_sum, y_sum, x_square_sum, y_square_sum, xy_sum)
    return line_data


def _compute_line_coefficients(line_data):
    """ Computes the line b0 and b1 coefficients

    Arguments:
        line_data(namedtuple): the LineData with intermediate results

    Returns:
        namedtuple: the LineData named tuple with the regression line coefficients
        None: if the number of points is lower than 2
    """
    # Too few points
    if len(line_data.points) < 2:
        return None

    # The coefficients computation
    s_xy = line_data.xy_sum - line_data.x_sum * line_data.y_sum / len(line_data.points)
    s_xx = line_data.x_square_sum - (line_data.x_sum ** 2) / len(line_data.points)
    b1 = s_xy / s_xx
    b0 = (line_data.y_sum - b1 * line_data.x_sum) / len(line_data.points)

    # Updating the namedtuple
    # This is NOT a private method according to the docs, it just happens to use underscore to reduce name clashes
    return line_data._replace(b0=b0, b1=b1)


def _compute_line_determination(line_data):
    """ Computes the line determination coefficient and error sum of squares.
        This allows us to compare the quality of regression models for the given data set.

    Arguments:
        line_data(namedtuple): the LineData with line b0 and b1 coefficients

    Returns:
        namedtuple: the LineData named tuple with the regression line coefficients
        None: if the number of points is lower than 2
    """
    # Too few points
    if len(line_data.points) < 2:
        return None

    # The error and determination computation
    sse = line_data.y_square_sum - line_data.b0 * line_data.y_sum - line_data.b1 * line_data.xy_sum
    sst = line_data.y_square_sum - (line_data.y_sum ** 2) / len(line_data.points)
    r_square = 1 - sse / sst

    # Updating the namedtuple
    # This is NOT a private method according to the docs, it just happens to use underscore to reduce name clashes
    return line_data._replace(r_square=r_square, sse=sse)
