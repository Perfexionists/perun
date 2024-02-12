"""Set of helper decorators used within the perun directory.

Contains decorators for enforcing certain conditions, like e.g. singleton-like return value of
the functions. Or various checker function, that checks given parameters of the functions.
"""
from __future__ import annotations

# Standard Imports
from typing import Callable, Any
import functools
import inspect

# Third-Party Imports

# Perun Imports
from perun.utils.exceptions import InvalidParameterException


def _singleton_core(
    func: Callable[[], Any], is_always_singleton: bool, allow_manual_reset: bool = False
) -> Callable[[], Any]:
    """
    Wraps the function @p func, so it will always return the same result,
    as given by the first call. I.e. the singleton. No params are expected.

    :param func: any function that takes no parameters and returns single value
    :returns: decorated function that will be run only once
    """
    func.instance = None  # type: ignore
    if not is_always_singleton:
        registered_singletons.append(func)
    if is_always_singleton and allow_manual_reset:
        manual_registered_singletons[func.__name__] = func

    def wrapper() -> Any:
        """Wrapper function of the @p func"""
        if func.instance is None:  # type: ignore
            func.instance = func()  # type: ignore
        return func.instance  # type: ignore

    return wrapper


singleton = functools.partial(_singleton_core, is_always_singleton=False)
always_singleton = functools.partial(_singleton_core, is_always_singleton=True)
resetable_always_singleton = functools.partial(
    _singleton_core, is_always_singleton=True, allow_manual_reset=True
)
registered_singletons: list[Callable[[], Any]] = []
manual_registered_singletons: dict[str, Callable[[], Any]] = {}


def arguments_to_key(func: Callable[..., Any], *args: Any, **kwargs: Any) -> tuple[Any, ...]:
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
    f_defaults = f_defaults or ()
    updated_defaults = list(f_defaults)
    number_of_updated_keyword_args = len(args) - (len(f_args) - len(f_defaults))
    if number_of_updated_keyword_args != 0:
        updated_defaults[:number_of_updated_keyword_args] = args[-number_of_updated_keyword_args:]
    keywords = f_args[-len(f_defaults) :]

    # update the defaults with new values
    if f_kwonlydefaults is not None:
        f_kwonlydefaults.update(kwargs)
        real_kwargs = f_kwonlydefaults
    else:
        real_kwargs = kwargs
    real_kwargs.update(zip(keywords, updated_defaults))

    # get the
    real_posargs = args[: len(f_args) - len(f_defaults)]

    return tuple(real_posargs) + tuple(real_kwargs.items())


def singleton_with_args(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Wraps the function @p func, so it will always return the same result,
    as given by the first call with given positional and keyword arguments.

    :param function func: any function that takes parameters and returns value
    :returns func: decorated function that will be run only once for give parameters
    """
    func_args_cache[func.__name__] = {}

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        """Wrapper function of the @p func"""
        key = arguments_to_key(func, *args, **kwargs)
        if key not in func_args_cache[func.__name__].keys():
            func_args_cache[func.__name__][key] = func(*args, **kwargs)
        return func_args_cache[func.__name__][key]

    return wrapper


func_args_cache: dict[str, dict[tuple[Any, ...], Any]] = {}


def remove_from_function_args_cache(funcname: str) -> None:
    """Helper function for clearing the key from func args cache

    :param str funcname: function name that we are removing from the cache
    """
    if funcname in func_args_cache.keys():
        func_args_cache[funcname].clear()


def validate_arguments(
    validated_args: list[str], validate: Callable[..., bool], *args: Any, **kwargs: Any
) -> Callable[..., Any]:
    """
    Validates the arguments stated by validated_args with validate function.
    Note that positional and kwarguments are not supported by this decorator

    :param list[str] validated_args: list of validated arguments
    :param function validate: function used for validation
    :param list args: list of additional positional arguments to validate function
    :param dict kwargs: dictionary of additional keyword arguments to validate function
    :returns func: decorated function for which given parameters will be validated
    """

    def inner_decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        """Wrapper function of the @p func"""
        f_args, *_ = inspect.getfullargspec(func)

        def wrapper(*wargs: Any, **wkwargs: Any) -> Any:
            """Wrapper function of the wrapper inner decorator"""
            params = list(zip(f_args[: len(wargs)], wargs)) + list(wkwargs.items())

            for param_name, param_value in params:
                if param_name not in validated_args:
                    continue
                if not validate(param_value, *args, **kwargs):
                    raise InvalidParameterException(param_value, param_name)

            return func(*wargs, **wkwargs)

        return wrapper

    return inner_decorator


def static_variables(**kwargs: Any) -> Callable[..., Any]:
    """
    :param dict kwargs: keyword with static variables and their values
    :returns func: decorated function for which static variables are set
    """

    def inner_wrapper(func: Callable[..., Any]) -> Callable[..., Any]:
        """Inner wrapper of the function"""
        for key, value in kwargs.items():
            setattr(func, key, value)
        return func

    return inner_wrapper
