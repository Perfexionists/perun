"""Set of helper function for logging and printing warnings or errors"""

from __future__ import annotations

# Standard Imports
from typing import Any, Callable, TYPE_CHECKING, Iterable, Optional, TextIO, Type, NoReturn, TypeVar
import builtins
import collections
import functools
import io
import itertools
import logging
import operator
import pydoc
import sys
import time
import traceback

# Third-Party Imports
import numpy as np
import progressbar
import termcolor

# Perun Imports
from perun.utils import decorators
from perun.utils.common import common_kit
from perun.utils.common.common_kit import (
    DEGRADATION_ICON,
    OPTIMIZATION_ICON,
    CHANGE_CMD_COLOUR,
    CHANGE_TYPE_COLOURS,
    AttrChoiceType,
    ColorChoiceType,
)
from perun.utils.structs.common_structs import (
    PerformanceChange,
    DegradationInfo,
    MinorVersion,
    CHANGE_COLOURS,
    CHANGE_STRINGS,
)

if TYPE_CHECKING:
    import types
    import numpy.typing as npt


VERBOSITY: int = 0
LOGGING: bool = False
COLOR_OUTPUT: bool = True
CURRENT_INDENT: int = 0
# Note: We set this to False during testing, since it screws the tests, however,
# in stdout and real usage we want this to not interleave the output
REDIRECT_STDOUT_IN_PROGRESS: bool = True

# Enum of verbosity levels
VERBOSE_DEBUG: int = 2
VERBOSE_INFO: int = 1
VERBOSE_RELEASE: int = 0

SUPPRESS_WARNINGS: bool = False
SUPPRESS_PAGING: bool = True

T = TypeVar("T")


def increase_indent() -> None:
    """Increases the indent for minor and major steps"""
    global CURRENT_INDENT
    CURRENT_INDENT += 1


def decrease_indent() -> None:
    """Increases the indent for minor and major steps"""
    global CURRENT_INDENT
    CURRENT_INDENT -= 1


def is_verbose_enough(verbosity_peak: int) -> bool:
    """Tests if the current verbosity of the log is enough

    :param verbosity_peak: peak of the verbosity we are testing
    :return: true if the verbosity is enough
    """
    return VERBOSITY >= verbosity_peak


def page_function_if(func: Callable[..., Any], paging_switch: bool) -> Callable[..., Any]:
    """Adds paging of the output to standard stream

    This decorator serves as a pager for long outputs to the standard stream. As a pager currently,
    'less -R' is used. Further extension to Windows and weird terminals without less -R is planned.

    Fixme: Try the paging on windows
    Fixme: Uhm, what about standard error?

    Note that this should be used by itself but by @paged_function() decorator

    :param func: original wrapped function that will be paged
    :param paging_switch: external paging condition, if set to tru the function will not be
        paged
    """

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        """Wrapper for the original function whose output will be paged

        :param args: list of positional arguments for original function
        :param kwargs: dictionary of key:value arguments for original function
        """
        if SUPPRESS_PAGING or not paging_switch:
            return func(*args, **kwargs)

        # Replace the original standard output with string buffer
        sys.stdout = io.StringIO()

        # Run the original input with positional and key-value arguments
        result = func(*args, **kwargs)

        # Read the caught standard output and then restore the original stream
        sys.stdout.seek(0)
        stdout_str = "".join(sys.stdout.readlines())
        sys.stdout = sys.__stdout__
        pydoc.pipepager(stdout_str, "less -R")

        return result

    return wrapper


def paged_function(paging_switch: bool) -> Callable[..., Any]:
    """The wrapper of the ``page_function_if`` to serve as a decorator, which partially applies the
    paging_switch. This way the function will accept only the function as parameter and can serve as
    decorator.

    :param paging_switch: external paging condition, if set to tru the function will not be
    :return: wrapped paged function
    """
    return functools.partial(page_function_if, paging_switch=paging_switch)


def _log_msg(
    stream: Callable[[int, str], None], msg: str, msg_verbosity: int, log_level: int
) -> None:
    """
    If the @p msg_verbosity is smaller than the set verbosity of the logging
    module, the @p msg is printed to the log with the given @p log_level

    :param stream: streaming function of the type void f(log_level, msg)
    :param msg: message to be logged if certain verbosity is set
    :param msg_verbosity: level of the verbosity of the message
    :param log_level: log level of the message
    """
    if msg_verbosity <= VERBOSITY:
        stream(log_level, msg)


def msg_to_stdout(message: str, msg_verbosity: int, log_level: int = logging.INFO) -> None:
    """
    Helper function for the log_msg, prints the @p msg to the stdout,
    if the @p msg_verbosity is smaller or equal to actual verbosity.
    """
    _log_msg(lambda lvl, msg: print(f"{msg}"), message, msg_verbosity, log_level)


def msg_to_file(msg: str, msg_verbosity: int, log_level: int = logging.INFO) -> None:
    """
    Helper function for the log_msg, prints the @p msg to the log,
    if the @p msg_verbosity is smaller or equal to actual verbosity
    """
    _log_msg(logging.log, msg, msg_verbosity, log_level)


