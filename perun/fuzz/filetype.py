"""Module for automatic recognizing file type and choosing appropriate fuzzing rules."""

import binaryornot.check as binaryornot
import mimetypes
import re

import perun.fuzz.randomizer as randomizer

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

        fuzzing_methods.append(
            (custom_rule, "User rule: \"" + key + "\" -> \"" + value + "\""))


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


def choose_methods(file, regex_rules=None):
    """ Automatically collects appropriate fuzz methods according to file type.

    :param str file: path to file
    :param dict regex_rules: dict of custom regex rules
    :return list: list of tuples fuzz_method_function, description
    """
    fuzzing_methods = []
    if regex_rules:
        custom_rules(regex_rules, fuzzing_methods)

    binary, filetype = get_filetype(file)
    if binary:
        from perun.fuzz.methods.binary import fuzzing_methods as binary_fm
        fuzzing_methods.extend(binary_fm)
    else:
        if filetype in ["xml", "html", "svg", "xhtml", "xul"]:
            from perun.fuzz.methods.xml import fuzzing_methods as markup_fm
            fuzzing_methods.extend(markup_fm)
        from perun.fuzz.methods.textfile import fuzzing_methods as text_fm
        fuzzing_methods.extend(text_fm)
    return fuzzing_methods