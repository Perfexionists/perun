"""View package contains visualization and interfaces of the perun.

View contains two main interfaces of the perun pcs: 1) CLI for working with pcs from command line
and 2) GUI for more lightweight experience of perun using the kivy multiplatform solution.
"""

from perun.utils import dynamic_module_function_call

__author__ = 'Tomas Fiedor'


def show(show_type, *args, **kwargs):
    """
    Arguments:
        show_type(str): type of the show format
        args(list): list of positional arguments
        kwargs(dict): dictionary of keyword arguments
    """
    pass
    dynamic_module_function_call('perun.view', show_type, 'show', *args, **kwargs)