def extract_stack_frame_info(frame: traceback.FrameSummary) -> tuple[str, str]:
    """Helper function for returning name and filename from frame.

    Note that this is needed because of fecking differences between Python 3.4 and 3.5

    :param frame: some fecking frame object
    :return: tuple of filename and function name
    """
    return (frame[0], frame[1]) if isinstance(frame, tuple) else (frame.filename, frame.name)


def print_current_stack(
    colour: ColorChoiceType = "red", raised_exception: Optional[BaseException] = None
) -> None:
    """Prints the information about stack track leading to an event

    Be default this is used in error traces, so the colour of the printed trace is red.
    Moreover, we filter out some of the events (in particular those outside of perun, or
    those that takes care of the actual trace).

    :param colour: colour of the printed stack trace
    :param raised_exception: exception that was raised before the error
    """
    reduced_trace = []
    trace = (
        traceback.extract_tb(raised_exception.__traceback__)
        if raised_exception
        else traceback.extract_stack()
    )
    for frame in trace:
        frame_file, frame_name = extract_stack_frame_info(frame)
        filtering_conditions = [
            # We filter frames that are not in perun's scope
            "perun" not in frame_file,
            # We filter the first load entry of the module
            frame_name == "<module>",
            # We filter these error and stack handlers ;)
            frame_file.endswith("log.py") and frame_name in ("error", "print_current_stack"),
        ]
        if not any(filtering_conditions):
            reduced_trace.append(frame)
    print(in_color("".join(traceback.format_list(reduced_trace)), colour), file=sys.stderr)


def write(msg: str, end: str = "\n") -> None:
    """
    :param msg: info message that will be printed only when there is at least lvl1 verbosity
    :param end:
    """
    print(f"{msg}", end=end)


def error_msg(
    msg: str,
    raised_exception: Optional[BaseException] = None,
) -> None:
    """Prints error message
    :param msg: error message printed to standard output
    :param raised_exception: exception that was raised before the error
    """
    print(f"{tag('error', 'red')} {in_color(msg, 'red')}", file=sys.stderr)
    if is_verbose_enough(VERBOSE_DEBUG):
        print_current_stack(raised_exception=raised_exception)


def error(
    msg: str,
    raised_exception: Optional[BaseException] = None,
) -> NoReturn:
    """Prints error and exits

    :param msg: error message printed to standard output
    :param raised_exception: exception that was raised before the error
    """
    error_msg(msg, raised_exception)
    sys.exit(1)


def warn(msg: str, end: str = "\n") -> None:
    """
    :param msg: warn message printed to standard output
    :param end:
    """
    if not SUPPRESS_WARNINGS:
        print(f"{tag('warning', 'yellow')} {msg}", end=end)


@decorators.static_variables(current_job=1)
def print_job_progress(overall_jobs: int) -> None:
    """Print the tag with the percent of the jobs currently done

    :param overall_jobs: overall number of jobs to be done
    """
    percentage_done = round((print_job_progress.current_job / overall_jobs) * 100)
    minor_status("Progress of the job", status=f"{str(percentage_done).rjust(3, ' ')}%")
    print_job_progress.current_job += 1


def cprint(
    string: str, colour: ColorChoiceType, attrs: Optional[AttrChoiceType] = None, flush: bool = True
) -> None:
    """Wrapper over coloured print without adding new line

    :param string: a printed coloured string
    :param colour: colour that will be used to colour the string
    :param attrs: name of additional attributes for the colouring
    :param flush: set True to immediately perform print operation
    """
    print(in_color(string, colour, attrs), end="", flush=flush)


def cprintln(string: str, colour: ColorChoiceType, attrs: Optional[AttrChoiceType] = None) -> None:
    """Wrapper over coloured print with added new line or other ending

    :param string: string that is printed with colours and newline
    :param colour: colour that will be used to colour the string
    :param attrs: name of additional attributes for the colouring
    """
    print(in_color(string, colour, attrs))


def tick(tick_symbol: str = ".") -> None:
    """Prints single dot or other symbol

    :param tick_symbol: symbol printed as tick
    """
    print(tick_symbol, end="")


def skipped(ending: str = "\n") -> None:
    """
    :param ending: end of the string, by default new line
    """
    write(in_color("skipped", color="light_grey", attribute_style=["bold"]), end=ending)


def major_info(msg: str, colour: ColorChoiceType = "blue", no_title: bool = False) -> None:
    """Prints major information, formatted in brackets [], in bold and optionally in color

    :param msg: printed message
    :param no_title: if set to true, then the title will be printed as it is
    :param colour: optional colour
    """
    stripped_msg = msg.strip() if no_title else msg.strip().title()
    printed_msg = "[" + in_color(stripped_msg, colour, attribute_style=["bold"]) + "]"
    newline()
    write(" " * CURRENT_INDENT * 2 + printed_msg)
    newline()


def minor_status(msg: str, status: str = "", sep: str = "-") -> None:
    """Prints minor status containing of two pieces of information: action and its status

    It prints the status of some action, starting with `-` with indent and ending with newline.

    Note, that there are some sanitizations happening to the message:
      1. Leading and trailing whitespace characters will be stripped;
      2. The first character will be made uppercase, if possible.

    :param msg: message to print, will be sanitized
    :param status: status of the info
    :param sep: separator used to separate the info with its results
    """
    write(
        " " * CURRENT_INDENT * 2 + f" - {common_kit.capitalize_first(msg.strip())} {sep} {status}"
    )


