"""Set of helper function for logging and printing warnings or errors"""

import logging
import sys
import termcolor
import io
import pydoc
import functools

from perun.utils.decorators import static_variables
from perun.utils.helpers import COLLECT_PHASE_ATTRS, COLLECT_PHASE_ATTRS_HIGH

__author__ = 'Tomas Fiedor'
VERBOSITY = 0

# Enum of verbosity levels
VERBOSE_DEBUG = 2
VERBOSE_INFO = 1
VERBOSE_RELEASE = 0

SUPPRESS_WARNINGS = False
SUPPRESS_PAGING = True

# set the logging for the perun
logging.basicConfig(filename='perun.log', level=logging.DEBUG)


def page_function_if(func, paging_switch):
    """Adds paging of the output to standard stream

    This decorator serves as a pager for long outputs to the standard stream. As a pager currently,
    'less -R' is used. Further extension to Windows and weird terminals without less -R is planned.

    Fixme: Try the paging on windows
    Fixme: Uhm, what about standard error?

    Note that this should be used by itself but by @paged_function() decorator

    :param function func: original wrapped function that will be paged
    :param bool paging_switch: external paging condition, if set to tru the function will not be
        paged
    """
    def wrapper(*args, **kwargs):
        """Wrapper for the original function whose output will be paged

        Arguments:
            args(list): list of positional arguments for original function
            kwargs(dict): dictionary of key:value arguments for original function
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


def paged_function(paging_switch):
    """The wrapper of the ``page_function_if`` to serve as a decorator, which partially applies the
    paging_switch. This way the function will accept only the function as parameter and can serve as
    decorator.

    :param bool paging_switch: external paging condition, if set to tru the function will not be
    :return: wrapped paged function
    """
    return functools.partial(page_function_if, paging_switch=paging_switch)


def _log_msg(stream, msg, msg_verbosity, log_level):
    """
    If the @p msg_verbosity is smaller than the set verbosity of the logging
    module, the @p msg is printed to the log with the given @p log_level

    Attributes:
        stream(function): streaming function of the type void f(log_level, msg)
        msg(str): message to be logged if certain verbosity is set
        msg_verbosity(int): level of the verbosity of the message
        log_level(int): log level of the message
    """
    if msg_verbosity <= VERBOSITY:
        stream(log_level, msg)


def msg_to_stdout(message, msg_verbosity, log_level=logging.INFO):
    """
    Helper function for the log_msg, prints the @p msg to the stdout,
    if the @p msg_verbosity is smaller or equal to actual verbosity.
    """
    _log_msg(lambda lvl, msg: print("{}".format(msg)), message, msg_verbosity, log_level)


def msg_to_file(msg, msg_verbosity, log_level=logging.INFO):
    """
    Helper function for the log_msg, prints the @p msg to the log,
    if the @p msg_verbosity is smaller or equal to actual verbosity
    """
    _log_msg(logging.log, msg, msg_verbosity, log_level)


def info(msg):
    """
    Arguments:
        msg(str): info message that will be printed only when there is at least lvl1 verbosity
    """
    print("info: {}".format(msg))


def quiet_info(msg):
    """
    Arguments:
        msg(str): info message to the stream that will be always shown
    """
    msg_to_stdout(msg, VERBOSE_RELEASE)


def error(msg, recoverable=False):
    """
    Arguments:
        msg(str): error message printe to standard output
        recoverable(bool): whether we can recover from the error
    """
    print(termcolor.colored("fatal: {}".format(msg), 'red'), file=sys.stderr)

    # If we cannot recover from this error, we end
    if not recoverable:
        exit(1)


def warn(msg):
    """
    Arguments:
        msg(str): warn message printed to standard output
    """
    if not SUPPRESS_WARNINGS:
        print("warn: {}".format(msg))


def print_current_phase(phase_msg, phase_unit, phase_colour):
    """Print helper coloured message for the current phase

    Arguments:
        phase_msg(str): message that will be printed to the output
        phase_unit(str): additional parameter that is passed to the phase_msg
        phase_colour(str): phase colour defined in helpers.py
    """
    print(termcolor.colored(
        phase_msg.format(
            termcolor.colored(phase_unit, attrs=COLLECT_PHASE_ATTRS_HIGH)
        ), phase_colour, attrs=COLLECT_PHASE_ATTRS
    ))


@static_variables(current_job=1)
def print_job_progress(overall_jobs):
    """Print the tag with the percent of the jobs currently done

    Arguments:
        overall_jobs(int): overall number of jobs to be done
    """
    percentage_done = round((print_job_progress.current_job / overall_jobs) * 100)
    print("[{}%] ".format(
        str(percentage_done).rjust(3, ' ')
    ), end='')
    print_job_progress.current_job += 1


def cprint(string, colour, attrs=None):
    """Wrapper over coloured print without adding new line

    Arguments:
        string(str): string that is printed with colours
        colour(str): colour that will be used to colour the string
        attrs(list): list of additional attributes for the colouring
    """
    attrs = attrs or []
    print(termcolor.colored(string, colour, attrs=attrs), end='')


def cprintln(string, colour, attrs=None, ending='\n'):
    """Wrapper over coloured print with added new line or other ending

    Arguments:
        string(str): string that is printed with colours and newline
        colour(str): colour that will be used to colour the stirng
        attrs(list): list of additional attributes for the colouring
        ending(str): ending of the string, be default new line
    """
    attrs = attrs or []
    print(termcolor.colored(string, colour, attrs=attrs), end=ending)


def done(ending='\n'):
    """Helper function that will print green done to the terminal

    Arguments:
        ending(str): end of the string, by default new line
    """
    print('[', end='')
    cprint("DONE", 'green', attrs=['bold'])
    print(']', end=ending)


def failed(ending='\n'):
    """
    Arguments:
        ending(str): end of the string, by default new line
    """
    print('[', end='')
    cprint("FAILED", 'red', attrs=['bold'])
    print(']', end=ending)
