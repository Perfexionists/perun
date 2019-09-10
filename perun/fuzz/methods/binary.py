"""Collects fuzzing rules specific for binary files."""

__author__ = 'Matus Liscinsky'

import os

import perun.fuzz.randomizer as randomizer

RULE_ITERATIONS = 10


def insert_byte(lines):
    """ Selects random line and inserts a random byte to any position.

    Example:
        Defenestration -> Def%enestration

    :param list lines: lines of the file in list
    """
    for _ in range(randomizer.rand_from_range(1, RULE_ITERATIONS)):
        rand = randomizer.rand_index(len(lines))
        index = randomizer.rand_index(len(lines[rand]))
        byte = os.urandom(1)
        lines[rand] = lines[rand][:index] + byte + lines[rand][index:]


def remove_byte(lines):
    """ Selects random line and removes random byte.

    Example:
        #ef15ac -> ef15ac

    :param list lines: lines of the file in list
    """
    for _ in range(randomizer.rand_from_range(1, RULE_ITERATIONS)):
        rand = randomizer.rand_index(len(lines))
        index = randomizer.rand_index(len(lines[rand]))
        lines[rand] = lines[rand][:index] + lines[rand][index+1:]


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
    for _ in range(randomizer.rand_from_range(1, RULE_ITERATIONS)):
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


def bit_flip(lines):
    """ Selects random line and flips random bit.

    Example:
    before:
        Defenestration
    after:
        Defenestratinn

    :param list lines: lines of the file in list
    """
    for _ in range(randomizer.rand_from_range(1, RULE_ITERATIONS)):
        rand = randomizer.rand_index(len(lines))
        index = randomizer.rand_index(len(lines[rand]))

        char_ascii_val = lines[rand][index]
        char_ascii_val = char_ascii_val ^ (1 << (randomizer.rand_index(8)))
        lines[rand] = lines[rand][:index] + \
            chr((char_ascii_val)).encode() + lines[rand][index + 1:]


def remove_zero_byte(lines):
    """ Selects random line and removes random zero byte.

    Example:
        This is C string.\0 You are gonna love it.\0 -> This is string. You are gonna love it.\0

    :param list lines: lines of the file in list
    """
    for _ in range(randomizer.rand_from_range(1, RULE_ITERATIONS)):
        rand = randomizer.rand_index(len(lines))
        positions = [pos for pos, char in enumerate(lines[rand]) if char == 0]
        if positions:
            index = randomizer.rand_choice(positions)
            lines[rand] = lines[rand][:index] + lines[rand][index+1:]


def insert_zero_byte(lines):
    """ Selects random line and inserts zero byte to any position.

    Example:
        This is C string.\0You are gonna love it.\0 -> This is C\0 string.\0You are gonna love it.\0

    :param list lines: lines of the file in list
    """
    for _ in range(randomizer.rand_from_range(1, RULE_ITERATIONS)):
        rand = randomizer.rand_index(len(lines))
        index = randomizer.rand_index(len(lines[rand]))
        lines[rand] = lines[rand][:index] + b'\0' + lines[rand][index:]


fuzzing_methods = [(remove_zero_byte, "Remove zero byte"),
                   (insert_zero_byte, "Insert zero byte to random position"),
                   (insert_byte, "Insert a random byte to random position"),
                   (remove_byte, "Remove random byte"),
                   (byte_swap, "Switch two random bytes"),
                   (bit_flip, "Flip random bit")]
