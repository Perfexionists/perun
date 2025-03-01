"""Set of helper constants and helper named tuples for perun pcs"""

from __future__ import annotations

# Standard Imports
from typing import (
    Any,
    Callable,
    Iterable,
    Literal,
    Optional,
    Type,
    TypeVar,
    TYPE_CHECKING,
)
import array
import contextlib
import importlib
import itertools
import operator
import os
import re
import signal
import statistics

# Third-Party Imports
import click

# Perun Imports
from perun.postprocess.regression_analysis import tools
from perun.utils.exceptions import (
    NotPerunRepositoryException,
    SignalReceivedException,
    SuppressedExceptions,
)

if TYPE_CHECKING:
    import types

T = TypeVar("T")
KT = TypeVar("KT")
VT = TypeVar("VT")

# Color types based on variables in perun/templates/style/general_setup.css
ColorVariableType = Literal[
    "correct",
    "wrong",
    "primary",
]

# Types
ColorChoiceType = Literal[
    "black",
    "grey",
    "red",
    "green",
    "yellow",
    "blue",
    "magenta",
    "cyan",
    "light_grey",
    "dark_grey",
    "light_red",
    "light_green",
    "light_yellow",
    "light_blue",
    "light_magenta",
    "light_cyan",
    "white",
]
AttrChoiceType = Iterable[Literal["bold", "dark", "underline", "blink", "reverse", "concealed"]]

# Other constants
TEXT_ATTRS: Optional[AttrChoiceType] = None
TEXT_EMPH_COLOUR: ColorChoiceType = "green"
TEXT_WARN_COLOUR: ColorChoiceType = "red"
AGGREGATIONS: tuple[str, ...] = "sum", "mean", "count", "nunique", "median", "min", "max"

# Profile specific stuff
SUPPORTED_PROFILE_TYPES: list[str] = ["memory", "mixed", "time"]
PROFILE_TRACKED: ColorChoiceType = "white"
PROFILE_UNTRACKED: ColorChoiceType = "red"
PROFILE_TYPE_COLOURS: dict[str, ColorChoiceType] = {
    "time": "blue",
    "mixed": "cyan",
    "memory": "white",
}
PROFILE_DELIMITER: str = "|"

HEADER_ATTRS: AttrChoiceType = ["underline"]
HEADER_COMMIT_COLOUR: ColorChoiceType = "green"
HEADER_INFO_COLOUR: ColorChoiceType = "white"
HEADER_SLASH_COLOUR: ColorChoiceType = "white"

# Job specific
COLLECT_PHASE_CMD: ColorChoiceType = "blue"
COLLECT_PHASE_WORKLOAD: ColorChoiceType = "cyan"
COLLECT_PHASE_COLLECT: ColorChoiceType = "magenta"
COLLECT_PHASE_POSTPROCESS: ColorChoiceType = "yellow"
COLLECT_PHASE_ATTRS: Optional[AttrChoiceType] = None

# Degradation specific
CHANGE_CMD_COLOUR: ColorChoiceType = "magenta"
CHANGE_TYPE_COLOURS: dict[str, ColorChoiceType] = {
    "time": "blue",
    "mixed": "cyan",
    "memory": "white",
}
DEGRADATION_ICON: Literal["-"] = "-"
OPTIMIZATION_ICON: Literal["+"] = "+"
LINE_PARSING_REGEX: re.Pattern[Any] = re.compile(
    r"(?P<location>.+)\s"
    r"PerformanceChange[.](?P<result>[A-Za-z]+)\s"
    r"(?P<type>\S+)\s"
    r"(?P<from>\S+)\s"
    r"(?P<to>\S+)\s"
    r"(?P<drate>\S+)\s"
    r"(?P<ctype>\S+)\s"
    r"(?P<crate>\S+)\s"
    r"(?P<rdrate>\S+)\s"
    r"(?P<minor>\S+)\s"
    r"(?P<cmdstr>.+)"
)

ALWAYS_CONFIRM: bool = False
DEFAULT_CONFIRMATION: bool = True


def perun_confirm(confirm_message: str) -> bool:
    """Wrapper function for confirming information from user

    :param confirm_message: message that is printed to user
    :return: confirmation status
    """
    if ALWAYS_CONFIRM:
        return DEFAULT_CONFIRMATION
    return click.confirm(confirm_message)


