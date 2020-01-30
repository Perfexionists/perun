"""Collects fuzzing rules specific for text files."""

import perun.fuzz.randomizer as randomizer
import perun.fuzz.helpers as helpers

__author__ = 'Matus Liscinsky'

RULE_ITERATIONS = 10
WS_MIN = 100
WS_MAX = 1000


@randomizer.random_repeats(RULE_ITERATIONS)
def change_char(lines):
    """ Changes a random character of a line.

    Example:
        "<author>Gambardella, Matthew</author>" -> "<author>Gambardella, Matthew</a!uthor>                    "

    :param list lines: lines of the workload, which has been choosen for mutating
    """
    rand = randomizer.rand_index(len(lines))
    index = randomizer.rand_index(len(lines[rand]))
    changed_char = chr(randomizer.rand_from_range(0, 255))
    helpers.replace_at_split(lines, rand, index, changed_char)


@randomizer.random_repeats(RULE_ITERATIONS)
def divide_line(lines):
    """ Divides a line by inserting newline to random position.

    Example:
        "<author>Gambardella, Matthew</author>" -> "<author>Gambardella, Matthew</au"
                                                   "thor>                    "

    :param list lines: lines of the workload, which has been choosen for mutating
    """
    rand = randomizer.rand_index(len(lines))
    index = randomizer.rand_index(len(lines[rand]))
    helpers.insert_at_split(lines, rand, index, "\n")


@randomizer.random_repeats(RULE_ITERATIONS)
def fuzz_insert_ws(lines):
    """ Inserts 100-1000 spaces to random position in a line.

    Example:
        "<author>Gambardella, Matthew</author>" -> "<author>Gambardella, Matthew</author>
                                                                            "

    :param list lines: lines of the workload, which has been choosen for mutating
    """
    rand = randomizer.rand_index(len(lines))
    index = randomizer.rand_index(len(lines[rand]))
    inserted_ws = " " * randomizer.rand_from_range(WS_MIN, WS_MAX)
    helpers.insert_at_split(lines, rand, index, inserted_ws)


@randomizer.random_repeats(RULE_ITERATIONS)
def fuzz_double_line(lines):
    """ Doubles the size of a line by its duplicating.

    Example:
        "The quick brown fox." -> "The quick brown fox.The quick brown fox."

    :param list lines: lines of the workload, which has been choosen for mutating
    """
    rand = randomizer.rand_index(len(lines))
    lines[rand] = lines[rand][:-1] * 2 + lines[rand][-1:]


@randomizer.random_repeats(RULE_ITERATIONS)
def fuzz_append_ws(lines):
    """ Appends 100-1000 spaces to a line.

    Example:
        "<author>Gambardella, Matthew</author>" -> "<author>Gambardella, Matthew</author>
                                                                            "

    :param list lines: lines of the workload, which has been choosen for mutating
    """
    rand = randomizer.rand_index(len(lines))
    appended_whitespace = " " * randomizer.rand_from_range(WS_MIN, WS_MAX)
    lines[rand] = lines[rand][:-1] + appended_whitespace + lines[rand][-1:]


@randomizer.random_repeats(RULE_ITERATIONS)
def fuzz_bloat_word(lines):
    """ Creates big words by removing whitespaces of a line.

    Example:
        "The quick brown fox." -> "Thequickbrownfox."

    :param list lines: lines of the workload, which has been choosen for mutating
    """
    rand = randomizer.rand_index(len(lines))
    lines[rand] = "".join(lines[rand].split()) + "\n"


@randomizer.random_repeats(RULE_ITERATIONS)
def multiplicate_ws(lines):
    """ Replaces white spaces with more white spaces.

    Example:
        "The quick brown fox." -> "The quick brown fox.,

                    The quick brown fox."

    :param list lines: lines of the workload, which has been choosen for mutating
    """
    rand = randomizer.rand_index(len(lines))
    lines[rand] = lines[rand].replace(" ", " "*10, 100)


@randomizer.random_repeats(RULE_ITERATIONS)
def prepend_ws(lines):
    """ Prepends a line with 100-1000 white spaces.

    Example:
        "The quick brown fox." -> "
                                                           The quick brown fox."

    :param list lines: lines of the workload, which has been choosen for mutating
    """
    rand = randomizer.rand_index(len(lines))
    lines[rand] = " "*randomizer.rand_from_range(WS_MIN, WS_MAX) + lines[rand]


