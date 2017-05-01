"""Common interface for multiple visualizer modules.

The interface contains function for switching the visualisation module, setting up the figure,
displaying the figure, scatter plot and model plotting. The _visualizers dict contains specification
of appropriate functions for given visualizer.

Every interface function has only keyword arguments and the visualizer-specific functions handle the
specific arguments passed to the functions.

"""

import enum
import visualizer.bokeh_visualizer as bokeh_vis


class Visualizer(enum.Enum):
    """The currently supported visualizer modules"""
    bokeh = 'bokeh'


def switch_visualizer(visualizer):
    """Switches the currently used visualizer module.

    Arguments:
        visualizer(Visualizer): the new visualizer module to be used
    """
    global _active_visualizer
    _active_visualizer = _visualizers[visualizer.value]


def set_figure(**kwargs):
    """Sets new plotting figure."""
    _visualizers[_active_visualizer]['set_figure'](**kwargs)


def show_figure(**kwargs):
    """Shows the current plotting figure."""
    _visualizers[_active_visualizer]['show_figure'](**kwargs)


def plot_scatter(**kwargs):
    """Creates a scatter plot."""
    _visualizers[_active_visualizer]['plot_scatter'](**kwargs)


def plot_model(**kwargs):
    """Plots computed model."""
    _visualizers[_active_visualizer]['plot_model'](**kwargs)


# Currently used visualizer module
_active_visualizer = 'bokeh'

# Specification of visualizer properties
_visualizers = {
    'bokeh': {
        'set_figure': bokeh_vis.set_figure,
        'show_figure': bokeh_vis.show_figure,
        'plot_scatter': bokeh_vis.plot_scatter,
        'plot_model': bokeh_vis.plot_model
    }
}
