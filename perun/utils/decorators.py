"""Set of helper decorators used within the perun directory.

Contains decorators for enforcing certain conditions, like e.g. singleton-like return value of
the functions. Or various checker function, that checks given parameters of the functions.
"""

import inspect

import perun.utils.exceptions as exceptions

__author__ = 'Tomas Fiedor'


def singleton(func):
    """
    Wraps the function @p func so it will always return the same result,
    as given by the first call. I.e. the singleton. No params are expected.

    Arguments:
        func(function): function that will be decorated

    Returns:
        func: decorated function that will be run only once
    """
    func.instance = None

    def wrapper():
        """Wrapper function of the @p func"""
        if func.instance is None:
            func.instance = func()
        return func.instance

    return wrapper


def arguments_to_key(func, *args, **kwargs):
    """
    Transforms the real parameters of the @p func call, i.e. the combination
    of args and kwargs into unique key. Note that this has to be generic and
    accept various types of function combinations

    Arguments:
        func(function): function we are extracting parameters for
        *args(list): list of non keyword arguments
        **kwargs(dict): dictionary of keyword arguments

    Returns:
        tuple: key usable for identification of called parameters
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
    Arguments:
        func(function): function that will be decorated

    Returns:
        func: decorated function that will be run only once for give parameters
    """
    func.cache = {}

    def wrapper(*args, **kwargs):
        """Wrapper function of the @p func"""
        key = arguments_to_key(func, *args, **kwargs)
        if key not in func.cache.keys():
            func.cache[key] = func(*args, **kwargs)
        return func.cache[key]

    return wrapper


def validate_arguments(validated_args, validate, *args, **kwargs):
    """
    Validates the arguments stated by validated_args with validate function.
    Note that positional and kwarguments are not supported by this decorator

    Arguments:
        validated_args(list[str]): list of validated arguments
        validate(function): function used for validation
        args(list): list of additional positional arguments to validate function
        kwargs(dict): dictionary of additional keyword arguments to validate function

    Returns:
        func: decorated function for which given parameters will be validated
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
                    error_msg = "Invalid value '{}' for parameter '{}'".format(
                        param_name, param_value
                    )
                    raise exceptions.InvalidParameterException(error_msg)

            return func(*wargs, **wkwargs)
        return wrapper

    return inner_decorator


def assume_version(version_spec, actual_version):
    """
    Arguments:
        version_spec(int): specification of the version that is checked
        actual_version(int): actual version that the given version supports/expects

    Returns:
        func: decorated function for which the version will be checked
    """
    def inner_wrapper(func):
        """Inner wrapper of the function"""
        def wrapper(*args, **kwargs):
            """Wrapper function of the @p func"""
            assert version_spec == actual_version and "function {} expects format version {}".format(
                func.__name__, version_spec
            )
            return func(*args, **kwargs)
        return wrapper
    return inner_wrapper


def static_variables(**kwargs):
    """
    Arguments:
        kwargs(dict): keyword with static variables and their values

    Returns:
        func: decorated function for which static variables are set
    """
    def inner_wrapper(func):
        """Inner wrapper of the function"""
        for key, value in kwargs.items():
            setattr(func, key, value)
        return func
    return inner_wrapper