@randomizer.random_repeats(RULE_ITERATIONS)
def fuzz_duplicate_line(lines):
    """ Duplicates random line in file.

    Example:
        "The quick brown fox." -> "The quick brown fox."
                                  "The quick brown fox."

    :param list lines: lines of the workload, which has been choosen for mutating
    """
    rand = randomizer.rand_index(len(lines))
    lines.insert(rand, lines[randomizer.rand_from_range(0, len(lines)-1)])


@randomizer.random_repeats(RULE_ITERATIONS)
def fuzz_sort_line(lines):
    """ Sorts the words or numbers.

    Example:
        "The quick brown fox." -> "brown fox quick The"

    :param list lines: lines of the workload, which has been choosen for mutating
    """
    rand = randomizer.rand_index(len(lines))
    words = lines[rand].split()
    try:
        lines[rand] = " ".join(sorted(words, key=int))
    except ValueError:
        lines[rand] = " ".join(sorted(words))


@randomizer.random_repeats(RULE_ITERATIONS)
def fuzz_rsort_line(lines):
    """ Reversely sorts the words or numbers.

    Example:
        "The quick brown fox." -> "brown fox quick The"

    :param list lines: lines of the workload, which has been choosen for mutating
    """
    rand = randomizer.rand_index(len(lines))
    words = lines[rand].split()
    try:
        lines[rand] = " ".join(sorted(words, reverse=True, key=int))
    except ValueError:
        lines[rand] = " ".join(sorted(words, reverse=True))


@randomizer.random_repeats(RULE_ITERATIONS)
def repeat_word(lines):
    """ 100 times repeats a random word and append it to a line.
        The length of a word is limited to 100, to prevent from DoS.
    Example:
        "The quick brown fox." -> "The quick brown fox.brown brown brown brown

    :param list lines: lines of the workload, which has been choosen for mutating
    """
    repetitions = 100
    rand = randomizer.rand_index(len(lines))
    try:
        word = randomizer.rand_choice(lines[rand].split())
        lines[rand] = lines[rand][:-1] + \
            (" " + (word[100]))*repetitions + lines[rand][-1:]
    except (ValueError, IndexError):
        pass


@randomizer.random_repeats(RULE_ITERATIONS)
def del_line(lines):
    """ Deletes random line.
    Example:
        "The quick brown fox." -> ""

    :param list lines: lines of the workload, which has been choosen for mutating
    """
    if len(lines):
        del lines[randomizer.rand_from_range(0, len(lines)-1)]


@randomizer.random_repeats(RULE_ITERATIONS)
def del_word(lines):
    """ Deletes random word of line.
    Example:
        "The quick brown fox." -> " quick brown fox."

    :param list lines: lines of the workload, which has been choosen for mutating
    """
    rand = randomizer.rand_index(len(lines))
    try:
        word = randomizer.rand_choice(lines[rand].split())
        lines[rand] = lines[rand].replace(word, "")
    except ValueError:
        pass


@randomizer.random_repeats(RULE_ITERATIONS)
def del_char(lines):
    """ Deletes random character from random line.
    Example:
        "The quick brown fox." -> "The quick brown fo."

    :param list lines: lines of the workload, which has been choosen for mutating
    """
    rand = randomizer.rand_index(len(lines))
    try:
        index = randomizer.rand_index(len(lines[rand]))
        lines[rand] = lines[rand][:index] + lines[rand][index + 1:]
    except ValueError:
        pass


fuzzing_methods = [
    (change_char, "Change random characters at random places"),
    (fuzz_insert_ws, "Insert whitespaces at random places"),
    (divide_line, "Divide a random line"),
    (fuzz_double_line, "Double the size of random line"),
    (fuzz_append_ws, "Append WS at the end of the line"),
    (fuzz_bloat_word, "Remove WS of random line"),
    (multiplicate_ws, "Multiplicate WS of random line"),
    (prepend_ws, "Prepend WS to random line"),
    (fuzz_duplicate_line, "Duplicate random line"),
    (fuzz_sort_line, "Sort words of random line"),
    (fuzz_rsort_line, "Reversely sort words of random line"),
    (repeat_word, "Multiplicate word of random line"),
    (del_line, "Remove random line"),
    (del_word, "Remove random word of line"),
    (del_char, "Remove random character of line "),
]
