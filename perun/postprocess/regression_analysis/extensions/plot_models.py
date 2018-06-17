""" Extension for regression model coefficients transformation into array of points. The points
    array can be then used for model plotting as a series of lines forming a (curved) line.
"""

import perun.postprocess.regression_analysis.tools as tools
import numpy as np


# Default model curve smoothness specified as number of points generated from x interval
# The higher the value, the smoother the curves, the longer the computation tho.
# Default value is an empirically chosen compromise between speed and smoothness
DEFAULT_SMOOTHNESS = 51


def model_plot_computation(model_x, model_y, **data):
    """ The model plotting computation wrapper.

    Handles required operations for all models, such as creating x and y plot points.
    The model specifics are handled by the 'model_x' and 'model_y' functions and other parameters.

    'model_x' is function object which computes the x points for plotting
    'model_y' is function object which computes the y points for plotting

    Creates data dictionary with 'plot_x' and 'plot_y' lists containing the model points
    for plotting.

    :param function model_x: function for computation of x plot points
    :param function model_y: function for computation of y plot points
    :param dict data: data dictionary with computed regression model
    :raises TypeError: if the required function arguments are not in the unpacked dictionary input
    :returns dict: data dictionary with 'plot_x' and 'plot_y' points
    """
    # Build the x points from the x interval values, stored as 'plot_x'
    plot_data = model_x(**data)
    # Update the data for next computation
    data.update(plot_data)
    # Compute the function values for x points, stored as 'plot_y'
    plot_data.update(model_y(**data))

    return plot_data


def generic_plot_x_pts(x_interval_start, x_interval_end, smoothness=DEFAULT_SMOOTHNESS, **_):
    """Generic version of model x points computation.

    Splits the x interval of model into number of points.

    :param int or float x_interval_start: the left bound of the x interval
    :param int or float x_interval_end: the right bound of the x interval
    :param int smoothness: number of points to produce from the interval
    :raises TypeError: if the required function arguments are not in the unpacked dictionary input
    :returns dict: data dictionary with 'plot_x' array
    """
    # Produce number of points from the interval
    plot_x = tools.split_model_interval(x_interval_start, x_interval_end, smoothness)
    return dict(plot_x=plot_x)


def linear_plot_x_pts(x_interval_start, x_interval_end, **_):
    """Specific version of model x points computation.

    Creates array with only the interval border values (i.e. [interval_start, interval_end])

    :param int or float x_interval_start: the left bound of the x interval
    :param int or float x_interval_end: the right bound of the x interval
    :raises TypeError: if the required function arguments are not in the unpacked dictionary input
    :returns dict: data dictionary with 'plot_x' array
    """
    # Create simple two-value array
    plot_x = np.array([x_interval_start, x_interval_end])
    return dict(plot_x=plot_x)


def generic_plot_y_pts(plot_x, b0, b1, formula, m_fx=None, **_):
    """ The generic function for y points computation.

    This function computes the y points for model plotting using the 'fp' formula.

    The 'm_fx' function modifies the value of point x according to the regression model if needed
    (e.g. x**2, log, ...).

    Creates data dictionary with 'plot_y' containing the y values for plotting.

    :param numpy array plot_x: array of x points
    :param float b0: the b0 model coefficient
    :param float b1: the b1 model coefficient
    :param function formula: function object containing the computation formula
    :param function m_fx: function object with x values modification
    :raises TypeError: if the required function arguments are not in the unpacked dictionary input
    :returns dict: data dictionary with 'plot_y' array
    """
    # Modify the x points if needed
    if m_fx:
        f_x = np.vectorize(m_fx)
        plot_x = f_x(plot_x)
    # Apply the computation formula
    plot_y = np.array(formula(b0, b1, plot_x))

    return dict(plot_y=plot_y)


def quad_plot_y_pts(plot_x, b0, b1, b2, formula, **_):
    """ The quadratic function for y points computation.

    This function computes the y points for model plotting using the 'fp' formula.

    The 'm_fx' function modifies the value of point x according to the regression model if needed
    (e.g. x**2, log, ...).

    Creates data dictionary with 'plot_y' containing the y values for plotting.

    :param numpy array plot_x: array of x points
    :param float b0: the b0 model coefficient
    :param float b1: the b1 model coefficient
    :param float b2: the b2 model coefficient
    :param function formula: function object containing the computation formula
    :raises TypeError: if the required function arguments are not in the unpacked dictionary input
    :returns dict: data dictionary with 'plot_y' array
    """
    # Apply the computation formula
    plot_y = np.array(formula(b0, b1, b2, plot_x))

    return dict(plot_y=plot_y)
