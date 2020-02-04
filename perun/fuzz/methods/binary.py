"""Collects fuzzing rules specific for binary files."""

__author__ = 'Matus Liscinsky'

import os

import perun.fuzz.randomizer as randomizer
import perun.fuzz.helpers as helpers

RULE_ITERATIONS = 10


@randomizer.random_repeats(RULE_ITERATIONS)
def insert_byte(lines):
    """ Selects random line and inserts a random byte to any position.

    Example:
        Defenestration -> Def%enestration

    :param list lines: lines of the file in list
    """
    rand = randomizer.rand_index(len(lines))
    index = randomizer.rand_index(len(lines[rand]))
    byte = os.urandom(1)
    helpers.insert_at_split(lines, rand, index, byte)


@randomizer.random_repeats(RULE_ITERATIONS)
def remove_byte(lines):
    """ Selects random line and removes random byte.

    Example:
        #ef15ac -> ef15ac

    :param list lines: lines of the file in list
    """
    rand = randomizer.rand_index(len(lines))
    index = randomizer.rand_index(len(lines[rand]))
    helpers.remove_at_split(lines, rand, index)


@randomizer.random_repeats(RULE_ITERATIONS)
def byte_swap(lines):
    """ Selects two random lines and switch theirs random bytes.

    Example:
    before:
        Defenestration
        #ef15ac
    after:
        Def5nestration
        #ef1eac

    :param list lines: lines of the file in list
    """
    line_num1 = randomizer.rand_index(len(lines))
    line_num2 = randomizer.rand_index(len(lines))

    index1 = randomizer.rand_index(len(lines[line_num1]))
    index2 = randomizer.rand_index(len(lines[line_num2]))

    # converting to byte arrays to be able to modify
    ba1 = bytearray(lines[line_num1])
    ba2 = bytearray(lines[line_num2])

    # swap
    tmp = ba1[index1]
    ba1[index1] = ba2[index2]
    ba2[index2] = tmp

    lines[line_num1] = ba1
    lines[line_num2] = ba2


@randomizer.random_repeats(RULE_ITERATIONS)
def bit_flip(lines):
    """ Selects random line and flips random bit.

    Example:
    before:
        Defenestration
    after:
        Defenestratinn

    :param list lines: lines of the file in list
    """
    rand = randomizer.rand_index(len(lines))
    index = randomizer.rand_index(len(lines[rand]))

    char_ascii_val = lines[rand][index]
    char_ascii_val = char_ascii_val ^ (1 << (randomizer.rand_index(8)))
    inserted_byte = chr(char_ascii_val).encode()
    helpers.replace_at_split(lines, rand, index, inserted_byte)


@randomizer.random_repeats(RULE_ITERATIONS)
def remove_zero_byte(lines):
    """ Selects random line and removes random zero byte.

    Example:
        This is C string.\0 You are gonna love it.\0 -> This is string. You are gonna love it.\0

    :param list lines: lines of the file in list
    """
    rand = randomizer.rand_index(len(lines))
    positions = [pos for pos, char in enumerate(lines[rand]) if char == 0]
    if positions:
        index = randomizer.rand_choice(positions)
        helpers.remove_at_split(lines, rand, index)


@randomizer.random_repeats(RULE_ITERATIONS)
def insert_zero_byte(lines):
    """ Selects random line and inserts zero byte to any position.

    Example:
        This is C string.\0You are gonna love it.\0 -> This is C\0 string.\0You are gonna love it.\0

    :param list lines: lines of the file in list
    """
    rand = randomizer.rand_index(len(lines))
    index = randomizer.rand_index(len(lines[rand]))
    helpers.insert_at_split(lines, rand, index, b'\0')


FUZZING_METHODS = [
    (remove_zero_byte, "Remove zero byte"),
    (insert_zero_byte, "Insert zero byte to random position"),
    (insert_byte, "Insert a random byte to random position"),
    (remove_byte, "Remove random byte"),
    (byte_swap, "Switch two random bytes"),
    (bit_flip, "Flip random bit")
]
