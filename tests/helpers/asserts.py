"""Helper assertion function to be used in tests"""
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
        traceback.print_tb(cli_result.exc_info[2])
        raise failed_assertion