def minor_info(msg: str, end: str = "\n") -> None:
    """Prints minor information, formatted with indent and starting with -

    Note, that there are some sanitizations happening:
      1. Leading and trailing whitespace characters will be stripped;
      2. The first character will be made uppercase, if possible;
      3. If the message ends with a new line, we add a punctuation.

    :param msg: message to print, will be sanitized
    :param end: ending of the message
    """
    msg = common_kit.capitalize_first(msg.strip())
    if end == "\n" and msg[-1] not in ".!;":
        msg += "."
    write(" " * CURRENT_INDENT * 2 + f" - {msg}", end)


def minor_fail(msg: str, fail_message: str = "failed") -> None:
    """Helper function for shortening some messages"""
    minor_status(msg, status=failed_highlight(fail_message))


def minor_success(msg: str, success_message: str = "succeeded") -> None:
    """Helper function for shortening some messages"""
    minor_status(msg, status=success_highlight(success_message))


def tag(tag_str: str, colour: ColorChoiceType) -> str:
    """
    :param tag_str: printed tag
    :param colour: colour of the tag
    :param ending: end of the string, by default new line
    :return: formatted tag
    """
    return "[" + in_color(tag_str.upper(), colour, attribute_style=["bold"]) + "]"


def newline() -> None:
    """
    Prints blank line
    """
    print("")


def path_style(path_str: str) -> str:
    """Unified formatting and colouring of the path.

    :param path_str: string that corresponds to path
    :return: stylized path string
    """
    return in_color(path_str, "yellow", attribute_style=["bold"])


def cmd_style(cmd_str: str) -> str:
    """Unified formatting and colouring of the commands

    :param cmd_str: string that corresponds to command that should be run in terminal
    :return: stylized command string
    """
    return in_color(f"`{cmd_str}`", "light_grey")


def highlight(highlighted_str: str) -> str:
    """Highlights the string

    :param highlighted_str: string that will be highlighted
    :return: highlighted string
    """
    return in_color(highlighted_str, "blue", attribute_style=["bold"])


def success_highlight(highlighted_str: str) -> str:
    """Highlights of the string that is considered successful

    :param highlighted_str: string that will be highlighted
    :return: highlighted string
    """
    return in_color(highlighted_str, "green", attribute_style=["bold"])


def failed_highlight(highlighted_str: str) -> str:
    """Highlights of the string that is considered failure

    :param highlighted_str: string that will be highlighted
    :return: highlighted string
    """
    return in_color(highlighted_str, "red", attribute_style=["bold"])


def in_color(
    output: str, color: ColorChoiceType = "white", attribute_style: Optional[AttrChoiceType] = None
) -> str:
    """Transforms the output to colored version.

    :param output: the output text that should be colored
    :param color: the color
    :param attribute_style: name of the additional style, i.e. bold, italic, etc.

    :return: the new colored output (if enabled)
    """
    if COLOR_OUTPUT:
        return termcolor.colored(output, color, attrs=attribute_style, force_color=True)
    else:
        return output


def count_degradations_per_group(
    degradation_list: list[tuple[DegradationInfo, str, str]],
) -> dict[str, int]:
    """Counts the number of optimizations and degradations

    :param degradation_list: list of tuples of (degradation info, cmdstr, minor version)
    :return: dictionary mapping change strings to its counts
    """
    # Get only degradation results
    changes = map(operator.attrgetter("result"), map(operator.itemgetter(0), degradation_list))
    # Transform the enum into a string
    change_names = list(map(operator.attrgetter("name"), changes))
    counts = dict(collections.Counter(change_names))
    return counts


def get_degradation_change_colours(
    degradation_result: PerformanceChange,
) -> tuple[ColorChoiceType, ColorChoiceType]:
    """Returns the tuple of two colours w.r.t degradation results.

    If the change was optimization (or possible optimization) then we print the first model as
    red and the other by green (since we went from better to worse model). On the other hand if the
    change was degradation, then we print the first one green (was better) and the other as red
    (is now worse). Otherwise, (for Unknown and no change) we keep the stuff yellow, though this
    is not used at all

    :param degradation_result: change of the performance
    :returns: tuple of (from model string colour, to model string colour)
    """
    colour: tuple[ColorChoiceType, ColorChoiceType] = "yellow", "yellow"
    if degradation_result in (
        PerformanceChange.TotalOptimization,
        PerformanceChange.SevereOptimization,
        PerformanceChange.Optimization,
        PerformanceChange.MaybeOptimization,
    ):
        colour = "red", "green"
    elif degradation_result in (
        PerformanceChange.TotalDegradation,
        PerformanceChange.SevereDegradation,
        PerformanceChange.Degradation,
        PerformanceChange.MaybeDegradation,
    ):
        colour = "green", "red"
    return colour


