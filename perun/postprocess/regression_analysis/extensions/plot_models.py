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

    Arguments:
        model_x(function): function for computation of x plot points
        model_y(function): function for computation of y plot points
        data(dict): data dictionary with computed regression model
    Raises:
        TypeError: if the required function arguments are not in the unpacked dictionary input
    Return:
        dict: data dictionary with 'plot_x' and 'plot_y' points

    """
    # Build the x points from the x interval values, stored as 'plot_x'
    plot_data = model_x(**data)
    # Update the data for next computation
    data.update(plot_data)
    # Compute the function values for x points, stored as 'plot_y'
    plot_data.update(model_y(**data))

    return plot_data


def generic_plot_x_pts(x_interval_start, x_interval_end, smoothness=DEFAULT_SMOOTHNESS, return_dict=True, **_):
    """Generic version of model x points computation.

    Splits the x interval of model into number of points.

    Arguments:
        x_interval_start(int or float): the left bound of the x interval
        x_interval_end(int or float): the right bound of the x interval
        smoothness(int): number of points to produce from the interval
    Raises:
        TypeError: if the required function arguments are not in the unpacked dictionary input
    Returns:
        dict: data dictionary with 'plot_x' array
    """
    # Produce number of points from the interval
    plot_x = tools.split_model_interval(x_interval_start, x_interval_end, smoothness)
    if return_dict == True:
        return dict(plot_x=plot_x)
    return plot_x


def linear_plot_x_pts(x_interval_start, x_interval_end, return_dict=True, **_):
    """Specific version of model x points computation.

    Creates array with only the interval border values (i.e. [interval_start, interval_end])

    Arguments:
        x_interval_start(int or float): the left bound of the x interval
        x_interval_end(int or float): the right bound of the x interval
    Raises:
        TypeError: if the required function arguments are not in the unpacked dictionary input
    Returns:
        dict: data dictionary with 'plot_x' array
    """
    # Create simple two-value array
    plot_x = np.array([x_interval_start, x_interval_end])
    if return_dict == True:
        return dict(plot_x=plot_x)
    return plot_x


def generic_plot_y_pts(plot_x, b0, b1, formula, m_fx=None, return_dict=True, **_):
    """ The generic function for y points computation.

    This function computes the y points for model plotting using the 'fp' formula.

    The 'm_fx' function modifies the value of point x according to the regression model if needed
    (e.g. x**2, log, ...).

    Creates data dictionary with 'plot_y' containing the y values for plotting.

    Arguments:
        plot_x(numpy array): array of x points
        b0(float): the b0 model coefficient
        b1(float): the b1 model coefficient
        formula(function): function object containing the computation formula
        m_fx(function): function object with x values modification
    Raises:
        TypeError: if the required function arguments are not in the unpacked dictionary input
    Return:
        dict: data dictionary with 'plot_y' array

    """
    # Modify the x points if needed
    if m_fx:
        f_x = np.vectorize(m_fx)
        plot_x = f_x(plot_x)
    # Apply the computation formula
    plot_y = np.array(formula(b0, b1, plot_x))

    if return_dict:
        return dict(plot_y=plot_y)
    return plot_y


def quad_plot_y_pts(plot_x, b0, b1, b2, formula, return_dict=True, **_):
    """ The quadratic function for y points computation.

    This function computes the y points for model plotting using the 'fp' formula.

    The 'm_fx' function modifies the value of point x according to the regression model if needed
    (e.g. x**2, log, ...).

    Creates data dictionary with 'plot_y' containing the y values for plotting.

    Arguments:
        plot_x(numpy array): array of x points
        b0(float): the b0 model coefficient
        b1(float): the b1 model coefficient
        b2(float): the b2 model coefficient
        formula(function): function object containing the computation formula
    Raises:
        TypeError: if the required function arguments are not in the unpacked dictionary input
    Return:
        dict: data dictionary with 'plot_y' array

    """
    # Apply the computation formula
    plot_y = np.array(formula(b0, b1, b2, plot_x))

    if return_dict:
        return dict(plot_y=plot_y)
    return plot_y
