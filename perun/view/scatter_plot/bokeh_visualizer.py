"""Bokeh visualizer module.

"""

import bokeh.plotting as plot
from bokeh.models import NumeralTickFormatter
import visualizer.tools as tools

# Current plotting figure
_fig = None


def set_figure(**kwargs):
    """Sets new bokeh plotting figure.

    Expects 'filename' key and optional bokeh figure arguments.

    """

    global _fig

    # Check the required argument
    tools.check_missing_arg(['filename'], kwargs)
    filename = kwargs.pop('filename')

    # Default kwargs values
    default_kwargs = {
        'x_axis_label': 'structure size (elements in the struct)',
        'y_axis_label': 'duration (\u00B5s)',
        'plot_width': 700,
        'plot_height': 350
    }
    default_kwargs.update(kwargs)
    kwargs = default_kwargs

    # Create the output file
    plot.output_file(filename)
    # Create the figure
    _fig = plot.figure(**kwargs)

    # Plot styling
    # Plot border
    _fig.outline_line_color = '#ececec'
    _fig.outline_line_width = 2

    # Plot title
    _fig.title.text_font_size = '14pt'
    _fig.title.text_color = '#374049'
    _fig.title.text_font = "helvetica"
    _fig.title.text_font_style = "italic"
    _fig.title.align = 'left'

    # Plot axis lines
    _fig.axis.axis_line_width = 3
    _fig.axis.axis_line_color = 'black'
    _fig.axis.axis_line_cap = 'round'

    # Plot axis ticks
    _fig.axis.minor_tick_line_color = 'black'
    _fig.axis.major_tick_line_color = "black"
    _fig.axis.major_tick_line_cap = "round"
    _fig.axis.major_tick_line_width = 1
    _fig.axis.major_tick_out = 7
    _fig.axis.major_tick_in = 4

    # Plot ticks labels
    _fig.axis.major_label_text_color = '#374049'
    _fig.axis.major_label_text_font = 'helvetica'
    _fig.axis.major_label_text_font_style = 'bold'
    _fig.axis.major_label_text_font_size = '11pt'

    # Plot axis labels
    _fig.axis.axis_label_text_font_size = '11pt'
    _fig.axis.axis_label_text_font_style = 'bold'
    _fig.axis.axis_label_text_color = '#374049'
    _fig.axis.axis_label_text_font = 'helvetica'

    # Plot grids
    _fig.grid.minor_grid_line_color = '#d3d3d3'
    _fig.grid.minor_grid_line_alpha = 0.6
    _fig.grid.minor_grid_line_dash = 'dotted'

    _fig.xaxis[0].formatter = NumeralTickFormatter(format="0,0")
    _fig.yaxis[0].formatter = NumeralTickFormatter(format="0,0")


def show_figure(**kwargs):
    """Displays the bokeh plotting figure.

    No arguments are required.

    """

    global _fig
    _fig.legend.location = "top_left"

    _fig.legend.label_text_font = "helvetica"
    _fig.legend.label_text_font_style = "italic"
    _fig.legend.label_text_color = "#374049"
    _fig.legend.label_text_font_size = "10.5pt"

    plot.show(_fig)


def plot_set_range(fig, min_y, max_y):
    """Sets the plotting area range of figure based on y limits.

    Arguments:
        fig(Figure): the bokeh figure to modify
        min_y(int): the minimum y value of plotting area
        max_y(int): the maximum y value of plotting area

    Returns:
        Figure: the updated figure object

    """

    # The range is already set better, do not change
    if fig.y_range.start is not None and fig.y_range.start < min_y and fig.y_range.end > max_y:
        return fig

    # Check each side
    start_delta, end_delta = False, False
    if fig.y_range.start is None or fig.y_range.start > min_y:
        fig.y_range.start = min_y
        start_delta = True
    if fig.y_range.end is None or fig.y_range.end < max_y:
        fig.y_range.end = max_y
        end_delta = True

    # Sets 5% blank space on each side if needed
    delta = (fig.y_range.end - fig.y_range.start) * 0.05
    if start_delta:
        fig.y_range.start -= delta
    if end_delta:
        fig.y_range.end += delta
    return fig


def plot_scatter(**kwargs):
    """Creates a scatter plot in the figure.

    Expects the 'x' and 'y' arguments with points coordinates and optional bokeh circle arguments.

    """

    global _fig

    # Check the arguments presence
    tools.check_missing_arg(['x', 'y'], kwargs)
    x = kwargs.pop('x')
    y = kwargs.pop('y')

    # Default kwargs values
    default_kwargs = {
        'legend': 'profiling data',
        'color': '#ff3c1a',
        'line_color': 'red',
        'size': 6,
        'line_width': 2,
        'line_alpha': 0.75,
        'fill_alpha': 0.25
    }
    default_kwargs.update(kwargs)
    kwargs = default_kwargs

    _fig.circle(x, y, **kwargs)
    # Set the y axis to proper dimensions
    data_start, data_end = min(y), max(y)
    plot_set_range(_fig, data_start, data_end)


def plot_model(**kwargs):
    """Plot the model based on a provided plot data.

    Expects 'x' and 'y' coordinates and optional bokeh line arguments.

    """

    global _fig

    # Check the required arguments
    tools.check_missing_arg(['x', 'y'], kwargs)
    x = kwargs.pop('x')
    y = kwargs.pop('y')

    # Default kwargs values
    default_kwargs = {
        'legend': 'model',
        'color': 'blue',
        'line_width': 2.5
    }
    default_kwargs.update(kwargs)
    kwargs = default_kwargs

    # Plot lines using the points
    _fig.line(x, y, **kwargs)


def plot_relative_comparison(**kwargs):
    """Plot the relative algorithm comparison with guideline.

    Expects 'x' and 'y' coordinates and optional bokeh line arguments

    """
    global _fig

    # Check the arguments presence
    tools.check_missing_arg(['x', 'y'], kwargs)
    x = kwargs.pop('x')
    y = kwargs.pop('y')

    # Default kwargs values
    default_kwargs = {
        'legend': 'algorithms relative time (\u00B5s) comparison',
        'color': '#ff3c1a',
        'line_color': 'red',
        'size': 6,
        'line_width': 2,
        'line_alpha': 0.75,
        'fill_alpha': 0.25
    }
    default_kwargs.update(kwargs)
    kwargs = default_kwargs

    _fig.circle(x, y, **kwargs)

    # Set x and y axis to form a proper square
    data_start, data_end = min(min(x), min(y)), max(max(x), max(y))
    delta = (data_end - data_start) * 0.05
    _fig.x_range.start = data_start - delta
    _fig.y_range.start = data_start - delta
    _fig.x_range.end = data_end + delta
    _fig.y_range.end = data_end + delta

    _fig.line(x=[0, data_end * 2], y=[0, data_end * 2], line_width=2.5, legend='guideline')
