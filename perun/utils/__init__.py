"""Utils contains helper modules, that are not directly dependent on pcs.

Utils contains various helper modules and functions, that can be used in arbitrary projects, and
are not specific for perun pcs, like e.g. helper decorators, logs, etc.
"""

import importlib
import subprocess

from .log import msg_to_stdout, error
from .exceptions import UnsupportedModuleException, UnsupportedModuleFunctionException

__author__ = 'Tomas Fiedor'


def run_external_command(cmd_args):
    """
    Arguments:
        cmd_args(list): list of external command and its arguments to be run

    Returns:
        bool: return value of the external command that was run
    """
    process = subprocess.Popen(cmd_args)
    process.wait()
    return process.returncode


def get_stdout_from_external_command(command):
    """
    Arguments:
        command(list): list of arguments for command

    Returns:
        str: string representation of output of command
    """
    output = subprocess.check_output([c for c in command if c is not ''], stderr=subprocess.STDOUT)
    return output.decode('utf-8')


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
    # Simply pass these exceptions higher however with different flavours:
    # 1) When Import Error happens, this means, that some module is not found in Perun hierarchy,
    #   hence, we are trying to call some collector/visualizer/postprocessor/vcs, which is not
    #   implemented in Perun.
    #
    # 2) When Attribute Error happens, this means, that we have found supported module, but, there
    #   is some functionality, that is missing in the module.
    #
    # Why reraise the exceptions? Because it is up to the higher levels to catch these exceptions
    # and handle the errors their way. It should be different in CLI and in GUI, and they should
    # be caught in right places.
    except ImportError:
        raise UnsupportedModuleException(module_name)
    except AttributeError:
        raise UnsupportedModuleFunctionException(fun_name, function_location_path)


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


def get_supported_module_names(package):
    """Obtains list of supported modules supported by the package.

    Contains the hard-coded dictionary of packages and their supported values. This simply does
    a key lookup and returns the list of supported values.

    This was originally dynamic collection of all the modules through beautiful module iteration,
    which was shown to be completely uselessly slow than this hardcoded table. Since I assume, that
    new modules will be registered very rarely, I think it is ok to have it implemented like this.

    Arguments:
        package(str): name of the package for which we want to obtain the supported modules
          one of ('vcs', 'collect', 'postprocess')

    Returns:
        list: list of names of supported modules for the given package
    """
    assert package in ('vcs', 'collect', 'postprocess', 'view')
    return {
        'vcs': ['git'],
        'collect': ['complexity', 'memory', 'time'],
        'postprocess': ['filter', 'normalizer', 'regression_analysis'],
        'view': ['alloclist', 'bars', 'flamegraph', 'flow', 'heapmap', 'raw', 'scatter']
    }[package]


def merge_dictionaries(lhs, rhs):
    """Helper function for merging two dictionaries to one to be used as oneliner.

    Arguments:
        lhs(dict): left operand of the dictionary merge
        rhs(dict): right operand of the dictionary merge

    Returns:
        dict: merged dictionary of the lhs and rhs
    """
    res = lhs.copy()
    res.update(rhs)
    return res


def merge_dict_range(*args):
    """Helper function for merging range (list, ...) of dictionaries to one to be used as oneliner.

    Arguments:
        args(dict): list of dictionaries

    Returns:
        dict: one merged dictionary
    """
    res = {}
    for dictionary in args:
        res.update(dictionary)
    return res
