"""Set of helper decorators used within the perun directory.

Contains decorators for enforcing certain conditions, like e.g. singleton-like return value of
the functions. Or various checker function, that checks given parameters of the functions.
"""

import inspect
import time

import termcolor

from perun.utils.exceptions import InvalidParameterException

__author__ = 'Tomas Fiedor'


def singleton(func):
    """
    Wraps the function @p func so it will always return the same result,
    as given by the first call. I.e. the singleton. No params are expected.

    :param function func: function that will be decorated
    :returns func: decorated function that will be run only once
    """
    func.instance = None
    registered_singletons.append(func)

    def wrapper():
        """Wrapper function of the @p func"""
        if func.instance is None:
            func.instance = func()
        return func.instance

    return wrapper
registered_singletons = []


def arguments_to_key(func, *args, **kwargs):
    """
    Transforms the real parameters of the @p func call, i.e. the combination
    of args and kwargs into unique key. Note that this has to be generic and
    accept various types of function combinations

    :param function func: function we are extracting parameters for
    :param list args: list of non keyword arguments
    :param dict kwargs: dictionary of keyword arguments
    :returns tuple: key usable for identification of called parameters
    """
    # positional, *, **, default for positional, keywords after *, keywords defaults
    f_args, _, _, f_defaults, _, f_kwonlydefaults, _ = inspect.getfullargspec(func)

    # get defaults that were updated
    f_defaults = f_defaults or []
    updated_defaults = list(f_defaults)
    number_of_updated_keyword_args = len(args) - (len(f_args) - len(f_defaults))
    if number_of_updated_keyword_args != 0:
        updated_defaults[:number_of_updated_keyword_args] = args[-number_of_updated_keyword_args:]
    keywords = f_args[-len(f_defaults):]

    # update the defaults with new values
    real_kwargs = f_kwonlydefaults.update(kwargs) if f_kwonlydefaults is not None else kwargs
    real_kwargs.update(zip(keywords, updated_defaults))

    # get the
    real_posargs = args[:len(f_args)-len(f_defaults)]

    return tuple(real_posargs) + tuple(real_kwargs.items())


def singleton_with_args(func):
    """
    Wraps the function @p func, so it will always return the same result,
    as givn by the first call with given positional and keyword arguments.

    :param function func: function that will be decorated
    :returns func: decorated function that will be run only once for give parameters
    """
    func_args_cache[func.__name__] = {}

    def wrapper(*args, **kwargs):
        """Wrapper function of the @p func"""
        key = arguments_to_key(func, *args, **kwargs)
        if key not in func_args_cache[func.__name__].keys():
            func_args_cache[func.__name__][key] = func(*args, **kwargs)
        return func_args_cache[func.__name__][key]

    return wrapper
func_args_cache = {}


def remove_from_function_args_cache(funcname):
    """Helper function for clearing the key from func args cache

    :param str funcname: function name that we are removing from the cache
    :return:
    """
    if funcname in func_args_cache.keys():
        func_args_cache[funcname].clear()


def validate_arguments(validated_args, validate, *args, **kwargs):
    """
    Validates the arguments stated by validated_args with validate function.
    Note that positional and kwarguments are not supported by this decorator

    :param list[str] validated_args: list of validated arguments
    :param function validate: function used for validation
    :param list args: list of additional positional arguments to validate function
    :param dict kwargs: dictionary of additional keyword arguments to validate function
    :returns func: decorated function for which given parameters will be validated
    """
    def inner_decorator(func):
        """Wrapper function of the @p func"""
        f_args, *_ = inspect.getfullargspec(func)

        def wrapper(*wargs, **wkwargs):
            """Wrapper function of the wrapper inner decorator"""
            params = list(zip(f_args[:len(wargs)], wargs)) + list(wkwargs.items())

            for param_name, param_value in params:
                if param_name not in validated_args:
                    continue
                if not validate(param_value, *args, **kwargs):
                    raise InvalidParameterException(param_value, param_name)

            return func(*wargs, **wkwargs)
        return wrapper

    return inner_decorator


def static_variables(**kwargs):
    """
    :param dict kwargs: keyword with static variables and their values
    :returns func: decorated function for which static variables are set
    """
    def inner_wrapper(func):
        """Inner wrapper of the function"""
        for key, value in kwargs.items():
            setattr(func, key, value)
        return func
    return inner_wrapper


def phase_function(phase_name):
    """Sets the phase name for the given function

    The phase name is outputed when the elapsed time is printed.

    :param str phase_name: name of the phase to which the given function corresponds
    :return: decorated function with new phase name
    """
    def inner_wrapper(func):
        """Inner wrapper of the decorated function

        :param function func: function we are decorating with its phase name
        :return: decorated function with new phase name
        """
        func.phase_name = phase_name
        return func
    return inner_wrapper


def print_elapsed_time(func):
    """Prints elapsed time after the execution of the wrapped function

    Takes the timestamp before the execution of the function and after the execution and prints
    the elapsed time to the standard output.

    :param function func: wrapped function
    :return: function for which we will print the elapsed time
    """
    def inner_wrapper(*args, **kwargs):
        """Inner wrapper of the decorated function

        :param list args: original arguments of the function
        :param dict kwargs: original keyword arguments of the function
        :return: results of the decorated function
        """
        before = time.time()
        results = func(*args, **kwargs)
        elapsed = time.time() - before
        print("[\u231A] {} [{}] in {} [\u231A]".format(
            (func.phase_name if hasattr(func, 'phase_name') else func.__name__).title(),
            termcolor.colored("DONE", 'green', attrs=['bold']),
            termcolor.colored("{:0.2f}s".format(elapsed), 'white', attrs=['bold'])
        ))
        return results
    return inner_wrapper
