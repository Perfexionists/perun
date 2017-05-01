"""Bokeh visualizer module.

"""

import bokeh.plotting as plot
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
        'plot_width': 800,
        'plot_height': 800
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

    # Sets 5% blank space on each side
    delta = (max_y - min_y) * 0.05
    fig.y_range.start = min_y - delta
    fig.y_range.end = max_y + delta
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
