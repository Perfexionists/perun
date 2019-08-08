"""Collects fuzzing rules specific for xml files and similar markup format files."""

import re
import random

RULE_ITERATIONS = 10


def remove_attribute_value(lines):
    """ Selects random line and removes random attribute value, 1-10 times.

    Example:
        <book id="bk106" pages="457"> -> <book id="bk106" pages="">

    :param list lines: lines of the file in list
    """
    for _ in range(random.randint(1, RULE_ITERATIONS)):
        rand = random.randrange(len(lines))
        try:
            attr = random.choice(re.findall(r"\"\s*\S+\s*\"", lines[rand]))
            lines[rand] = lines[rand].replace(attr, "\"\"", 1)
        except IndexError:
            pass


def remove_attribute_name(lines):
    """ Selects random line and removes random attribute name, 1-10 times.

    Example:
        <book id="bk106" pages="457"> -> <book id="bk106" "457">

    :param list lines: lines of the file in list
    """
    for _ in range(random.randint(1, RULE_ITERATIONS)):
        rand = random.randrange(len(lines))
        try:
            attr = random.choice(re.findall(r"\S*\s*=\s*[\"|\']", lines[rand]))
            lines[rand] = lines[rand].replace(attr, attr[-1], 1)
        except IndexError:
            pass


def remove_attribute(lines):
    """ Selects random line and removes random attribute(name and value), 1-10 times.

    Example:
        <book id="bk106" pages="457"> -> <book id="bk106" >

    :param list lines: lines of the file in list
    """
    for _ in range(random.randint(1, RULE_ITERATIONS)):
        rand = random.randrange(len(lines))
        try:
            attr = random.choice(re.findall(
                r"\S*\s*=\s*\"\s*\S*\s*\"", lines[rand]))
            lines[rand] = lines[rand].replace(attr, "", 1)
        except IndexError:
            pass


def remove_tag(lines):
    """ Selects random line and removes random attribute(name and value), 1-10 times.

    Example:
        "<book id="bk106" pages="457">" -> ""

    :param list lines: lines of the file in list
    """
    for _ in range(random.randint(1, RULE_ITERATIONS)):
        rand = random.randrange(len(lines))
        try:
            tag = random.choice(re.findall(r"<[^>]*>", lines[rand]))
            lines[rand] = lines[rand].replace(tag, "", 1)
        except IndexError:
            pass


fuzzing_methods = [(remove_attribute_value, "Remove random attribute value"),
                   (remove_attribute_name, "Remove random attribute name"),
                   (remove_attribute, "Remove random attribute"),
                   (remove_tag, "Remove random tag")]
