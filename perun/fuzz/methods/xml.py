"""Collects fuzzing rules specific for xml files and similar markup format files."""

import re

import perun.fuzz.randomizer as randomizer

RULE_ITERATIONS = 10


def random_regex_replace(lines, pattern, repl):
    rand = randomizer.rand_index(len(lines))
    pattern = re.compile(pattern)
    matches = pattern.finditer(lines[rand])
    matches = list(matches)
    # pick random match
    if matches:
        picked_match = randomizer.rand_choice(matches)
        # lines[rand] = lines[rand][:picked_match.start()] + repl + lines[rand][picked_match.end():]
        lines[rand] = lines[rand][:picked_match.start()] + \
            pattern.sub(repl, lines[rand][picked_match.start():], 1)


def remove_attribute_value(lines):
    """ Selects random line and removes random attribute value.

    Example:
        <book id="bk106" pages="457"> -> <book id="bk106" pages="">

    :param list lines: lines of the file in list
    """
    for _ in range(randomizer.rand_from_range(1, RULE_ITERATIONS)):
        random_regex_replace(lines, r"\"\s*\S+\s*\"", "\"\"")


def remove_attribute_name(lines):
    """ Selects random line and removes random attribute name.

    Example:
        <book id="bk106" pages="457"> -> <book id="bk106" "457">

    :param list lines: lines of the file in list
    """
    for _ in range(randomizer.rand_from_range(1, RULE_ITERATIONS)):
        random_regex_replace(
            lines, r"\S*\s*=\s*(?P<quote>[\"|\'])", r"\g<quote>")


def remove_attribute(lines):
    """ Selects random line and removes random attribute(name and value).

    Example:
        <book id="bk106" pages="457"> -> <book id="bk106" >

    :param list lines: lines of the file in list
    """
    for _ in range(randomizer.rand_from_range(1, RULE_ITERATIONS)):
        random_regex_replace(lines, r"\S*\s*=\s*\"\s*\S*\s*\"", "")


def remove_tag(lines):
    """ Selects random line and removes random tag.

    Example:
        "<book id="bk106" pages="457">" -> ""

    :param list lines: lines of the file in list
    """
    for _ in range(randomizer.rand_from_range(1, RULE_ITERATIONS)):
        random_regex_replace(lines, r"<[^>]*>", "")


fuzzing_methods = [(remove_attribute_value, "Remove random attribute value"),
                   (remove_attribute_name, "Remove random attribute name"),
                   (remove_attribute, "Remove random attribute"),
                   (remove_tag, "Remove random tag")]
