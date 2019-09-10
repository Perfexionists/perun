"""Module that simply encapsulate all the random functions that are used in fuzzing,
with only one call of function from random package."""

__author__ = 'Matus Liscinsky'

import random


def rand_from_range(start, stop):
    """Basic function that randomly choose an integer from range bounded by `start` and `stop`
    parameters. Matematically expressed as `start` <= random_number <= `stop`.

    :param int start: lower bound of the interval
    :param str pattern: upper limit of the interval
    :return int: random integer from given range
    """
    return random.randint(start, stop)


def rand_index(lst_len):
    """Function that randomly choose an index from list.

    :param int lst_len: length of the list
    :return int: random integer that represents valid index of element in list
    """
    return rand_from_range(0, lst_len-1)


def rand_choice(lst):
    """Return a randomly selected element of a list.

    :param list lst: the list from which the element will be selected
    :return: element of list on random index
    """
    return lst[rand_from_range(0, len(lst)-1)]