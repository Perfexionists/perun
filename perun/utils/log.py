"""Set of helper function for logging and printing warnings or errors"""

import logging
import sys
import termcolor

from perun.utils.decorators import static_variables

from perun.utils.helpers import COLLECT_PHASE_ATTRS, COLLECT_PHASE_ATTRS_HIGH

__author__ = 'Tomas Fiedor'
VERBOSITY = 0

# Enum of verbosity levels
VERBOSE_DEBUG = 2
VERBOSE_INFO = 1
VERBOSE_RELEASE = 0

SUPPRESS_WARNINGS = False

# set the logging for the perun
logging.basicConfig(filename='perun.log', level=logging.DEBUG)


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
