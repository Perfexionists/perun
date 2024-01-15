"""
In case of binary files we cannot apply specific domain knowledge nor can we be inspired by
existing performance issues. Instead, we mostly adapt the classical fuzzing rules.
"""
from __future__ import annotations

# Standard Imports
import os

# Third-Party Imports

# Perun Imports
from perun.fuzz import helpers, randomizer


RULE_ITERATIONS = 10


@randomizer.random_repeats(RULE_ITERATIONS)
def insert_byte(lines: list[bytes]) -> None:
    """**Rule B.3: Insert random byte.**

    * **Input**: "the quick brown fox jumps over the lazy dog"
    * **Mutation**: "the qui#ck brown fox jumps over the lazy dog"
    * **Description**: Implementation of classical fuzzing rule.
    * **Known Issues**: none
    """
    rand = randomizer.rand_index(len(lines))
    index = randomizer.rand_index(len(lines[rand]))
    byte = os.urandom(1)
    helpers.insert_at_split(lines, rand, index, byte)


@randomizer.random_repeats(RULE_ITERATIONS)
def remove_byte(lines: list[bytes]) -> None:
    """**Rule B.4: Remove random byte.**

    * **Input**: "the quick brown fox jumps over the lazy dog"
    * **Mutation**: "the quik brown fox jumps over the lazy dog"
    * **Description**: Implementation of classical fuzzing rule.
    * **Known Issues**: none
    """
    rand = randomizer.rand_index(len(lines))
    index = randomizer.rand_index(len(lines[rand]))
    helpers.remove_at_split(lines, rand, index)


@randomizer.random_repeats(RULE_ITERATIONS)
def swap_byte(lines: list[bytes]) -> None:
    """**Rule B.5: Swap random bytes.**

    * **Input**: "the quick brown fox jumps over the lazy dog"
    * **Mutation**: "the quock brown fix jumps over the lazy dog"
    * **Description**: Implementation of classical fuzzing rule. Picks two random lines and
      two random bytes in the line and swaps them.
    * **Known Issues**: none
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
def flip_bit(lines: list[bytes]) -> None:
    """**Rule B.6: Flip random bit.**

    * **Input**: "the quick brown fox jumps over the lazy dog"
    * **Mutation**: "the quack brown fox jumps over the lazy dog"
    * **Description**: Implementation of classical fuzzing rule.
    * **Known Issues**: none
    """
    rand = randomizer.rand_index(len(lines))
    index = randomizer.rand_index(len(lines[rand]))

    char_ascii_val = lines[rand][index]
    char_ascii_val = char_ascii_val ^ (1 << (randomizer.rand_index(8)))
    inserted_byte = chr(char_ascii_val).encode()
    helpers.replace_at_split(lines, rand, index, inserted_byte)


@randomizer.random_repeats(RULE_ITERATIONS)
def remove_zero_byte(lines: list[bytes]) -> None:
    """**Rule B.1: Remove random zero byte**

    * **Input**: This is C string.\0 You are gonna love it.\0
    * **Mutation**: This is string. You are gonna love it.\0
    * **Description**: The rule removes random zero byte ``\0`` in the string. The intuition is to
      target the C language application, that process the strings as zero-terminated string of
      bytes. Removing the zero byte could lead to program non-termination, or at least crashing
      when reading the whole memory.
    * **Known Issues**: none
    """
    rand = randomizer.rand_index(len(lines))
    positions = [pos for pos, char in enumerate(lines[rand]) if char == 0]
    if positions:
        index = randomizer.rand_choice(positions)
        helpers.remove_at_split(lines, rand, index)


@randomizer.random_repeats(RULE_ITERATIONS)
def insert_zero_byte(lines: list[bytes]) -> None:
    """**Rule B.2: Insert random zero byte.**

    * **Input**: This is C string. You are gonna love it.\0
    * **Mutation**: This is string.``\0`` You are gonna love it.\0
    * **Description**: The rule inserts random zero byte ``\0`` in the string. The intuition is to
      target the C language application, that process the strings as zero-terminated string of
      bytes.
    * **Known Issues**: none
    """
    rand = randomizer.rand_index(len(lines))
    index = randomizer.rand_index(len(lines[rand]))
    helpers.insert_at_split(lines, rand, index, b"\0")


FUZZING_METHODS = [
    (remove_zero_byte, "Remove zero byte"),
    (insert_zero_byte, "Insert zero byte to random position"),
    (insert_byte, "Insert a random byte to random position"),
    (remove_byte, "Remove random byte"),
    (swap_byte, "Switch two random bytes"),
    (flip_bit, "Flip random bit"),
]
