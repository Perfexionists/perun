""" Module used for visualization of computed regression data. The matplotlib is used as a plotting environment. """

import matplotlib.pyplot as plot
import math

# Coefficient for proper plot limits scaling
_PLOT_AXES_RESERVE = 0.11
# Coefficient for correct annotation position
_ANNOTATION_OFFSET_COEFFICIENT = 0.02
# The actual computed annotation offset
_ANNOTATION_OFFSET = 0

# The font used for plot labels, for more info about possible values visit matplotlib docs
_FONT = {
    'family': 'serif',
    'color': 'black',
    'weight': 'normal',
    'size': 13
}


def visualize_regression(regression_data, description, colored_annotations=False, error_bars=None):
    """ Creates new pyplot figure with visualized regression data. Data points are visualized as a scatter
        plot, the estimated dependencies according to their regression model (line, parabole ...). Each chunk in
        the regression data has a label indicating the estimated regression function and its determination coefficient.

    Arguments:
        regression_data(namedtuple): the RegressionData namedtuple containing the regression results
        description(str): the description of visualized data and plot
        colored_annotations(bool): if true, the annotations text color will match the plotted function color
        error_bars(str): sets the error bars format
                         None - no error bars will be shown,
                         'a' - the average error bar will be shown for all regression data points
                         'p' - the precise error bar will be shown for every regression data point
    """
    # Prepare the plot figure, its description, axes labels, axes scale and annotation scales
    plot.figure()
    plot.title(description)
    plot.xlabel('Structure size (n)')
    plot.ylabel('Operation duration (s)')
    _scale_figure(regression_data.x_min, regression_data.x_max, regression_data.y_min, regression_data.y_max)
    _scale_annotation_offset(regression_data.y_min, regression_data.y_max)

    # Create the data points scatter plot
    visualize_points(regression_data.points)

    # Plot all chunks in the regression_data according to their regression model
    for chunk in regression_data.chunks:
        if type(chunk).__name__ == 'LineData':
            # The regression model of the chunk is a line
            _process_line(chunk, colored_annotations, error_bars)
    plot.show()


def visualize_points(points):
    """ Plots all data points as a scatter plot

    Arguments:
        points(list): the data points as a list of (x, y) tuples
    """
    x_pts, y_pts = zip(*points)
    plot.scatter(x_pts, y_pts, color='r')


def visualize_line(line_data, error_bar=None):
    """ Plots the regression line

    Arguments:
        line_data(namedtuple): the LineData namedtuple containing info about the regression line
        error_bar(str): sets the error bars format
                        None - no error bars will be shown,
                        'a' - the average error bar will be shown for all regression data points
                        'p' - the precise error bar will be shown for every regression data point

    Returns:
        Line2D: the plotted line data or None if the error bar is incorrectly specified
    """
    if error_bar is None:
        plotted = _plot_line_error_none(line_data)
    elif error_bar == 'a':
        plotted = _plot_line_error_avg(line_data)
    elif error_bar == 'p':
        plotted = _plot_line_error_precise(line_data)
    else:
        plotted = None
    return plotted


def annotate_chunk(label, x_coords, color=_FONT['color']):
    """ Annotates the chunk with the given label in the bottom center part of the chunk

    Arguments:
        label(str): the label used for the annotation
        x_coords(list): the chunk edge x coordinates [x_min, x_max]
        color(str): the color used for the annotation text
    """
    y_min, y_max = plot.ylim()
    label_x = x_coords[0] + ((x_coords[-1] - x_coords[0]) / 2)
    plot.text(label_x, y_min + _ANNOTATION_OFFSET, label, fontdict=_FONT, ha='center', color=color)


def _scale_figure(x_min, x_max, y_min, y_max):
    """ Scales the plot axes to provide enough space for all plotted objects

    Arguments:
        x_min(float): the minimum x value across all points
        x_max(float): the maximum x value across all points
        y_min(float): the minimum y value across all points
        y_max(float): the maximum y value across all points
    """
    # The x and y axes enlargement
    x_reserve = (x_max - x_min) * _PLOT_AXES_RESERVE
    y_reserve = (y_max - y_min) * _PLOT_AXES_RESERVE
    plot.xlim(x_min - x_reserve, x_max + x_reserve)
    plot.ylim(y_min - y_reserve * 2, y_max + y_reserve)


