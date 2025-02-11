"""Extension for regression model coefficients transformation into array of points. The points
array can be then used for model plotting as a series of lines forming a (curved) line.
"""

from __future__ import annotations

# Standard Imports
from typing import Callable, Any, Optional, TYPE_CHECKING

# Third-Party Imports
import numpy as np

# Perun Imports
from perun.postprocess.regression_analysis import tools

if TYPE_CHECKING:
    import numpy.typing as npt

# Default model curve smoothness specified as number of points generated from x interval
# The higher the value, the smoother the curves, the longer the computation tho.
# Default value is an empirically chosen compromise between speed and smoothness
DEFAULT_SMOOTHNESS: int = 51


def model_plot_computation(
    model_x: Callable[..., dict[str, Any]],
    model_y: Callable[..., dict[str, Any]],
    **data: Any,
) -> dict[str, Any]:
    """The model plotting computation wrapper.

    Handles required operations for all models, such as creating x and y plot points.
    The model specifics are handled by the 'model_x' and 'model_y' functions and other parameters.

    'model_x' is function object which computes the x points for plotting
    'model_y' is function object which computes the y points for plotting

    Creates data dictionary with 'plot_x' and 'plot_y' lists containing the model points
    for plotting.

    :param model_x: function for computation of x plot points
    :param model_y: function for computation of y plot points
    :param data: data dictionary with computed regression model
    :raises TypeError: if the required function arguments are not in the unpacked dictionary input
    :return: data dictionary with 'plot_x' and 'plot_y' points
    """
    # Build the x points from the x interval values, stored as 'plot_x'
    plot_data = model_x(**data)
    # Update the data for next computation
    data.update(plot_data)
    # Compute the function values for x points, stored as 'plot_y'
    plot_data.update(model_y(**data))

    return plot_data


def generic_plot_x_pts(
    x_start: int,
    x_end: int,
    smoothness: int = DEFAULT_SMOOTHNESS,
    transform_by: Callable[[Any], dict[str, Any]] = tools.as_plot_x_dict,
    **_: Any,
) -> dict[str, Any]:
    """Generic version of model x points computation.

    Splits the x interval of model into number of points.

    :param x_start: the left bound of the x interval
    :param x_end: the right bound of the x interval
    :param smoothness: number of points to produce from the interval
    :param transform_by: function for additional transformation of the resulting data
    :raises TypeError: if the required function arguments are not in the unpacked dictionary input
    :return: data dictionary with 'plot_x' array
    """
    # Produce number of points from the interval
    return transform_by(tools.split_model_interval(x_start, x_end, smoothness))


def generic_plot_y_pts(
    plot_x: npt.NDArray[np.float64],
    b0: float,
    b1: float,
    formula: Callable[[npt.NDArray[np.float64], float, float], list[float]],
    m_fx: Optional[Callable[[float], float]] = None,
    transform_by: Callable[[Any], dict[str, Any]] = tools.as_plot_y_dict,
    **_: Any,
) -> dict[str, Any]:
    """The generic function for y points computation.

    This function computes the y points for model plotting using the 'fp' formula.

    The 'm_fx' function modifies the value of point x according to the regression model if needed
    (e.g. x**2, log, ...).

    Creates data dictionary with 'plot_y' containing the y values for plotting.

    :param plot_x: array of x points
    :param b0: the b0 model coefficient
    :param b1: the b1 model coefficient
    :param formula: function object containing the computation formula
    :param m_fx: function object with x values modification
    :param transform_by: function for additional transformation of the resulting data
    :raises TypeError: if the required function arguments are not in the unpacked dictionary input
    :return: data dictionary with 'plot_y' array
    """
    # Modify the x points if needed
    if m_fx:
        f_x = np.vectorize(m_fx)
        plot_x = f_x(plot_x)
    # Apply the computation formula
    return transform_by(np.array(formula(plot_x, b0, b1)))


def quad_plot_y_pts(
    plot_x: npt.NDArray[np.float64],
    b0: float,
    b1: float,
    b2: float,
    formula: Callable[[npt.NDArray[np.float64], float, float, float], list[float]],
    transform_by: Callable[[Any], dict[str, Any]] = tools.as_plot_y_dict,
    **_: Any,
) -> dict[str, Any]:
    """The quadratic function for y points computation.

    This function computes the y points for model plotting using the 'fp' formula.

    The 'm_fx' function modifies the value of point x according to the regression model if needed
    (e.g. x**2, log, ...).

    Creates data dictionary with 'plot_y' containing the y values for plotting.

    :param plot_x: array of x points
    :param b0: the b0 model coefficient
    :param b1: the b1 model coefficient
    :param b2: the b2 model coefficient
    :param formula: function object containing the computation formula
    :param transform_by: function for additional transformation of the resulting data
    :raises TypeError: if the required function arguments are not in the unpacked dictionary input
    :return: data dictionary with 'plot_y' array
    """
    # Apply the computation formula
    return transform_by(np.array(formula(plot_x, b0, b1, b2)))
