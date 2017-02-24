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
    except ImportError as e:
        perun_log.msg_to_stdout(e, 2)
        perun_log.error("Unrecognized or unsupported VCS type '{}'".format(
            module_name
        ))
    except AttributeError as e:
        perun_log.msg_to_stdout(e, 2)
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


def walk_minor_versions(vcs_type, *args, **kwargs):
    """
    Arguments:
        vcs_type(str): type of the vcs that we are calling the function for
        args(list): list of non-keyword arguments
        kwargs(dict): dictionary of keyword arguments

    Returns:
        str: minor version sha-1 representation
    """
    perun_log.msg_to_stdout("Walking minor versions of type {}".format(
        vcs_type
    ), 1)
    return dynamic_module_function_call(
        'perun.core.vcs', vcs_type, '_walk_minor_versions', *args, **kwargs
    )


def walk_major_versions(vcs_type, *args, **kwargs):
    """
    Arguments:
        vcs_type(str): type of the vcs that we are calling the function for
        args(list): list of non-keyword arguments
        kwargs(dict): dictionary of keyword arguments

    Returns:
        str: major version representation
    """
    perun_log.msg_to_stdout("Walking major versions of type {}".format(
        vcs_type
    ), 1)
    return dynamic_module_function_call(
        'perun.core.vcs', vcs_type, '_walk_major_versions', *args, **kwargs
    )


def get_minor_version_info(vcs_type, *args, **kwargs):
    """
    Arguments:
        vcs_type(str): type of the vcs that we are calling the function for
        args(list): list of non-keyword arguments
        kwargs(dict): dictionary of keyword arguments

    Returns:
        MinorVersion: minor version named tuple for further process
    """
    perun_log.msg_to_stdout("Getting minor version info of type {} and args {}, {}".format(
        vcs_type, args, kwargs
    ), 1)
    return dynamic_module_function_call(
        'perun.core.vcs', vcs_type, '_get_minor_version_info', *args, **kwargs
    )


def get_head_major_version(vcs_type, *args, **kwargs):
    """
    Arguments:
        vcs_type(str): type of the vcs that we are calling the function for
        args(list): list of non-keyword arguments
        kwargs(dict): dictionary of keyword arguments

    Returns:
        str: identification of the major version
    """
    perun_log.msg_to_stdout("Getting head major version of type {}".format(
        vcs_type
    ), 1)
    return dynamic_module_function_call(
        'perun.core.vcs', vcs_type, '_get_head_major_version', *args, **kwargs
    )