def print_short_summary_of_degradations(
    degradation_list: list[tuple[DegradationInfo, str, str]],
) -> None:
    """Prints a short string representing the summary of the found changes.

    This prints a short statistic of found degradations and short summary string.

    :param degradation_list:
        list of tuples (degradation info, command string, source minor version)
    """
    counts = count_degradations_per_group(degradation_list)

    print_short_change_string(counts)
    optimization_count = common_kit.str_to_plural(
        counts.get("Optimization", 0) + counts.get("SevereOptimization", 0),
        "optimization",
    )
    degradation_count = common_kit.str_to_plural(
        counts.get("Degradation", 0) + counts.get("SevereDegradation", 0), "degradation"
    )
    print(f"{optimization_count}({OPTIMIZATION_ICON}), {degradation_count}({DEGRADATION_ICON})")


def change_counts_to_string(counts: dict[str, int], width: int = 0) -> str:
    """Transforms the counts to a single coloured string

    :param counts: dictionary with counts of degradations
    :param width: width of the string justified to left
    :return: string representing the counts of found changes
    """
    width = max(width - counts.get("Optimization", 0) - counts.get("Degradation", 0), 0)
    change_str = in_color(
        str(OPTIMIZATION_ICON * counts.get("Optimization", 0)),
        CHANGE_COLOURS[PerformanceChange.Optimization],
        ["bold"],
    )
    change_str += in_color(
        str(DEGRADATION_ICON * counts.get("Degradation", 0)),
        CHANGE_COLOURS[PerformanceChange.Degradation],
        ["bold"],
    )
    return change_str + width * " "


def print_short_change_string(counts: dict[str, int]) -> None:
    """Prints short string representing a summary of the given degradation list.

    This prints a short string of form representing a summary of found optimizations (+) and
    degradations (-) in the given degradation list. Uncertain optimizations and degradations
    are omitted. The string can e.g. look as follows:

    ++++-----

    :param counts: dictionary mapping found string changes into their counts
    """
    overall_changes = sum(counts.values())
    print(common_kit.str_to_plural(overall_changes, "change"), end="")
    if overall_changes > 0:
        change_string = change_counts_to_string(counts)
        print(f" | {change_string}", end="")
    newline()


def _print_models_info(deg_info: DegradationInfo) -> None:
    """
    The function prints information about both models from detection.

    This function prints available information about models at which
    was detected change, according to the applied strategy.
    Depends on the applied strategy it can log the type of
    parametric model (e.g. constant, linear, etc.) or kind of
    models (e.g. regressogram, constant, etc.). The function also
    prints information about confidence at detection, i.e. confidence
    rate and confidence type.

    :param deg_info: structures of found degradations with required information
    :param model_strategy: detection model strategy for obtains the relevant kind of models
    """

    def print_models_kinds(
        baseline_str: str,
        baseline_colour: ColorChoiceType,
        target_str: str,
        target_colour: ColorChoiceType,
        attrs: AttrChoiceType,
    ) -> None:
        """
        The function format the given parameters to required format at output.

        :param baseline_str: baseline kind of model (e.g. regressogram, constant, etc.)
        :param baseline_colour: baseline colour to print baseline string
        :param target_str: target kind of model (e.g. moving_average, linear, etc.)
        :param target_colour: target colour to print target string
        :param attrs: name of type attributes for the colouring
        """
        write(baseline_str, end="")
        cprint(f"{deg_info.from_baseline}", colour=baseline_colour, attrs=attrs)
        write(target_str, end="")
        cprint(f"{deg_info.to_target}", colour=target_colour, attrs=attrs)

    from_colour, to_colour = get_degradation_change_colours(deg_info.result)

    print_models_kinds(" from: ", from_colour, " -> to: ", to_colour, ["bold"])

    if deg_info.confidence_type != "no":
        write(" (with confidence ", end="")
        cprint(f"{deg_info.confidence_type} = {deg_info.confidence_rate}", "white", ["bold"])
        write(")", end="")


def _print_partial_intervals(
    partial_intervals: list[tuple[PerformanceChange, float, float, float]],
) -> None:
    """
    The function prints information about detected changes on the partial intervals.

    This function is using only when was used the `local-statistics` detection
    method, that determines the changes on the individual sub-intervals. The
    function prints the range of the sub-interval and the error rate on this
    sub-interval.

    :param partial_intervals: array with partial intervals and all required items
    """
    print("  \u2514 ", end="")
    for change_info, rel_error, x_start, x_end in aggregate_intervals(partial_intervals):
        if change_info != PerformanceChange.NoChange:
            cprint(
                f"<{x_start}, {x_end}> {rel_error}x; ",
                CHANGE_COLOURS.get(change_info, "white"),
            )
    newline()