def _scale_annotation_offset(y_min, y_max):
    """ Scales the annotation label offset to display the annotations correctly

    Arguments:
        y_min(float): the minimum y value across all points
        y_max(float): the maximum y value across all points
    """
    # Infer the annotation labels offset
    global _ANNOTATION_OFFSET
    _ANNOTATION_OFFSET = (y_max - y_min) * _ANNOTATION_OFFSET_COEFFICIENT


def _process_line(chunk, colored, error_bars):
    """ Plots the line and its annotation

    Arguments:
        chunk(namedtuple): the regression_data chunk which is fitted by a linear model
        colored(bool): if true, the annotation text color will match the plotted line color
        error_bars(str): sets the error bars format
                         None - no error bars will be shown,
                         'a' - the average error bar will be shown for all regression data points
                         'p' - the precise error bar will be shown for every regression data point
    """
    # Plot the linear model itself
    line = visualize_line(chunk, error_bars)

    # Create the chunk annotation
    label = _create_line_annotation_label(chunk.b0, chunk.b1, chunk.r_square)
    if colored:
        annotate_chunk(label, [chunk.points[0][0], chunk.points[-1][0]], line.get_color())
    else:
        annotate_chunk(label, [chunk.points[0][0], chunk.points[-1][0]])


def _create_line_annotation_label(b0, b1, r_square):
    """ Builds the annotation string label for line

    Arguments:
        b0(float): the b0 coefficient of line formula
        b1(float): the b1 coefficient of line formula
        r_square(float): the coefficient of determination value for the given line

    Returns:
        str: the created label string
    """
    # Set the label formula sign
    if b1 < 0:
        sign = '-'
    else:
        sign = '+'
    # Build the actual label
    return '$y = {0:.2f} {1} {2:.2f}x$\n$r^{{2}} = {3:.2f}$'.format(b0, sign, abs(b1), r_square)


def _plot_line_error_none(line_data):
    """ Plots the specified line without error bars

    Arguments:
        line_data(namedtuple): The LineData namedtuple with the computed regression line

    Returns:
        Line2D: the plotted line data
    """
    # Get the edge x, y values of the regression line
    x_points = [line_data.points[0][0], line_data.points[-1][0]]
    y_points = [line_data.b0 + line_data.b1 * x_points[0], line_data.b0 + line_data.b1 * x_points[1]]

    line = plot.plot(x_points, y_points)
    return line[0]


def _plot_line_error_avg(line_data):
    """ Plots the specified line with average error bars for every data point

    Arguments:
        line_data(namedtuple): The LineData namedtuple with the computed regression line

    Returns:
        Line2D: the plotted line data
    """
    # Compute the average error from the sum of squares
    avg_error = math.sqrt(line_data.sse / len(line_data.points))
    # Get the error bars plotting position
    x_pts, f_x = [], []
    for point in line_data.points:
        x_pts.append(point[0])
        f_x.append(line_data.b0 + line_data.b1 * point[0])

    # Plot the line and error bars
    line = plot.errorbar(x_pts, f_x, yerr=avg_error, capsize=0)
    return line[0]


def _plot_line_error_precise(line_data):
    """ Plots the specified line with exact error bars for each data point

    Arguments:
        line_data(namedtuple): The LineData namedtuple with the computed regression line

    Returns:
        Line2D: the plotted line data
    """
    # Get the exact error value for every data point
    x_pts, f_x, err_neg, err_pos = [], [], [], []
    for point in line_data.points:
        x_pts.append(point[0])
        f_x.append(line_data.b0 + line_data.b1 * point[0])
        diff = point[1] - f_x[-1]
        # Specify the error bar direction (up/down) based on the error value sign
        if diff < 0:
            err_neg.append(abs(diff))
            err_pos.append(0)
        else:
            err_neg.append(0)
            err_pos.append(diff)

    # Plot the line and exact error bars
    line = plot.errorbar(x_pts, f_x, yerr=[err_neg, err_pos], capsize=0)
    return line[0]
