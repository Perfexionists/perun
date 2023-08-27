"""Helper assertion function to be used in tests"""

import os
import traceback

__author__ = 'Tomas Fiedor'


def predicate_from_cli(cli_result, predicate):
    """Checks the correctness of the @p predicate.

    In case the predicate is violated, the function outputs additional helper information for
    debugging, since CliRunner of click captures the output. Currently, the function lists the
    captured output and trace leading to the error/exception (if raised).

    :param click.testing.Result cli_result: result object of
    :param bool predicate: predicate returning true or false
    """
    try:
        assert predicate
    except AssertionError as failed_assertion:
        if cli_result.output:
            print("=== Captured output ===")
            print(cli_result.output)
        print("=== Inner traceback ===")
        if cli_result.exception:
            print(cli_result.exception)
        traceback.print_tb(cli_result.exc_info[2])
        raise failed_assertion


def invalid_cli_choice(cli_result, choice, file=None):
    """Checks, that click correctly ended as invalid choice

    Arguments:
        cli_result(click.Result): result of the commandline interface
        choice(str): choice that we tried
        file(str): name of the file that should not be created (optional)
    """
    predicate_from_cli(cli_result, cli_result.exit_code == 2)
    predicate_from_cli(cli_result, f"'{choice}' is not one of" in cli_result.output)
    if file:
        assert file not in os.listdir(os.getcwd())


def invalid_param_choice(cli_result, choice, file=None):
    """Checks that click correctly ended with invalid choice and 1 return code
    Arguments:
        cli_result(click.Result): result of the commandline interface
        choice(str): choice that we tried
        file(str): name of the file that should not be created (optional)
    """
    predicate_from_cli(cli_result, cli_result.exit_code == 1)
    predicate_from_cli(cli_result, "Invalid value '{}'".format(choice) in cli_result.output)
    if file:
        assert file not in os.listdir(os.getcwd())