def print_list_of_degradations(
    degradation_list: list[tuple[DegradationInfo, str, str]],
) -> None:
    """Prints list of found degradations grouped by location

    Currently, this is hardcoded and prints the list of degradations as follows:

    at {loc}:
      {result} from {from} -> to {to}

    :param degradation_list: list of found degradations
    """
    if not degradation_list:
        write("no changes found")
        return

    def keygetter(item: tuple[DegradationInfo, str, str]) -> str:
        """Returns the location of the degradation from the tuple

        :param item: tuple of (degradation result, cmd string, source minor version)
        :return: location of the degradation used for grouping
        """
        return item[0].location

    # Group by location
    degradation_list.sort(key=keygetter)
    for location, changes in itertools.groupby(degradation_list, keygetter):
        # Print the location
        write("at", end="")
        cprint(f" {location}", "white", attrs=["bold"])
        write(":")
        # Iterate and print everything
        for deg_info, cmd, __ in changes:
            write("\u2514 ", end="")
            if deg_info.rate_degradation_relative > 0.0 or deg_info.rate_degradation_relative < 0.0:
                cprint(
                    f"{round(deg_info.rate_degradation, 2)}ms ({round(deg_info.rate_degradation_relative, 2)}%)",
                    "white",
                    ["bold"],
                )
            else:
                cprint(f"{round(deg_info.rate_degradation, 2)}x", "white", ["bold"])
            write(": ", end="")
            cprint(deg_info.type, CHANGE_TYPE_COLOURS.get(deg_info.type, "white"))
            write(" ", end="")
            cprint(
                f"{CHANGE_STRINGS[deg_info.result]}",
                CHANGE_COLOURS[deg_info.result],
                ["bold"],
            )
            if deg_info.result != PerformanceChange.NoChange:
                _print_models_info(deg_info)

            # Print information about command that was executed
            write(" (", end="")
            cprint(f"$ {cmd}", CHANGE_CMD_COLOUR, ["bold"])
            write(")")

            # Print information about the change on the partial intervals (only at Local-Statistics)
            if len(deg_info.partial_intervals) > 0:
                _print_partial_intervals(deg_info.partial_intervals)
    newline()


def aggregate_intervals(
    input_intervals: list[Any] | npt.NDArray[Any],
) -> list[tuple[Any, Any, Any, Any]]:
    """
    Function aggregates the partial intervals according to the types of change.

    Fixme: This function is messy, and IMO buggy, needs to be fixed.

    The function aggregates the neighbourly partial intervals when they have the
    same detected type of change. Then the individual intervals are joined since
    in the whole interval are the same kind of the changes. For example, we can
    suppose the following intervals:

        - <0, 1>: Degradation; <1, 2> Degradation; <2, 3>: Optimization;
          <3, 4>: MaybeOptimization; <4, 5>: MaybeOptimization

    Then the resulting aggregated intervals will be the following:

        - <0, 2>: Degradation; <2, 3>: Optimization; <3, 5>: MaybeOptimization

    :param input_intervals: the array of partial intervals with tuples of required information
    :return: list of the aggregated partial intervals to print
    """
    # Fixme: This is baaaad. But the partial intervals are somewhat broken (sometimes list, sometimes narray)
    intervals = np.array(input_intervals) if isinstance(input_intervals, list) else input_intervals

    def get_indices_of_intervals() -> Iterable[tuple[int, int]]:
        """
        Function computes the indices of the aggregated intervals.

        The function iterates over the individual partial intervals and aggregates the
        neighbourly intervals when they have the same type of change. When the next
        interval has the different type of change, then the relevant indices of
        aggregated intervals are returned and proceeds to the next iteration.

        :return: function returns the indices of aggregate intervals.
        """
        if intervals.any():
            start_idx, end_idx = 0, 0
            change, _, _, _ = intervals[start_idx]
            for end_idx, (new_change, _, _, _) in enumerate(intervals[1:], 1):
                if change != new_change:
                    yield start_idx, end_idx - 1
                    if end_idx == len(intervals) - 1:
                        yield end_idx, end_idx
                    change = new_change
                    start_idx = end_idx
            if start_idx != end_idx or len(intervals) == 1:
                yield start_idx, end_idx

    intervals = intervals[intervals[:, 0] != PerformanceChange.NoChange]
    agg_intervals = []
    for start_index, end_index in get_indices_of_intervals():
        rel_error = np.sum(intervals[start_index : end_index + 1, 1]) / (
            end_index - start_index + 1
        )
        agg_intervals.append(
            (
                intervals[start_index][0],
                np.round(rel_error, 2),
                intervals[start_index][2],
                intervals[end_index][3],
            )
        )

    return agg_intervals


def print_elapsed_time(func: Callable[..., Any]) -> Callable[..., Any]:
    """Prints elapsed time after the execution of the wrapped function

    Takes the timestamp before the execution of the function and after the execution and prints
    the elapsed time to the standard output.

    :param func: function accepting any parameters and returning anything
    :return: function for which we will print the elapsed time
    """

    def inner_wrapper(*args: Any, **kwargs: Any) -> Any:
        """Inner wrapper of the decorated function

        :param args: original arguments of the function
        :param kwargs: original keyword arguments of the function
        :return: results of the decorated function
        """
        before = time.time()
        results = func(*args, **kwargs)
        elapsed = time.time() - before
        minor_status("Elapsed time", status=f"{elapsed:0.2f}s")

        return results

    return inner_wrapper


def scan_formatting_string(
    fmt: str,
    default_fmt_callback: Callable[[str], str],
    callback: Callable[[str], str] = common_kit.identity,
    sep: str = "%",
) -> list[tuple[str, str]]:
    """Scans the string, parses delimited formatting tokens and transforms them w.r.t callbacks

    :param fmt: formatting string
    :param callback: callback function for non formatting string tokens
    :param default_fmt_callback: default callback called for tokens not found in the callbacks
    :param sep: delimiter for the tokens
    :return: list of transformed tokens
    """
    i = 0
    tokens = []
    current_token = ""
    for character in fmt:
        if character == sep:
            # found start or end of the token
            i += 1
            if i % 2 == 0:
                # token is formatting string
                tokens.append(("fmt_string", default_fmt_callback(current_token)))
            else:
                # token is raw string
                tokens.append(("raw_string", callback(current_token)))
            current_token = ""
        else:
            current_token += character

    # Add what is rest
    if current_token:
        tokens.append(("raw_string", callback(current_token)))

    # TODO: Add check if there is i % 2 == 1 at the end
    return tokens


