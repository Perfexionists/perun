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
        key = tuple(args) + tuple(kwargs)
        if key not in func.cache.keys():
            func.cache[key] = func(*args, **kwargs)
        return func.cache[key]

    return wrapper
