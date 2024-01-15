"""Module that simply encapsulate all the random functions that are used in fuzzing,
with only one call of function from random package."""
from __future__ import annotations

# Standard Imports
from typing import Callable, Any
import random

# Third-Party Imports

# Perun Imports


def random_repeats(repeats: int) -> Callable[[Any], Any]:
    """Decorator for random number of repeats of inner function

    Note that the return value of the wrapped function is NOT checked or passed anywhere

    :param int repeats: the upper bound of number of repeats
    :return: decorator that takes function and repeats its call up to @p repeats times
    """

    def inner_wrapper(func: Callable[[Any], Any]) -> Callable[[Any], Any]:
        """Inner wrapper

        :param function func: wrapped function
        :return: innermost wrapper
        """

        def innermost_wrapper(*args: Any, **kwargs: Any) -> None:
            """Innermost wrapper

            :param list args: list of arguments
            :param dict kwargs: list of keyword arguments
            """
            for _ in range(rand_from_range(1, repeats)):
                func(*args, **kwargs)

        innermost_wrapper.__doc__ = func.__doc__
        return innermost_wrapper

    return inner_wrapper


def rand_from_range(start: int, stop: int) -> int:
    """Basic function that randomly choose an integer from range bounded by `start` and `stop`
    parameters. Mathematically expressed as `start` <= random_number <= `stop`.

    :param int start: lower bound of the interval
    :param int stop: upper limit of the interval
    :return int: random integer from given range
    """
    return random.randint(start, stop) if start != stop else start


def rand_index(lst_len: int) -> int:
    """Function that randomly choose an index from list.

    :param int lst_len: length of the list
    :return int: random integer that represents valid index of element in list
    """
    return rand_from_range(0, lst_len - 1)


def rand_choice(lst: list[Any]) -> Any:
    """Return a randomly selected element of a list.

    :param list lst: the list from which the element will be selected
    :return: element of list on random index
    """
    return lst[rand_from_range(0, len(lst) - 1)]
