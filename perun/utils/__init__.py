"""Utils contains helper modules, that are not directly dependent on pcs.

Utils contains various helper modules and functions, that can be used in arbitrary projects, and
are not specific for perun pcs, like e.g. helper decorators, logs, etc.
"""

import importlib
import subprocess

from .log import msg_to_stdout, error

__author__ = 'Tomas Fiedor'


def run_external_command(cmd_args):
    """
    Arguments:
        cmd_args(list): list of external command and its arguments to be run

    Returns:
        bool: return value of the external command that was run
    """
    print("Running the following process: {}".format(cmd_args))
    process = subprocess.Popen(" ".join(cmd_args), shell=True)
    process.wait()
    return process.returncode


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
        module = get_module(function_location_path)
        module_function = getattr(module, fun_name)
        return module_function(*args, **kwargs)
    except ImportError as e:
        msg_to_stdout(e, 2)
        error("Unrecognized or unsupported VCS type '{}'".format(
            module_name
        ))
    except AttributeError as e:
        msg_to_stdout(e, 2)
        error("Function '{}' is unsupported in module {}".format(
            fun_name, function_location_path
        ))


def get_module(module_name):
    """
    Arguments:
        module_name(str): dynamically load a module (but first check the cache)

    Returns:
        module: loaded module
    """
    if module_name not in get_module.cache.keys():
        get_module.cache[module_name] = importlib.import_module(module_name)
    return get_module.cache[module_name]
get_module.cache = {}
