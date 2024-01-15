"""Collects fuzzing rules specific for text files."""
from __future__ import annotations

# Standard Imports

# Third-Party Imports

# Perun Imports
from perun.fuzz import helpers, randomizer
from perun.utils.exceptions import SuppressedExceptions

RULE_ITERATIONS = 10
WS_MIN = 100
WS_MAX = 1000


@randomizer.random_repeats(RULE_ITERATIONS)
def change_character(lines: list[str]) -> None:
    """**Rule T.4: Change random character.**

    * **Input**: "the quick brown fox jumps over the lazy dog"
    * **Mutation**: "the quack brown [b]ox jumps over the lazy dog"
    * **Description**: Adaptation of classical rule for text files. Changes a random character
      at random line to different character.
    * **Known Issues**: none
    """
    rand = randomizer.rand_index(len(lines))
    index = randomizer.rand_index(len(lines[rand]))
    changed_char = chr(randomizer.rand_from_range(0, 255))
    helpers.replace_at_split(lines, rand, index, changed_char)


@randomizer.random_repeats(RULE_ITERATIONS)
def divide_line(lines: list[str]) -> None:
    """**Rule T.3: Divide line.**

    * **Input**: "<author>Gambardella, Matthew</author>"
    * **Mutation**: "<author>Gambardella, Matthew</au", "thor>"
    * **Description**: Divides a line by inserting newline character in random position.
    * **Known Issues**: none
    """
    rand = randomizer.rand_index(len(lines))
    index = randomizer.rand_index(len(lines[rand]))
    helpers.insert_at_split(lines, rand, index, "\n")


@randomizer.random_repeats(RULE_ITERATIONS)
def insert_whitespace(lines: list[str]) -> None:
    """**Rule T.10: Insert whitespaces on a random place.**

    * **Input**: "the quick brown fox jumps over the lazy dog"
    * **Mutation**: "The quick bro[   ]wn fox jumps over the lazy dog"
    * **Description**: The rule inserts random number of whitespaces at random place in the random
      line. There are several intuitions behind this rule: (1) some trimming regular expressions
      can induce the excessive number of backtracking, and (2) some structures, such as hash
      tables, can have bad properties and lead to a singly-linked list when induced with lots of
      words (e.g. when one chooses wrong size of the table or bad hash-function).
    * **Known Issues**: none
    """
    rand = randomizer.rand_index(len(lines))
    index = randomizer.rand_index(len(lines[rand]))
    inserted_ws = " " * randomizer.rand_from_range(WS_MIN, WS_MAX)
    helpers.insert_at_split(lines, rand, index, inserted_ws)


@randomizer.random_repeats(RULE_ITERATIONS)
def double_line(lines: list[str]) -> None:
    """**Rule T.1: Double the size of a line.**

    * **Input**: "The quick brown fox."
    * **Mutation**: "The quick brown fox.The quick brown fox."
    * **Description**: This rule focuses on possible performance issues associated with long lines
      appearing in files. The rule doubles the selected random line in the input.
    * **Known Issues**:

       1. gedit_ text editor (issue with too long lines)
       2. Poorly validated regexps (issue with lengthy backtracking)

    .. _gedit: https://wiki.gnome.org/Apps/Gedit
    """
    rand = randomizer.rand_index(len(lines))
    lines[rand] = lines[rand][:-1] * 2 + lines[rand][-1:]


@randomizer.random_repeats(RULE_ITERATIONS)
def append_whitespace(lines: list[str]) -> None:
    """**Rule T.8: Append whitespaces.**

    * **Input**: "the quick brown fox jumps over the lazy dog"
    * **Mutation**: "the quick brown fox jumps over the lazy dog[    ]"
    * **Description**: The rule appends random number of whitespaces at random line.
    * **Known Issues**: none
    """
    rand = randomizer.rand_index(len(lines))
    appended_whitespace = " " * randomizer.rand_from_range(WS_MIN, WS_MAX)
    lines[rand] = lines[rand][:-1] + appended_whitespace + lines[rand][-1:]


@randomizer.random_repeats(RULE_ITERATIONS)
def bloat_words(lines: list[str]) -> None:
    """**Rule T.12: Remove whitespaces.**

    * **Input**: "The quick brown fox."
    * **Mutation**: "The quickbrown fox."
    * **Description**: Removes whitespace from a random line. The intuition is to create a bigger
      words that might bloat the underlying structures.
    * **Known Issues**: none
    """
    rand = randomizer.rand_index(len(lines))
    lines[rand] = "".join(lines[rand].split()) + "\n"


@randomizer.random_repeats(RULE_ITERATIONS)
def repeat_whitespace(lines: list[str]) -> None:
    """**Rule T.11: Repeat whitespaces.**

    * **Input**: "the quick brown fox jumps over the lazy dog"
    * **Mutation**: "The quick brown[    ] fox jumps over the lazy dog"
    * **Description**: The rule repeats random number of whitespaces at random place in the random
      line. There intuition behind this rule is that some trimming regular expressions
      can induce the excessive number of backtracking.
    * **Known Issues**: none
    """
    rand = randomizer.rand_index(len(lines))
    lines[rand] = lines[rand].replace(" ", " " * 10, 100)


@randomizer.random_repeats(RULE_ITERATIONS)
def prepend_whitespace(lines: list[str]) -> None:
    """**Rule T.9: Prepend whitespaces.**

     * **Input**: "the quick brown fox jumps over the lazy dog"
     * **Mutation**: "[    ]The quick brown fox jumps over the lazy dog"
     * **Description**: The rule prepends random number of whitespaces at random line.
     * **Known Issues**:

       1. StackOverflow_ regular expression with quadratic number of backtracking.

    .. _StackOverflow: https://stackstatus.net/post/147710624694/outage-postmortem-july-20-2016
    """
    rand = randomizer.rand_index(len(lines))
    lines[rand] = " " * randomizer.rand_from_range(WS_MIN, WS_MAX) + lines[rand]


