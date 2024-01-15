"""
Exploiting more domain-specific knowledge about the workload we
devised specific rules for concrete formats. We propose rules for
removing tags, attributes, names or values of attributes used in XML
based files (i.e. ``.xml``, ``.svg``, ``.xhtml``, ``.xul``).
For example, we can assume a situation, when fuzzer removes closing tag,
which will increase the nesting. Then a recursively implemented parser
will fail to find one or more of closing brackets (representing recursion
stop condition) and may hit a stack overflow error.
"""
from __future__ import annotations

# Standard Imports
import re

# Third-Party Imports

# Perun Imports
from perun.fuzz import randomizer

RULE_ITERATIONS = 10


def random_regex_replace(lines: list[str], pattern: str, repl: str) -> None:
    """Helper function for replacing the string in lines given a pattern

    :param list lines: list of lines
    :param str pattern: pattern which will be replaced
    :param str repl: string which will replace the pattern
    """
    rand = randomizer.rand_index(len(lines))
    regex_pattern = re.compile(pattern)
    matches = list(regex_pattern.finditer(lines[rand]))
    # pick random match
    if matches:
        picked_match = randomizer.rand_choice(matches)
        lines[rand] = lines[rand][: picked_match.start()] + regex_pattern.sub(
            repl, lines[rand][picked_match.start() :], 1
        )


@randomizer.random_repeats(RULE_ITERATIONS)
def remove_attribute_value(lines: list[str]) -> None:
    """**Rule D.3: Removed attribute value.**

    * **Input**: <book id="bk106" pages="457">
    * **Mutation**: <book id="bk106" pages="">
    * **Description**: Removes random value of the attribute in the random line and tag.
    * **Known Issues**: none
    """
    random_regex_replace(lines, r"\"\s*\S+\s*\"", '""')


@randomizer.random_repeats(RULE_ITERATIONS)
def remove_attribute_name(lines: list[str]) -> None:
    """**Rule D.2: Remove attribute name.**

    * **Input**: <book id="bk106" pages="457">
    * **Mutation**: <book id="bk106" "457">
    * **Description**: Removes name of the attribute in random tag in the random line.
    * **Known Issues**: none
    """
    random_regex_replace(lines, r"\S*\s*=\s*(?P<quote>[\"|\'])", r"\g<quote>")


@randomizer.random_repeats(RULE_ITERATIONS)
def remove_attribute(lines: list[str]) -> None:
    """**Rule D.1: Remove an attribute.**

    * **Input**: <book id="bk106" pages="457">
    * **Mutation**: <book id="bk106">
    * **Description**: Selects random tag and removes a random attribute.
    * **Known Issues**: none
    """
    random_regex_replace(lines, r"\S*\s*=\s*\"\s*\S*\s*\"", "")


@randomizer.random_repeats(RULE_ITERATIONS)
def remove_tag(lines: list[str]) -> None:
    """**Rule D.4: Remove tag.**

    * **Input**: <book id="bk106" pages="457">
    * **Mutation**:
    * **Description**: Removes a random tag.
    * **Known Issues**: none
    """
    random_regex_replace(lines, r"<[^>]*>", "")


FUZZING_METHODS = [
    (remove_attribute_value, "Remove random attribute value"),
    (remove_attribute_name, "Remove random attribute name"),
    (remove_attribute, "Remove random attribute"),
    (remove_tag, "Remove random tag"),
]