def format_file_size(size: Optional[float]) -> str:
    """Format file size in Bytes into a fixed-length output so that it can be easily printed.

    If size is set to 'None' then the function returns number of whitespace characters of the
    same width as if an actual value was supplied.

    Courtesy of 'https://stackoverflow.com/questions/1094841/reusable-library-to-get-human-
    readable-version-of-file-size'

    :param size: the size in Bytes

    :return: the formatted size for output
    """
    if size is None:
        return " " * 10
    for unit in ["", "Ki", "Mi", "Gi", "Ti"]:
        if abs(size) < 1024.0:
            if unit == "":
                return f"{size:6.0f} B  "
            return f"{size:6.1f} {unit}B"
        size /= 1024.0
    return f"{size:.1f} PiB"


def collector_to_command(collector_info: dict[str, Any]) -> str:
    """Converts the collector info dictionary into prettier one line command

    :param collector_info: dictionary with information about collector
    :return: prettified collector info
    """
    params = " ".join(
        f"--{param.replace('_', '-')}={val}"
        for (param, val) in collector_info.get("params", {}).items()
        if val
    )
    return f"{collector_info['name']} {params}"


def progress(collection: Iterable[T], description: str = "") -> Iterable[T]:
    """Wrapper for printing of any collection

    :param collection: any iterable
    :param description: tag on the left side of the output of the bar
    """
    widgets = [
        (description + ": ") if description else "",
        progressbar.Percentage(),
        " ",
        progressbar.Bar(),
        " [",
        progressbar.Timer(),
        ", ",
        progressbar.AdaptiveETA(),
        "]",
    ]
    yield from progressbar.progressbar(
        collection, redirect_stdout=REDIRECT_STDOUT_IN_PROGRESS, widgets=widgets
    )


