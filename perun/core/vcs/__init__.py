import perun.utils.log
import importlib
__author__ = 'Tomas Fiedor'
__brief__ = 'Data module consists of Version Control System wrappers and unified API'


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
        return module_function(args, kwargs)
    except ImportError:
        perun.utils.log.error("Unrecognized or unsupported VCS type '{}'".format(
            package_name
        ))
    except AttributeError:
        perun.utils.log.error("Function '{}' is unsupported in module {}".format(
            fun_name, function_location_path
        ))
        pass


def get_minor_head(vcs_type):
    """
    Arguments:
        vcs_type(str): type of the vcs that we are calling the function for

    Returns:
        str: unique representation of current head (usually SHA-1)
    """
    return dynamic_module_function_call('perun.core.vcs', vcs_type, '_get_minor_head')


def init(vcs_type, *args, **kwargs):
    """
    Arguments:
        vcs_type(str): type of the vcs that we are calling the function for
        args(list): list of non-keyword arguments
        kwargs(dict): dictionary of keyword arguments
    Returns:
        bool: true if the vcs was successfully initialized at vcs_path
    """
    return dynamic_module_function_call('perun.core.vcs', vcs_type, '_init', args, kwargs)