@randomizer.random_repeats(RULE_ITERATIONS)
def duplicate_line(lines: list[str]) -> None:
    """**Rule T.2: Duplicate a line.**

    * **Input**: "The quick brown fox."
    * **Mutation**: "The quick brown fox.", "The quick brown fox."
    * **Description**: Extends the file vertically, by duplicating random
      line in the file.
    * **Known Issues**: none
    """
    rand = randomizer.rand_index(len(lines))
    lines.insert(rand, lines[randomizer.rand_from_range(0, len(lines) - 1)])


@randomizer.random_repeats(RULE_ITERATIONS)
def sort_line(lines: list[str]) -> None:
    """**Rule T.6: Sort words or numbers of a line.**

    * **Input**: "The quick brown fox."
    * **Mutation**: "brown fox quick The.
    * **Description**: The intuition of this rule is to force bad behaviour, e.g. to sorting
      algorithm, that in some cases perform worse for sorted output, or to balanced trees, which
      might be unbalanced for sorted values.
    * **Known Issues**: none
    """
    rand = randomizer.rand_index(len(lines))
    words = lines[rand].split()
    try:
        lines[rand] = " ".join(sorted(words, key=int))
    except ValueError:
        lines[rand] = " ".join(sorted(words))


@randomizer.random_repeats(RULE_ITERATIONS)
def sort_line_in_reverse(lines: list[str]) -> None:
    """**Rule T.7: Sort words or numbers of a line in reverse.**

     * **Input**: "The quick brown fox."
     * **Mutation**: "brown fox quick The.
     * **Description**: The intuition of this rule is to force bad behaviour, e.g. to sorting
       algorithm, that in some cases perform worse for sorted output, or to balanced trees, which
       might be unbalanced for sorted values.
     * **Known Issues**: none
    """ ""
    rand = randomizer.rand_index(len(lines))
    words = lines[rand].split()
    try:
        lines[rand] = " ".join(sorted(words, reverse=True, key=int))
    except ValueError:
        lines[rand] = " ".join(sorted(words, reverse=True))


@randomizer.random_repeats(RULE_ITERATIONS)
def repeat_word(lines: list[str]) -> None:
    """**Rule T.5: Repeat random word of a line.**

    * **Input**: "the quick brown fox jumps over the lazy dog"
    * **Mutation**: "the quick brown [brown] fox jumps over the lazy dog"
    * **Description**: The rule picks a random word in random line and repeats it several times.
      The intuition is, that there e.g. exist certain vulnerabilities, when repeated occurrences
      of words can either lead to faster (e.g. when the word is cached) or slower time
      (e.g. when in hash-table the underlying structure is degradated to list). Moreover, some
      algorithms, such as quick sort are forced to worst-case, when all elements are same.
    * **Known Issues**: none
    """
    repetitions = 100
    rand = randomizer.rand_index(len(lines))
    with SuppressedExceptions(ValueError, IndexError):
        word = randomizer.rand_choice(lines[rand].split())
        lines[rand] = lines[rand][:-1] + (" " + (word[100])) * repetitions + lines[rand][-1:]


@randomizer.random_repeats(RULE_ITERATIONS)
def delete_line(lines: list[str]) -> None:
    """**Rule T.13: Remove random line.**

    * **Input**: "the quick brown fox jumps over the lazy dog"
    * **Mutation**: ""
    * **Description**: Removes random line.
    * **Known Issues**:
    """
    if len(lines) > 0:
        del lines[randomizer.rand_from_range(0, len(lines) - 1)]


@randomizer.random_repeats(RULE_ITERATIONS)
def delete_word(lines: list[str]) -> None:
    """**Rule T.14: Remove random word**

    * **Input**: "the quick brown fox jumps over the lazy dog"
    * **Mutation**: "the brown fox jumps over the lazy dog"
    * **Description**: Removes random word in random line.
    * **Known Issues**: none
    """
    rand = randomizer.rand_index(len(lines))
    with SuppressedExceptions(ValueError):
        word = randomizer.rand_choice(lines[rand].split())
        lines[rand] = lines[rand].replace(word, "")


@randomizer.random_repeats(RULE_ITERATIONS)
def delete_character(lines: list[str]) -> None:
    """**Rule T.15: remove a random character.**

    * **Input**: "the quick brown fox jumps over the lazy dog"
    * **Mutation**: "the quck brown fox jumps over the lazy dog"
    * **Description**: Removes a random character in random word in random line.
    * **Known Issues**: none
    """
    rand = randomizer.rand_index(len(lines))
    with SuppressedExceptions(ValueError):
        index = randomizer.rand_index(len(lines[rand]))
        helpers.remove_at_split(lines, rand, index)


FUZZING_METHODS = [
    (change_character, "Change random characters at random places"),
    (insert_whitespace, "Insert whitespaces at random places"),
    (divide_line, "Divide a random line"),
    (double_line, "Double the size of random line"),
    (append_whitespace, "Append WS at the end of the line"),
    (bloat_words, "Remove WS of random line"),
    (repeat_whitespace, "Multiplicate WS of random line"),
    (prepend_whitespace, "Prepend WS to random line"),
    (duplicate_line, "Duplicate random line"),
    (sort_line, "Sort words of random line"),
    (sort_line_in_reverse, "Reversely sort words of random line"),
    (repeat_word, "Multiplicate word of random line"),
    (delete_line, "Remove random line"),
    (delete_word, "Remove random word of line"),
    (delete_character, "Remove random character of line "),
]