class History:
    """Helper with wrapper, which is used when one wants to visualize the version control history
    of the project, printing specific stuff corresponding to a git history

    :ivar unresolved_edges: list of parents that needs to be resolved in the vcs graph,
        for each such parent, we keep one column.
    :ivar auto_flush_with_border: specifies whether in auto-flushing the border should be
        included in the output
    :ivar _original_stdout: original standard output that is saved and restored when leaving
    :ivar _saved_print: original print function which is replaced with flushed function
        and is restored when leaving the history
    """

    __slots__ = ["unresolved_edges", "auto_flush_with_border", "_original_stdout", "_saved_print"]

    class Edge:
        """Represents one edge of the history

        :ivar next: the parent of the edge, i.e. the previously processed sha
        :ivar colour: colour of the edge (red for deg, yellow for deg+opt, green for opt)
        :ivar prev: the child of the edge, i.e. the not yet processed sha
        """

        __slots__ = ["next", "colour", "prev"]

        def __init__(
            self, n: str, colour: ColorChoiceType = "white", prev: Optional[str] = None
        ) -> None:
            """Initiates one edge of the history

            :param n: the next sha that will be processed
            :param colour: colour of the edge
            :param prev: the "parent" of the n
            """
            self.next: str = n
            self.colour: ColorChoiceType = colour
            self.prev: Optional[str] = prev

        def to_ascii(self, char: str) -> str:
            """Converts the edge to ascii representation

            :param char: string that represents the edge
            :return: string representing the edge in ascii
            """
            return char if self.colour == "white" else in_color(char, self.colour, ["bold"])

    def __init__(self, head: str) -> None:
        """Creates a with wrapper, which keeps and prints the context of the current vcs
        starting at head

        :param head: head minor version
        """
        self.unresolved_edges: list[History.Edge] = [History.Edge(head)]
        self.auto_flush_with_border: bool = False
        self._original_stdout: TextIO = sys.stdout
        self._saved_print: Callable[..., Any] = builtins.print

    def __enter__(self) -> History:
        """When entering, we create a new string io object to catch standard output

        :return: the history object
        """
        # We will get the original standard output with string buffer and handle writing ourselves
        self._original_stdout = sys.stdout
        sys.stdout = io.StringIO()
        self._saved_print = builtins.print

        def flushed_print(
            print_function: Callable[..., Any], history: History
        ) -> Callable[..., Any]:
            """Decorates the print_function with automatic flushing of the output.

            Whenever a newline is included in the output, the stream will be automatically flushed

            :param print_function: function that will include the flushing
            :param history: history object that takes care of flushing
            :return: decorated flushed print
            """

            def wrapper(*args: Any, **kwargs: Any) -> None:
                """Decorator function for flushed print

                :param args: list of positional arguments for print
                :param kwargs: list of keyword arguments for print
                """
                print_function(*args, **kwargs)
                end_specified = "end" in kwargs.keys()
                if not end_specified or kwargs["end"] == "\n":
                    history.flush(history.auto_flush_with_border)

            return wrapper

        builtins.print = flushed_print(builtins.print, self)
        return self

    def __exit__(self, *_: Any) -> None:
        """Restores the stdout to the original state

        :param _: list of unused parameters
        """
        # Restore the stdout and printing function
        self.flush(self.auto_flush_with_border)
        builtins.print = self._saved_print
        sys.stdout = sys.__stdout__

    def get_left_border(self) -> str:
        """Returns the string representing the currently unresolved branches.

        Each unresolved branch is represented as a '|' characters

        The left border can e.g. look as follows:

        | | | | |

        :return: string representing the columns of the unresolved branches
        """
        return " ".join(edge.to_ascii("|") for edge in self.unresolved_edges) + "  "

    def _merge_parents(self, merged_parent: str) -> None:
        """Removes the duplicate instances of the merge parent.

        E.g. given the following parents:

            [p1, p2, p3, p2, p4, p2]

        End we merge the parent p2, then we will obtain the following:

            [p1, p2, p3, p4]

        This is used, when we are output the parent p2, and first we merged the branches, print
        the information about p2 and then actualize the unresolved parents with parents of p2.

        :param merged_parent: sha of the parent that is going to be merged in the unresolved
        """
        filtered_unresolved = []
        already_found_parent = False
        for parent in self.unresolved_edges:
            if parent.next == merged_parent and already_found_parent:
                continue
            already_found_parent = already_found_parent or parent.next == merged_parent
            filtered_unresolved.append(parent)
        self.unresolved_edges = filtered_unresolved

    def _print_minor_version(self, minor_version_info: MinorVersion) -> None:
        """Prints the information about minor version.

        The minor version is visualized as follows:

         | * | {sha:6} {desc}

        I.e. all unresolved parents are output as | and the printed parent is output as *.
        The further we print first six character of minor version checksum and first line of desc

        :param minor_version_info: printed minor version
        """
        minor_str = " ".join(
            "*" if p.next == minor_version_info.checksum else p.to_ascii("|")
            for p in self.unresolved_edges
        )
        print(minor_str, end="")
        cprint(f" {minor_version_info.checksum[:6]}", "yellow")
        print(": {} | ".format(minor_version_info.desc.split("\n")[0].strip()), end="")

    def progress_to_next_minor_version(self, minor_version_info: MinorVersion) -> None:
        r"""Progresses the history of the VCS to next minor version

        This flushes the current caught buffer, resolves the fork points (i.e. when we forked the
        history from the minor_version), prints the information about minor version and the resolves
        the merges (i.e. when the minor_version is spawned from the merge). Finally, this updates the
        unresolved parents with parents of minor_version.

        Prints the following:

        | | | |/ / /
        | | | * | | sha: desc
        | | | |\ \ \

        :param minor_version_info: information about minor version
        """
        minor_sha = minor_version_info.checksum
        self.flush(with_border=True)
        self.auto_flush_with_border = False
        self._process_fork_point(minor_sha)
        self._merge_parents(minor_sha)
        self._print_minor_version(minor_version_info)

    def finish_minor_version(
        self,
        minor_version_info: MinorVersion,
        degradation_list: list[tuple[DegradationInfo, str, str]],
    ) -> None:
        """Notifies that we have processed the minor version.

        Updates the unresolved parents, taints those where we found degradations and processes
        the merge points. Everything is flushed.

        :param minor_version_info: name of the finished minor version
        :param degradation_list: list of found degradations
        """
        # Update the unresolved parents
        minor_sha = minor_version_info.checksum
        version_index = common_kit.first_index_of_attr(self.unresolved_edges, "next", minor_sha)
        self.unresolved_edges[version_index : version_index + 1] = [
            History.Edge(p, "white", minor_sha) for p in minor_version_info.parents
        ]
        self._taint_parents(minor_sha, degradation_list)
        self._process_merge_point(version_index, minor_version_info.parents)

        # Flush the history
        self.flush()
        self.auto_flush_with_border = True

    def flush(self, with_border: bool = False) -> None:
        """Flushes the stdout optionally with left border of unresolved parent columns

        If the current stdout is not readable, the flushing is skipped

        :param with_border: if true, then every line is printed with the border of unresolved
            parents
        """
        # Unreadable stdout are skipped, since we are probably in silent mode
        if sys.stdout.readable():
            # flush the stdout
            sys.stdout.seek(0)
            for line in sys.stdout.readlines():
                if with_border:
                    self._original_stdout.write(self.get_left_border())
                self._original_stdout.write(line)

            # create new stringio
            sys.stdout = io.StringIO()

    def _taint_parents(
        self, target: str, degradation_list: list[tuple[DegradationInfo, str, str]]
    ) -> None:
        """According to the given list of degradation, sets the parents either as tainted
        or fixed.

        Tainted parents are output with red colour, while fixed parents with green colour.

        :param target: target minor version
        :param degradation_list: list of found degradations
        """
        # First we process all the degradations and optimization
        taints = set()
        fixes = set()
        for deg, _, baseline in degradation_list:
            if deg.result.name == "Degradation":
                taints.add(baseline)
            elif deg.result.name == "Optimization":
                fixes.add(baseline)

        # At last, we colour the edges; edges that contain both optimizations and degradations
        # are coloured yellow
        for edge in self.unresolved_edges:
            if edge.prev == target:
                tainted = edge.next in taints
                fixed = edge.next in fixes
                edge.colour = "white"
                if tainted:
                    edge.colour = "yellow" if fixed else "red"
                elif fixed:
                    edge.colour = "green"

    def _process_merge_point(self, merged_at: int, merged_parents: list[str]) -> None:
        r"""Updates the printed tree after we merged list of parents in the given merge_at index.

        This prints up to merged_at unresolved parents, and then creates a merge point (|\) that
        branches of to the length of the merged_parents columns.

        Prints the following:

        | | | * | | sha: desc
        | | | | \ \
        | | | |\ \ \
        | | | | | \ \
        | | | | |\ \ \
        | | | | | | \ \
        | | | | | |\ \ \
        | | | | | | | | |

        :param merged_at: index, where the merged has happened
        :param merged_parents: list of merged parents
        """
        parent_num = len(merged_parents)
        rightmost_branches_num = len(self.unresolved_edges) - merged_at - parent_num

        # We output one additional line for better readability; if we process some merges,
        # then we will have plenty of space left, so no need to do the newline
        if parent_num == 1:
            print(self.get_left_border())
        else:
            for _ in range(1, parent_num):
                merged_at += 1
                left_str = " ".join(e.to_ascii("|") for e in self.unresolved_edges[:merged_at])
                right_str = (
                    " ".join(
                        e.to_ascii("\\") for e in self.unresolved_edges[-rightmost_branches_num:]
                    )
                    if rightmost_branches_num
                    else ""
                )
                print(left_str + right_str)
                print(
                    left_str
                    + " ".join([self.unresolved_edges[merged_at].to_ascii("\\"), right_str])
                )

    def _process_fork_point(self, fork_point: str) -> None:
        """Updates the printed tree after we forked from the given sha.

        Prints the following:

        | | | | | | |
        | | | |/ / /
        | | | * | |

        :param fork_point: sha of the point, where we are forking
        """
        ulen = len(self.unresolved_edges)
        forked_index = common_kit.first_index_of_attr(self.unresolved_edges, "next", fork_point)
        src_index_map = list(range(0, ulen))
        tgt_index_map = [
            forked_index if self.unresolved_edges[i].next == fork_point else i
            for i in range(0, ulen)
        ]

        while src_index_map != tgt_index_map:
            line = list(" " * (max(src_index_map) + 1) * 2)
            triple_zip = zip(src_index_map, self.unresolved_edges, tgt_index_map)
            for i, (lhs, origin, rhs) in enumerate(triple_zip):
                # for this index we are moving to the left
                diff = -1 if rhs - lhs else 0
                if diff == 0:
                    line[2 * lhs] = origin.to_ascii("|")
                else:
                    line[2 * lhs - 1] = origin.to_ascii("/")
                src_index_map[i] += diff
            print("".join(line))


