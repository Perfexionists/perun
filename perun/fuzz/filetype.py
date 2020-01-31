"""Module for automatic recognizing file type and choosing appropriate fuzzing rules."""

import mimetypes
import re
import binaryornot.check as binaryornot

import perun.fuzz.randomizer as randomizer

import perun.fuzz.methods.binary as binary
import perun.fuzz.methods.xml as xml
import perun.fuzz.methods.textfile as textfile
from perun.fuzz.structs import RuleSet

__author__ = 'Matus Liscinsky'


def custom_rules(regex_rules, fuzzing_methods):
    """ Adds custom rules specified by regexps, and read from the file in YAML format.
    Format:
        del: add
        ([0-9]{6}),([0-9]{2}): \\1.\\2
        (\\w+)=(\\w+): \\2=\\1

    :param dict regex_rules: dict of custom regex rules
    :param list fuzzing_methods: list of functions, fuzzing (mutation) strategies
    """
    for key, value in regex_rules.items():
        def custom_rule(lines):
            comp_regexp = re.compile(key, flags=re.IGNORECASE)
            index = randomizer.rand_index(len(lines))
            lines[index] = comp_regexp.sub(value, lines[index])

        fuzzing_methods.append((custom_rule, "User rule: \"" + key + "\" -> \"" + value + "\""))


def get_filetype(file):
    """ Recognizes whether file is binary or text and its type using `mimetypes`

    :param str file: file name
    :return tuple: is_file_binary, file_type
    """
    try:
        filetype = (mimetypes.guess_type(file))[0].split("/")[-1]
    except AttributeError:
        filetype = None
    return binaryornot.is_binary(file), filetype


def choose_ruleset(file, regex_rules=None):
    """ Automatically collects appropriate fuzz methods according to file type.

    :param str file: path to file
    :param dict regex_rules: dict of custom regex rules
    :return list: list of tuples fuzz_method_function, description
    """
    fuzzing_methods = []
    if regex_rules:
        custom_rules(regex_rules, fuzzing_methods)

    is_binary, filetype = get_filetype(file)
    if is_binary:
        fuzzing_methods.extend(binary.fuzzing_methods)
    else:
        if filetype in ["xml", "html", "svg", "xhtml", "xul"]:
            fuzzing_methods.extend(xml.fuzzing_methods)
        fuzzing_methods.extend(textfile.fuzzing_methods)

    # last element is for total num of cov increases or perf degradations
    return RuleSet(fuzzing_methods, [0] * (len(fuzzing_methods) + 1))