def first_index_of_attr(input_list: list[Any], attr: str, value: Any) -> int:
    """Helper function for getting the first index of a value in list of objects

    :param input_list: list of object that have attributes
    :param attr: name of the attribute we are getting
    :param value: looked up value
    :return: index in the list or exception
    :raises: ValueError when there is no object with attribute with given value
    """
    list_of_attributes = list(map(operator.attrgetter(attr), input_list))
    return list_of_attributes.index(value)


def uid_getter(uid: tuple[str, Any]) -> int:
    """Helper function for getting the order priority of the uid

    By default, the highest priority is the executed binary or command,
    then file and package structure, then modules, objects, concrete functions
    or methods, on lines up to instruction. If we encounter unknown key, then we
    use some kind of lexicographic sorting

    :param uid: the part of the uid
    :return: the rank of the uid in the ordering
    """
    uid_priority = {
        "bin": 0,
        "file": 1,
        "source": 1,
        "package": 1,
        "module": 2,
        "class": 3,
        "struct": 3,
        "structure": 3,
        "function": 4,
        "func": 4,
        "method": 4,
        "procedure": 4,
        "line": 5,
        "instruction": 6,
    }
    max_value = max(uid_priority.values())
    return uid_priority.get(
        uid[0], int("".join(map(str, map(lambda x: x + max_value, map(ord, uid[0])))))
    )


def str_to_plural(count: int, verb: str) -> str:
    """Helper function that returns the plural of the string if count is more than 1

    :param count: number of the verbs
    :param verb: name of the verb we are creating a plural for
    """
    return str(count) + " " + (verb + "s" if count != 1 else verb)


def strtobool(value: str) -> bool:
    """Convert a string representation of truth to True or False.
    Taken from the source code of the `distutils` package that was deprecated in Python 3.10.
    True values are 'y', 'yes', 't', 'true', 'on', and '1'.
    False values are 'n', 'no', 'f', 'false', 'off', and '0'.
    :param value: the truth value to convert.
    :return: True or False depending on whether the value matches one of the truth strings.
    :raises ValueError: if the value does not match any of the expected strings.
    """
    value = value.lower()
    if value in ("y", "yes", "t", "true", "on", "1"):
        return True
    if value in ("n", "no", "f", "false", "off", "0"):
        return False
    raise ValueError(f"invalid truth value {value}")


def format_counter_number(count: int, max_number: int) -> str:
    """Helper function that returns string formatted to number of places given by the length of max
    counter number.

    :param count: the current number of the counter
    :param max_number: the maximal number of counter
    :return:
    """
    return f"{count:{len(str(max_number))}d}"


def capitalize_first(string: str) -> str:
    """Helper function that capitalizes only the first letter of a string.

    Note that contrary to the library string method `capitalize()` that changes the remaining
    characters to lowercase, this helper function does not modify any other character except the
    first.

    :param string: the string to capitalize

    :return: the string with the first letter being uppercase
    """
    return string[0].upper() + string[1:]


def default_signal_handler(signum: int, frame: types.FrameType) -> None:
    """Default signal handler used by the HandledSignals CM.

    The function attempts to block any subsequent handler invocation of the same signal by ignoring
    the signal. Thus, there should be no further interrupts by the same signal until the __exit__
    sentinel is reached (where all the handled signals are then temporarily ignored during
    the callback).

    However, this will still not block any other signals than the initially encountered one, since
    the default handler doesn't have means to find out all the signals that are being handled by
    a specific CM instance and should be thus ignored.

    To block all the signals handled by a certain HandledSignals context manager, a custom handler
    should be constructed in such a way that all the handled signals are set to signal.SIG_IGN.

    :param signum: representation of the signal that caused the handler to be invoked
    :param frame: the frame / stack trace object
    """
    signal.signal(signum, signal.SIG_IGN)
    raise SignalReceivedException(signum, frame)


def is_variable_len_dict(list_value: list[dict[Any, Any]]) -> bool:
    """This tests for a case when list_value is a list with dictionaries containing name and list_value
    keys only.

    This the case, e.g. for coefficients of models.

    :param list_value: object we are testing
    :return: true if list_value is variable length dictionary
    """
    return len(list_value) != 0 and all(
        isinstance(v, dict) and set(v.keys()) == {"name", "value"} for v in list_value
    )