class Logger(TextIO):
    """Helper object that logs the stream into isolate string io

    :ivar original: original stream
    :ivar log: log saving the stream
    """

    __slots__ = ["original", "log"]

    @property
    def errors(self):
        return self.original.errors

    @property
    def encoding(self):
        return self.original.encoding

    def __init__(self, stream: TextIO) -> None:
        self.original: TextIO = stream
        self.log: io.StringIO = io.StringIO()

    def write(self, message: str) -> int:
        """Writes the message to both streams

        :param message: written message
        """
        result = self.original.write(message)
        self.original.flush()
        self.log.write(message)
        return result

    def flush(self) -> None:
        """Flushes the original stream"""
        self.original.flush()

    def close(self) -> None:  # type: ignore
        assert NotImplementedError("Function not supported in wrapper Logger")

    def fileno(self) -> int:  # type: ignore
        return self.original.fileno()

    def isatty(self) -> bool:
        return self.original.isatty()

    def read(self, __n: int = -1) -> None:  # type: ignore
        assert NotImplementedError("Function not supported in wrapper Logger")

    def readable(self) -> bool:
        return False

    def readline(self, __limit: int = -1) -> None:  # type: ignore
        assert NotImplementedError("Function not supported in wrapper Logger")

    def readlines(self, __hint: int = -1) -> None:  # type: ignore
        assert NotImplementedError("Function not supported in wrapper Logger")

    def seek(self, __offset: int, __whence: int = io.SEEK_SET) -> int:
        return self.original.seek(__offset, __whence)

    def seekable(self) -> bool:
        return self.original.seekable()

    def tell(self) -> int:
        return self.original.tell()

    def truncate(self, __size: int | None = None) -> int:
        return self.original.truncate(__size)

    def writable(self) -> bool:
        return self.original.writable()

    def writelines(self, __lines: Iterable[str]) -> None:
        self.original.writelines(__lines)

    def __next__(self) -> None:  # type: ignore
        assert NotImplementedError("Function not supported in wrapper Logger")

    def __iter__(self) -> None:  # type: ignore
        assert NotImplementedError("Function not supported in wrapper Logger")

    def __exit__(  # type: ignore
        self,
        __t: Type[BaseException] | None,
        __value: BaseException | None,
        __traceback: types.TracebackType | None,
    ) -> None:
        assert NotImplementedError("Function not supported in wrapper Logger")

    def __enter__(self) -> None:  # type: ignore
        assert NotImplementedError("Function not supported in wrapper Logger")
