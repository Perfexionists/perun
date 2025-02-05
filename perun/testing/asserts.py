"""Helper assertion function to be used in tests"""

from __future__ import annotations

# Standard Imports
from typing import Optional
import os
import traceback

# Third-Party Imports
import click.testing

# Perun Imports


def predicate_from_cli(cli_result: click.testing.Result | list[str] | str, predicate: bool) -> None:
    """Checks the correctness of the @p predicate.

    In case the predicate is violated, the function outputs additional helper information for
    debugging, since CliRunner of click captures the output. Currently, the function lists the
    captured output and trace leading to the error/exception (if raised).

    :param cli_result: result object of
    :param predicate: predicate returning true or false
    """
    try:
        assert predicate
    except AssertionError as failed_assertion:
        if hasattr(cli_result, "output") and cli_result.output:
            print("=== Captured output ===")
            print(cli_result.output)
        elif isinstance(cli_result, list):
            print("=== Captured output ===")
            print("".join(cli_result))
        else:
            print("=== Captured output ===")
            print(cli_result)
        print("=== Inner traceback ===")
        if hasattr(cli_result, "exception") and cli_result.exception:
            print(cli_result.exception)
        if hasattr(cli_result, "exc_info") and cli_result.exc_info is not None:
            traceback.print_tb(cli_result.exc_info[2])
        raise failed_assertion


def invalid_cli_choice(
    cli_result: click.testing.Result, choice: str, file: Optional[str] = None
) -> None:
    """Checks, that click correctly ended as invalid choice

    :param cli_result: result of the commandline interface
    :param choice: choice that we tried
    :param file: name of the file that should not be created (optional)
    """
    predicate_from_cli(cli_result, cli_result.exit_code == 2)
    predicate_from_cli(cli_result, f"'{choice}' is not one of" in cli_result.output)
    if file:
        assert file not in os.listdir(os.getcwd())


def invalid_param_choice(
    cli_result: click.testing.Result, choice: str, file: Optional[str] = None
) -> None:
    """Checks that click correctly ended with invalid choice and 1 return code

    :param cli_result: result of the commandline interface
    :param choice: choice that we tried
    :param file: name of the file that should not be created (optional)
    """
    predicate_from_cli(cli_result, cli_result.exit_code == 1)
    predicate_from_cli(cli_result, f"Invalid value '{choice}'" in cli_result.output)
    if file:
        assert file not in os.listdir(os.getcwd())


def perun_successfully_init_at(path: str) -> None:
    """Checks that the perun was successfully initialized at the given path

    param path: the path to the working directory
    """
    perun_dir = os.path.join(path, ".perun")
    perun_content = os.listdir(perun_dir)
    assert "cache" in perun_content
    assert "objects" in perun_content
    assert "jobs" in perun_content
    assert "logs" in perun_content
    assert "stats" in perun_content
    assert "tmp" in perun_content
    assert os.path.exists(os.path.join(perun_dir, "local.yml"))
    assert len(perun_content) == 7


def git_successfully_init_at(path, is_bare=False):
    """Checks that the git was successfully initialized at the given path

    param path: the path to the working directory
    param is_bare: indication whether the git was initialized as a bare repo
    """
    git_dir = os.path.join(path, "" if is_bare else ".git")
    git_content = os.listdir(git_dir)
    # On some versions of git, the 'branches' directory is not created
    assert 7 <= len(git_content) <= 8
    assert "hooks" in git_content
    assert "info" in git_content
    assert "objects" in git_content
    assert "refs" in git_content
    assert "config" in git_content
    assert "description" in git_content
    assert "HEAD" in git_content