def escape_ansi(line: str) -> str:
    """Escapes the font/colour ansi characters in the line

    Based on: https://stackoverflow.com/a/38662876

    :param line: line with ansi control characters
    :return: ansi control-free string
    """
    ansi_escape = re.compile(r"(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]")
    return ansi_escape.sub("", line)


def touch_file(touched_filename: str, times: Optional[tuple[int, int]] = None) -> None:
    """
    Corresponding implementation of touch inside python.
    Courtesy of:
    https://stackoverflow.com/questions/1158076/implement-touch-using-python

    :param touched_filename: filename that will be touched
    :param times: access times of the file
    """
    with open(touched_filename, "a"):
        os.utime(touched_filename, times)


def touch_dir(touched_dir: str) -> None:
    """
    Touches directory, i.e. if it exists it does nothing and
    if the directory does not exist, then it creates it.

    :param touched_dir: path that will be touched
    """
    if not os.path.exists(touched_dir):
        os.makedirs(touched_dir)


def path_to_subpaths(path: str) -> list[str]:
    """Breaks path to all the subpaths, i.e. all the prefixes of the given path.

    >>> path_to_subpaths('/dir/subdir/subsubdir')
    ['/dir', '/dir/subdir', '/dir/subdir/subsubdir']

    :param path: path separated by os.sep separator
    :return: list of subpaths
    """
    components = os.path.abspath(path).split(os.sep)
    return [os.sep + components[0]] + [
        os.sep.join(components[:till]) for till in range(2, len(components) + 1)
    ]


def locate_perun_dir_on(path: str) -> str:
    """Locates the nearest perun directory

    Locates the nearest perun directory starting from the @p path. It walks all
    subpaths sorted by their length and checks if .perun directory exists there.

    :param path: starting point of the perun dir search
    :return: path to perun dir or "" if the path is not underneath some underlying perun
        control
    """
    perun_dir = locate_dir_on(path, ".perun")
    if perun_dir == "":
        raise NotPerunRepositoryException(path)
    return perun_dir


def locate_dir_on(path: str, searched_dir: str) -> str:
    """Locates the nearest directory containing the other directory

    :param path: starting point of the search
    :param path: dir we are searching
    :return: path to dir or "" if the path is not underneath some underlying perun control
    """
    # convert path to subpaths and reverse the list so deepest subpaths are traversed first
    lookup_paths = path_to_subpaths(path)[::-1]

    for tested_path in lookup_paths:
        if os.path.isdir(tested_path) and searched_dir in os.listdir(tested_path):
            return tested_path
    return ""


def try_convert(value: Any, list_of_types: list[type]) -> Any:
    """Tries to convert a value into one of the specified types

    :param value: object that is going to be converted to one of the types
    :param list_of_types: list or tuple of supported types
    :return: converted value or None, if conversion failed for all the types
    """
    for checked_type in list_of_types:
        try:
            return checked_type(value)
        except Exception:
            continue


def try_min(lhs: Optional[int | float], rhs: int | float) -> int | float:
    """Returns minimum if lhs is not None

    :param lhs: optional left side
    :param rhs: right side
    :return: minimum of two numbers or right number
    """
    return rhs if lhs is None else min(lhs, rhs)


def identity(*args: Any) -> Any:
    """Identity function, that takes the arguments and return them as they are

    Note that this is used as default transformator for to be used in arguments for transforming
    the data.

    :param args: list of input arguments
    :return: non-changed list of arguments
    """
    # Unpack the tuple if it is single
    return args if len(args) > 1 else args[0]


def safe_match(pattern: re.Pattern[str], searched_string: str, default: str) -> str:
    """Safely matches groups in searched string; if string not found returns @p default

    :param pattern: compiled regular expression pattern
    :param searched_string: searched string
    :param default: default value returned if no match is found
    :return: matched value or default
    """
    match = pattern.search(searched_string)
    return match.group() if match else default


def sanitize_filepart(part: str) -> str:
    """Helper function for sanitization of part of the filenames

    :param part: part of the filename, that needs to be sanitized, i.e. we are removing invalid characters
    :return: sanitized string representation of the part
    """
    invalid_characters = r"# %&{}\<>*?/ $!'\":@"
    return "".join("_" if c in invalid_characters else c for c in str(part))


