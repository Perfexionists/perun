import inspect

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
    f_args, f_varargs, f_varkw, f_defaults, _, f_kwonlydefaults, _ = inspect.getfullargspec(func)

    # get defaults that were updated
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
        key = arguments_to_key(func, *args, **kwargs)
        if key not in func.cache.keys():
            func.cache[key] = func(*args, **kwargs)
        return func.cache[key]

    return wrapper
