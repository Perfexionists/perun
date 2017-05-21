"""Set of helper function for logging and printing warnings or errors"""

import logging
import termcolor

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
    msg_to_stdout(msg, VERBOSE_INFO)


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
    print(termcolor.colored(
        "fatal: {}".format(msg)
    , 'red'))

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