def safe_division(dividend: float, divisor: float) -> float:
    """Safe division of dividend by operand

    :param dividend: upper operand of the division
    :param divisor: lower operand of the division, may be zero
    :return: safe value after division of approximated zero
    """
    try:
        return dividend / divisor
    except (ZeroDivisionError, ValueError):
        return dividend / tools.APPROX_ZERO


def chunkify(generator: Iterable[Any], chunk_size: int) -> Iterable[Any]:
    """Slice generator into multiple generators and each generator yields up to chunk_size items.

    Source: https://stackoverflow.com/questions/24527006/split-a-generator-into-chunks-without-pre-walking-it

    Example: chunkify(it, 100); it generates a total of 450 elements:
        _it0: 100,
        _it1: 100,
        _it2: 100,
        _it3: 100,
        _it4: 50

    :param generator: a generator object
    :param chunk_size: the maximum size of each chunk
    :return: a generator object
    """
    for first in generator:
        yield itertools.chain([first], itertools.islice(generator, chunk_size - 1))


def abs_in_absolute_range(value: float, border: float) -> bool:
    """Tests if value is in absolute range as follows:

    -border <= value <= border

    :param value: tests if the
    :param border:
    :return: true if the value is in absolute range
    """
    return -abs(border) <= value <= abs(border)


def abs_in_relative_range(value: float, range_val: float, range_rate: float) -> bool:
    """Tests if value is in relative range as follows:

    (1 - range_rate) * range_val <= value <= (1 + range_rate) * range_val

    :param value: value we are testing if it is in the range
    :param range_val: value which gives the range
    :param range_rate: the rate in percents which specifies the range
    :return: true if the value is in relative range
    """
    range_rate = range_rate if 0.0 <= range_rate <= 1.0 else 0.0
    return abs((1.0 - range_rate) * range_val) <= abs(value) <= abs((1.0 + range_rate) * range_val)


def merge_dictionaries(*args: dict[Any, Any]) -> dict[Any, Any]:
    """Helper function for merging range (list, ...) of dictionaries to one to be used as oneliner.

    :param args: list of dictionaries
    :return: one merged dictionary
    """
    res = {}
    for dictionary in args:
        res.update(dictionary)
    return res


def match_dicts_by_keys(
    lhs: dict[KT, VT], rhs: dict[KT, VT]
) -> dict[KT, tuple[VT, VT | None] | tuple[VT | None, VT]]:
    """Match and merge the keys and values from two dictionaries into a single one.

    Keys that are in both dictionaries will store a tuple of the lhs and rhs values. Keys that are
    in either but not both dictionaries will store a tuple of the lhs or rhs value and a None.

    :param lhs: the first dictionary
    :param rhs: the second dictionary

    :return: the merged dictionary with matched keys and values
    """
    match_map: dict[KT, tuple[VT, VT | None] | tuple[VT | None, VT]] = {}
    for lhs_key, lhs_item in lhs.items():
        match_map[lhs_key] = (lhs_item, rhs.get(lhs_key, None))
    for rhs_key, rhs_item in rhs.items():
        if rhs_key not in match_map:
            match_map[rhs_key] = (None, rhs_item)
    return match_map


def partition_list(
    input_list: Iterable[Any], condition: Callable[[Any], bool]
) -> tuple[list[Any], list[Any]]:
    """Utility function for list partitioning on a condition so that the list is not iterated
    twice and the condition is evaluated only once.

    Based on a SO answer featuring multiple methods and their performance comparison:
    'https://stackoverflow.com/a/31448772'

    :param input_list: the input list to be partitioned
    :param condition: the condition that should be evaluated on every list item
    :return: (list of items evaluated to True, list of items evaluated to False)
    """
    good, bad = [], []
    for item in input_list:
        if condition(item):
            good.append(item)
        else:
            bad.append(item)
    return good, bad


def get_module(module_name: str) -> types.ModuleType:
    """Finds module by its name.

    :param module_name: dynamically load a module (but first check the cache)
    :return: loaded module
    """
    if module_name not in MODULE_CACHE.keys():
        MODULE_CACHE[module_name] = importlib.import_module(module_name)
    return MODULE_CACHE[module_name]


