"""Wrapper over version control systems used for generic lookup of the concrete implementations.

VCS module contains modules with concrete implementations of the wrappers over the concrete version
control systems. It tries to enforce simplicity and lightweight approach in an implementation of
the wrapper.

Inside the wrapper are defined function that are used for lookup of the concrete implementations
depending of the chosen type/module, like e.g. git, svn, etc.
"""

import importlib

import perun.utils.log as perun_log

__author__ = 'Tomas Fiedor'


def dynamic_module_function_call(package_name, module_name, fun_name, *args, **kwargs):
    """Dynamically calls the function from other package with given arguments

    Looks up dynamically the module of the @p module_name inside the @p package_name
    package and calls its function @p fun_name with positional *args and keyword
    **kwargs.

    In case the module or function is missing, error is returned and program ends
    TODO: Add dynamic checking for the possible malicious code

    Arguments:
        package_name(str): name of the package, where the function we are calling is
        module_name(str): name of the module, to which the function corresponds
        fun_name(str): name of the function we are dynamically calling
        args(list): list of non-keyword arguments
        kwargs(dict): dictionary of keyword arguments

    Returns:
        ?: whatever the wrapped function returns
    """
    try:
        function_location_path = ".".join([package_name, module_name])
        module = importlib.import_module(function_location_path)
        module_function = getattr(module, fun_name)
        return module_function(*args, **kwargs)
    except ImportError:
        perun_log.error("Unrecognized or unsupported VCS type '{}'".format(
            module_name
        ))
    except AttributeError:
        perun_log.error("Function '{}' is unsupported in module {}".format(
            fun_name, function_location_path
        ))


def get_minor_head(vcs_type, *args, **kwargs):
    """
    Arguments:
        vcs_type(str): type of the vcs that we are calling the function for
        args(list): list of non-keyword arguments
        kwargs(dict): dictionary of keyword arguments

    Returns:
        str: unique representation of current head (usually SHA-1)
    """
    return dynamic_module_function_call(
        'perun.core.vcs', vcs_type, '_get_minor_head', *args, **kwargs
    )


def init(vcs_type, *args, **kwargs):
    """
    Arguments:
        vcs_type(str): type of the vcs that we are calling the function for
        args(list): list of non-keyword arguments
        kwargs(dict): dictionary of keyword arguments
    Returns:
        bool: true if the vcs was successfully initialized at vcs_path
    """
    perun_log.msg_to_stdout("Initializing {} version control with params {} and {}".format(
        vcs_type, args, kwargs
    ), 1)
    return dynamic_module_function_call(
        'perun.core.vcs', vcs_type, '_init', *args, **kwargs
    )