def compact_convert_list_to_str(
    number_list: list[int | float] | array.array[float] | array.array[int], float_precision: int = 2
) -> list[str]:
    """Converts list to list of compact strings

    :param number_list: list of numbers
    :param float_precision: float precision of the numbers
    :return: list of compact strings
    """
    return [compact_convert_num_to_str(num, 2) for num in number_list]


def compact_convert_num_to_str(number: int | float, float_precision: int = 2) -> str:
    """Converts the number to the smallest string possible

    :param number: converted number
    :param float_precision: float precision, i.e. number of decimal places in number
    :return: compact string
    """
    return str(to_compact_num(number, float_precision))


def to_compact_num(number: int | float, float_precision: int = 2) -> int | float:
    """Converts the number to the smallest string possible

    :param number: converted number
    :param float_precision: float precision, i.e. number of decimal places in number
    :return: compact num
    """
    if isinstance(number, int):
        return number
    elif number.is_integer():
        return int(number)
    else:
        return round(number, float_precision)


@contextlib.contextmanager
def disposable_resources(disposable: Any) -> Any:
    """Helper context manager that disposes of the passed object

    Disclaimers:
      1) So far, we have no tangible proof this helps in any way, however, it could potentially,
         reduce the memory peak of the application, if some huge file is kept in memory yet not
         used anymore.
      2) Usually, the GC is smarter than you, so it knows when it is the right time for collecting
         this actually could increase some time (hopefully traded by the memory footprint)

    :param disposable: object that should be disposed immediately
    :return: object
    """
    try:
        yield disposable
    except Exception:
        # Re-raise the encountered exception
        raise
    finally:
        del disposable


def binary_search(
    values: list[Any], value: Any, low: int, high: int, key: Callable[[Any], Any] = lambda x: x
) -> int:
    """Classical binary search algorithm

    Note: while bisect implements this functionality, for Python 3.9 it does not support
       the key parameter, that is unfortunately needed here.

    :param values: list of any values
    :param value: value for which we are looking up the insertion point
    :param key: key used for getting the key
    :param low: left pivot
    :param high: right pivot
    :return: insertion point for the value in values
    """
    while low <= high:
        mid = low + (high - low) // 2
        if key(value) == key(values[mid]):
            return mid + 1
        elif key(value) > key(values[mid]):
            low = mid + 1
        else:
            high = mid - 1
    return low


def add_to_sorted(
    values: list[Any], value: Any, key: Callable[[Any], Any] = lambda x: x, max_pick: int = -1
) -> None:
    """Adds a value to sorted list; the list is sorted wrt key function

    :param values: list of values of type T
    :param value: value that is added to the list of values
    :param key: function for addding to the value
    :param max_pick: picks at maximum max_pick elements
    """
    insert_point = binary_search(values, value, 0, len(values) - 1, key)
    values.insert(insert_point, value)
    if max_pick >= 0 and len(values) > max_pick:
        values.pop(0)


def hide_generics(uid: str) -> str:
    """Hides the generics in the uid

    This transforms std::<std::<type>> into std::<*>

    :param uid: uid with generics
    :return: uid without generics
    """
    nesting = 0
    chars = []
    for c in uid:
        if c == "<":
            nesting += 1
        elif c == ">":
            nesting -= 1
        if nesting == 0 or (c == "<" and nesting == 1):
            chars.append(c)
    return "".join(chars)


def ensure_type(obj: Any, target_type: Type[T]) -> T:
    """Ensures that object is of target type

    :param obj: object we are retyping
    :param target_type: type to which we are retyping, unless obj is already of the type
    :return: retyped object
    """
    if isinstance(obj, target_type):
        return obj
    return target_type(obj)  # type: ignore


def aggregate_list(
    input_list: list[float],
    aggregation: Literal["sum", "min", "max", "avg", "mean", "med", "median"],
) -> float:
    """Aggregates list of values according to the given function

    :param input_list: list of input values
    :param aggregation: named aggregation function
    :return: aggregation of the function
    """
    if aggregation == "sum":
        return sum(input_list)
    elif aggregation == "min":
        return min(input_list)
    elif aggregation == "max":
        return max(input_list)
    elif aggregation in ("avg", "mean"):
        return statistics.mean(input_list)
    elif aggregation in ("med", "median"):
        return statistics.median(input_list)
    assert False, f"Unknown aggregation {aggregation}"


MODULE_CACHE: dict[str, types.ModuleType] = {}
