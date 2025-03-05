"""Basic tests for running the cli interface of the Perun

Note that the functionality of the commands themselves are not tested,
this is done in appropriate test files, only the API is tested."""

# Standard Imports
import os
import re
import shutil
import sys
import time
import warnings

# Third-Party Imports
from click.testing import CliRunner
from git.exc import GitCommandError
from subprocess import CalledProcessError
import git
import pytest

# Perun Imports
from perun import cli
from perun.cli_groups import utils_cli, config_cli, run_cli, check_cli, collect_cli
from perun.logic import config, pcs, stats, temp
from perun.testing import asserts
from perun.utils import exceptions, log
from perun.utils.common import common_kit
from perun.utils.external import commands
from perun.utils.structs.common_structs import CollectStatus, RunnerReport
from perun import check as check
import perun.testing.utils as test_utils


SIZE_REGEX = re.compile(r"([0-9]+ (Ki|Mi){0,1}B)")


def test_cli(monkeypatch, pcs_with_root):
    """Generic tests for cli, such as testing verbosity setting etc."""
    runner = CliRunner()

    log.VERBOSITY = log.VERBOSE_RELEASE
    runner.invoke(cli.cli, ["-v", "-v", "log"])
    assert log.VERBOSITY == log.VERBOSE_DEBUG

    # Testing calling cli groups withouth commands
    result = runner.invoke(cli.cli, ["utils"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    result = runner.invoke(utils_cli.utils_group, ["temp", "list"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    result = runner.invoke(utils_cli.utils_group, ["stats"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    result = runner.invoke(utils_cli.stats_group, ["delete", "file"])
    asserts.predicate_from_cli(result, result.exit_code == 2)

    # Restore the verbosity
    log.VERBOSITY = log.VERBOSE_RELEASE
    log.SUPPRESS_PAGING = True

    result = runner.invoke(cli.cli, ["--version"])
    asserts.predicate_from_cli(result, result.output.startswith("Perun"))
    asserts.predicate_from_cli(result, result.exit_code == 0)

    result = runner.invoke(cli.cli, ["--version"])
    result.exception = "exception"
    # Try that predicate from cli reraises
    with pytest.raises(AssertionError):
        asserts.predicate_from_cli(result, False)


def run_non_param_test(runner, test_params, expected_exit_code, expected_output):
    result = runner.invoke(cli.postprocessby, test_params)
    asserts.predicate_from_cli(result, result.exit_code == expected_exit_code)
    asserts.predicate_from_cli(result, expected_output in result.output)


def test_regressogram_incorrect(pcs_single_prof):
    """
    Test various failure scenarios for regressogram cli.

    Expecting no exceptions, all tests should end with status code 2.
    """
    incorrect_tests = [
        # Test non-existing argument
        {"params": ["-a"], "output": "No such option: -a"},
        # Test malformed bucket_number argument
        {
            "params": ["--buckets_numbers"],
            "output": "No such option: --buckets_numbers",
        },
        # Test missing bucket_number value
        {"params": ["-bn"], "output": "Option '-bn' requires an argument."},
        # Test invalid bucket_number value
        {"params": ["-bn", "user"], "output": "Invalid value"},
        # Test malformed bucket_method argument
        {
            "params": ["--buckets_methods"],
            "output": "No such option: --buckets_methods",
        },
        # Test missing bucket_method value
        {
            "params": ["--bucket_method"],
            "output": "Option '--bucket_method' requires an argument.",
        },
        # Test invalid bucket_method value
        {"params": ["-bm", "user"], "output": "Invalid value"},
        # Test malformed statistic_function argument
        {
            "params": ["--statistic_functions"],
            "output": "No such option: --statistic_functions",
        },
        # Test invalid model name
        {"params": ["-sf", "max"], "output": "Invalid value"},
        # Test missing statistic_function value
        {
            "params": ["--statistic_function"],
            "output": "Option '--statistic_function' requires an argument.",
        },
    ]
    # TODO: multiple values check

    # Instantiate the runner fist
    runner = CliRunner()

    # Set stable parameters at all tests
    regressogram_params = ["0@i", "regressogram"]
    # Executing the testing
    for incorrect_test in incorrect_tests:
        run_non_param_test(
            runner,
            regressogram_params + incorrect_test["params"],
            2,
            incorrect_test["output"],
        )


def test_regressogram_correct(pcs_single_prof):
    """
    Test correct usages of the regressogram cli.

    Expecting no exceptions and errors, all tests should end with status code 0.
    """
    # Instantiate the runner first
    runner = CliRunner()

    result = runner.invoke(cli.status, [])
    match = re.search(r"([0-9]+@i).*.perf", result.output)
    assert match
    cprof_idx = match.groups(1)[0]

    correct_tests = [
        # Test the help printout first
        {"params": ["--help"], "output": "Usage"},
        # Test default values of parameters (buckets, statistic_function)
        {"params": []},
        # Test first acceptable value for statistic_function parameter (mean)
        {"params": ["--statistic_function", "mean"]},
        # Test second acceptable value for statistic_function parameter (median)
        {"params": ["-sf", "median"]},
        # Test integer variant as value for bucket_number parameter
        {"params": ["--bucket_number", "10"]},
        # Test 'auto' method as value for bucket_method parameter
        {"params": ["-bm", "auto"]},
        # Test 'fd' method as value for bucket_method parameter
        {"params": ["-bm", "fd"]},
        # Test 'doane' method as value for bucket_method parameter
        {"params": ["--bucket_method", "doane"]},
        # Test 'scott' method as value for bucket_method parameter
        {"params": ["--bucket_method", "scott"]},
        # Test 'sturges' method as value for bucket_method parameter
        {"params": ["-bm", "sturges"]},
        # Test 'rice' method as value for bucket_method parameter
        {"params": ["-bm", "rice"]},
        # Test 'sqrt' method as value for bucket_method parameter
        {"params": ["--bucket_method", "sqrt"]},
        # Test complex variant for regressogram method
        {"params": ["--bucket_method", "doane", "--statistic_function", "mean"]},
        # Test bucket_method and bucket_number parameters common
        {"params": ["--bucket_method", "sqrt", "--bucket_number", 10]},
    ]

    # Set stable parameters at all tests
    regressogram_params = [cprof_idx, "regressogram"]
    # Performing tests
    for _, correct_test in enumerate(correct_tests):
        run_non_param_test(
            runner,
            regressogram_params + correct_test["params"],
            0,
            correct_test.get("output", "succeeded"),
        )


def moving_average_runner_test(runner, tests_set, tests_edge, exit_code, cprof_idx):
    # Set stable parameters at all tests
    moving_average_params = [cprof_idx, "moving-average"]
    # Set the supported methods at moving average postprocessor
    moving_average_methods = {0: [], 1: ["smm"], 2: ["sma"], 3: ["ema"], 4: []}
    # Executing the testing
    method_idx = 0
    for idx, test in enumerate(tests_set):
        if method_idx == 1:
            for n in range(method_idx, 3):
                run_non_param_test(
                    runner,
                    moving_average_params + moving_average_methods[n] + test["params"],
                    exit_code,
                    test.get("output", "succeeded"),
                )
        else:
            run_non_param_test(
                runner,
                moving_average_params + moving_average_methods[method_idx] + test["params"],
                exit_code,
                test.get("output", "succeeded"),
            )
        method_idx += 1 if idx + 1 == tests_edge[method_idx] else 0


def test_moving_average_incorrect(pcs_single_prof):
    """
    Test various failure scenarios for moving average cli.

    Expecting no exceptions, all tests should end with status code 2.
    """
    incorrect_tests = [
        # TESTS MOVING AVERAGE COMMAND AND OPTIONS
        # 1. Test non-existing argument
        {"params": ["--abcd"], "output": "No such option: --abcd"},
        # 2. Test non-existing command
        {"params": ["cma"], "output": "No such command"},
        # 3. Test non-existing argument
        {"params": ["-b"], "output": "No such option: -b"},
        # 4. Test malformed min_periods argument
        {"params": ["--min_period"], "output": "No such option: --min_period"},
        # 5. Test missing min_period value
        {"params": ["-mp"], "output": "Option '-mp' requires an argument."},
        # 6. Test invalid range min_periods value
        {"params": ["--min_periods", 0], "output": "Invalid value"},
        # 7. Test invalid value type min_periods value
        {"params": ["-mp", "A"], "output": "Invalid value"},
        # 8. Test malformed per_key argument
        {"params": ["--per-keys"], "output": "No such option: --per-keys"},
        # 9. Test missing per_key value
        {"params": ["-per"], "output": "Option '-per' requires an argument."},
        # 10. Test invalid value per_key arguments
        {"params": ["--per-key", "unknown"], "output": "Invalid value"},
        # 11. Test malformed of_key argument
        {"params": ["--off"], "output": "No such option: --off"},
        # 12. Test missing of_key value
        {"params": ["--of-key"], "output": "Option '--of-key' requires an argument."},
        # 13. Test invalid value of_key arguments
        {"params": ["-of", "unknown"], "output": "Invalid value"},
        # TESTS SIMPLE MOVING AVERAGE COMMAND AND SIMPLE MOVING MEDIAN COMMAND
        # 14. Test malformed window-width argument
        {"params": ["--window_widh"], "output": "No such option: --window_widh"},
        # 15. Test missing window-width value
        {"params": ["-ww"], "output": "Option '-ww' requires an argument."},
        # 16. Test invalid range window-width argument
        {"params": ["-ww", -1], "output": "Invalid value"},
        # 17. Test invalid value type window-width argument
        {"params": ["--window_width", 0.5], "output": "Invalid value"},
        # 18. Test malformed center argument
        {"params": ["--centers"], "output": "No such option: --centers"},
        # 19. Test malformed no-center argument
        {"params": ["--mo-center"], "output": "No such option: --mo-center"},
        # 20. Test value for center argument
        {
            "params": ["--center", "True"],
            "output": "Got unexpected extra argument (True)",
        },
        # 21. Test value for no-center argument
        {
            "params": ["--no-center", "False"],
            "output": "Got unexpected extra argument (False)",
        },
        # TESTS SIMPLE MOVING AVERAGE COMMAND
        # 22. Test malformed window-type argument
        {"params": ["--windov_type"], "output": "No such option: --windov_type"},
        # 23. Test missing window-type value
        {
            "params": ["--window_type"],
            "output": "Option '--window_type' requires an argument.",
        },
        # 24. Test invalid range window-type argument
        {"params": ["-wt", "boxcars"], "output": "Invalid value"},
        # TESTS EXPONENTIAL MOVING AVERAGE COMMAND
        # 25. Test malformed decay argument
        {"params": ["--decays"], "output": "No such option: --decays"},
        # 26. Test missing decay value
        {"params": ["-d"], "output": "Option '-d' requires 2 arguments."},
        # 27. Test invalid type of first value in decay argument
        {"params": ["--decay", "spam", 3], "output": "Invalid value"},
        # 28. Test invalid type of second value in decay argument
        {"params": ["--decay", "span", "A"], "output": "Invalid value"},
        # 29. Test invalid range for `com` value in decay argument
        {"params": ["--decay", "com", -1], "output": " Invalid value for com"},
        # 30. Test invalid range for `span` value in decay argument
        {"params": ["--decay", "span", 0], "output": " Invalid value for span"},
        # 31. Test invalid range for `halflife` value in decay argument
        {"params": ["--decay", "halflife", 0], "output": "Invalid value for halflife"},
        # 32. Test invalid range for `com` value in decay argument
        {"params": ["--decay", "alpha", 0], "output": " Invalid value for alpha"},
    ]
    # edge of test groups for different commands group or individual commands
    tests_edge = [13, 21, 24, 32]

    # Instantiate the runner first
    runner = CliRunner()

    result = runner.invoke(cli.status, [])
    match = re.search(r"([0-9]+@i).*.perf", result.output)
    assert match
    cprof_idx = match.groups(1)[0]

    # Perform the testing
    moving_average_runner_test(runner, incorrect_tests, tests_edge, 2, cprof_idx)


def test_moving_average_correct(pcs_single_prof):
    """
    Test correct usages of the moving average cli.

    Expecting no exceptions and errors, all tests should end with status code 0.
    """
    correct_tests = [
        # TESTS MOVING AVERAGE COMMAND AND OPTIONS
        # 1. Test the help printout first
        {"params": ["--help"], "output": "Usage"},
        # 2. Test default command
        {"params": []},
        # 3. Test the help printout firsts
        {"params": ["--help"], "output": "Usage"},
        # 4. Test default value of parameters
        {"params": []},
        # 5. Test the value of min_periods parameter
        {"params": ["--min_periods", 1]},
        # 6. Test the value of per_key parameter
        {"params": ["--per-key", "amount"]},
        # 7. Test the value of of_key parameter
        {"params": ["-of", "structure-unit-size"]},
        # TESTS SIMPLE MOVING AVERAGE COMMAND AND SIMPLE MOVING MEDIAN COMMAND
        # 8. Test the value of window_width_parameter
        {"params": ["--window_width", 10]},
        # 9. Test center parameter
        {"params": ["--center"]},
        # 10. Test no-center parameter
        {"params": ["--no-center"]},
        # TESTS SIMPLE MOVING AVERAGE COMMAND
        # 11. Test `boxcar` as value for window-type parameter
        {"params": ["--window_type", "boxcar"]},
        # 12. Test `triang` as value for window-type parameter
        {"params": ["-wt", "triang"]},
        # 13. Test `blackman` as value for window-type parameter
        {"params": ["-wt", "blackman"]},
        # 14. Test `hamming` as value for window-type parameter
        {"params": ["--window_type", "hamming"]},
        # 15. Test `bartlett` as value for window-type parameter
        {"params": ["--window_type", "bartlett"]},
        # 16. Test `parzen` as value for window-type parameter
        {"params": ["-wt", "parzen"]},
        # 17. Test `blackmanharris` as value for window-type parameter
        {"params": ["--window_type", "blackmanharris"]},
        # 18. Test `bohman` as value for window-type parameter
        {"params": ["-wt", "bohman"]},
        # 19. Test `nuttall` as value for window-type parameter
        {"params": ["--window_type", "nuttall"]},
        # 20. Test `barthann` as value for window-type parameter
        {"params": ["-wt", "barthann"]},
        # 21. Test complex combination of parameters no.1
        {"params": ["--window_type", "blackmanharris", "-ww", 10]},
        # 22. Test complex combination of parameters no.2
        {"params": ["--no-center", "--window_type", "triang"]},
        # 23. Test complex combination of parameters no.3
        {"params": ["--window_width", 5, "--center", "-wt", "parzen"]},
        # TESTS EXPONENTIAL MOVING AVERAGE COMMAND
        # 24. Test valid value for `com` value in decay argument
        {"params": ["--decay", "com", 2]},
        # 25. Test valid value for `span` value in decay argument
        {"params": ["--decay", "span", 2]},
        # 26. Test valid value for `halflife` value in decay argument
        {"params": ["--decay", "halflife", 2]},
        # 27. Test valid value for `com` value in decay argument
        {"params": ["--decay", "alpha", 0.5]},
        # COMPLEX TESTS - addition of 'min_periods' argument
        # 28. test complex combination of parameters no.1 - EMA
        {"params": ["--min_periods", 5, "ema", "--decay", "alpha", 0.5]},
        # 29. test complex combination of parameters no.2 - EMA
        {"params": ["-mp", 2, "ema", "--decay", "com", 5]},
        # 30. Test complex combination of parameters no.1 - SMA
        {"params": ["-mp", 1, "sma", "--window_type", "blackmanharris"]},
        # 31. Test complex combination of parameters no.2 - SMA
        {
            "params": [
                "--min_periods",
                1,
                "sma",
                "--no-center",
                "--window_type",
                "triang",
            ]
        },
        # 32. Test complex combination of parameters no.3 - SMA
        {
            "params": [
                "--min_periods",
                3,
                "sma",
                "--window_width",
                5,
                "--center",
                "-wt",
                "parzen",
            ]
        },
        # 33. Test complex combination of parameters no.1 - SMM
        {"params": ["-mp", 2, "smm", "--window_width", 5, "--center"]},
        # 34. Test complex combination of parameters no.1 - SMM
        {"params": ["--min_periods", 3, "smm", "--no-center", "--window_width", 15]},
    ]
    tests_edge = [7, 10, 23, 27, 34]

    # Instantiate the runner first
    runner = CliRunner()

    result = runner.invoke(cli.status, [])
    match = re.search(r"([0-9]+@i).*.perf", result.output)
    assert match
    cprof_idx = match.groups(1)[0]

    # Perform the testing
    moving_average_runner_test(runner, correct_tests, tests_edge, 0, cprof_idx)


def kernel_regression_runner_test(runner, tests_set, tests_edge, exit_code, cprof_idx):
    # Set stable parameters at all tests
    kernel_regression_params = [cprof_idx, "kernel-regression"]
    # Set the supported methods at moving average postprocessor
    kernel_regression_modes = {
        0: [],
        1: ["estimator-settings"],
        2: ["method-selection"],
        3: ["user-selection"],
        4: ["kernel-ridge"],
        5: ["kernel-smoothing"],
    }
    # Executing the testing
    mode_idx = 0
    for idx, test in enumerate(tests_set):
        run_non_param_test(
            runner,
            kernel_regression_params + kernel_regression_modes[mode_idx] + test["params"],
            exit_code,
            test.get("output", "succeeded"),
        )
        mode_idx += 1 if idx + 1 == tests_edge[mode_idx] else 0


def test_kernel_regression_incorrect(pcs_single_prof):
    """
    Test various failure scenarios for kernel regression cli.

    Expecting no exceptions, all tests should end with status code 2.
    """
    incorrect_tests = [
        # TEST COMMON OPTIONS OF KERNEL-REGRESSION CLI AND IT COMMANDS
        # 1. Test non-existing argument
        {"params": ["--ajax"], "output": "No such option: --ajax"},
        # 2. Test non-existing command
        {"params": ["my-selection"], "output": "No such command"},
        # 3. Test non-existing argument
        {"params": ["-c"], "output": "No such option: -c"},
        # 4. Test malformed per-key argument
        {"params": ["--per-keys"], "output": "No such option: --per-keys"},
        # 5. Test missing per-key value
        {"params": ["-per"], "output": "Option '-per' requires an argument."},
        # 6. Test invalid value for per-key argument
        {"params": ["--per-key", "randomize"], "output": "Invalid value"},
        # 7. Test malformed of-key argument
        {"params": ["--off-key"], "output": "No such option: --off-key"},
        # 8. Test missing of-key value
        {"params": ["-of"], "output": "Option '-of' requires an argument."},
        # 9. Test invalid value for per-key argument
        {"params": ["-of", "invalid"], "output": "Invalid value"},
        # 10. Test malformed estimator-settings command
        {"params": ["estimator-setting"], "output": "No such command"},
        # 11. Test malformed user-selection command
        {"params": ["user_selection"], "output": "No such command"},
        # 12. Test malformed method-selection command
        {"params": ["method-selections"], "output": "No such command"},
        # 13. Test malformed kernel-smoothing command
        {"params": ["krnel-smoothing"], "output": "No such command"},
        # 14. Test malformed kernel-ridge command
        {"params": ["kernel-rigde"], "output": "No such command"},
        # TEST OPTIONS OF ESTIMATOR-SETTINGS MODES IN KERNEL-REGRESSION CLI
        # 15. Test malformed reg-type argument
        {"params": ["--reg-types"], "output": "No such option: --reg-types"},
        # 16. Test missing reg-type value
        {"params": ["-rt"], "output": "Option '-rt' requires an argument."},
        # 17. Test invalid value for reg-type argument
        {"params": ["--reg-type", "lp"], "output": "Invalid value"},
        # 18. Test malformed bandwidth-method argument
        {
            "params": ["--bandwidht-method"],
            "output": "No such option: --bandwidht-method",
        },
        # 19. Test missing bandwidth-value value
        {"params": ["-bw"], "output": "Option '-bw' requires an argument."},
        # 20. Test invalid value for bandwidth-value argument
        {"params": ["-bw", "cv-ls"], "output": "Invalid value"},
        # 21. Test malformed n-sub argument
        {"params": ["--n-sub-sample"], "output": "No such option: --n-sub-sample"},
        # 22. Test missing n-sub argument
        {"params": ["-nsub"], "output": "Option '-nsub' requires an argument."},
        # 23. Test invalid value for n-sub argument
        {"params": ["-nsub", 0], "output": "Invalid value"},
        # 24. Test malformed n-res argument
        {"params": ["--n-re-sample"], "output": "No such option: --n-re-sample"},
        # 25. Test missing n-sub argument
        {"params": ["-nres"], "output": "Option '-nres' requires an argument."},
        # 26. Test invalid value for n-sub argument
        {"params": ["--n-re-samples", 0], "output": "Invalid value"},
        # 27. Test malformed efficient argument
        {"params": ["--eficient"], "output": "No such option: --eficient"},
        # 28. Test malformed no-uniformly argument
        {"params": ["--uniformlys"], "output": "No such option: --uniformlys"},
        # 29. Test value for efficient argument
        {
            "params": ["--efficient", "True"],
            "output": "Got unexpected extra argument (True)",
        },
        # 30. Test value for uniformly argument
        {
            "params": ["--uniformly", "False"],
            "output": "Got unexpected extra argument (False)",
        },
        # 31. Test malformed randomize argument
        {"params": ["--randomized"], "output": "No such option: --randomized"},
        # 32. Test malformed no-randomize argument
        {"params": ["--no-randomized"], "output": "No such option: --no-randomized"},
        # 33. Test value for randomize argument
        {
            "params": ["--randomize", "False"],
            "output": "Got unexpected extra argument (False)",
        },
        # 34. Test value for no-randomize argument
        {
            "params": ["--no-randomize", "True"],
            "output": "Got unexpected extra argument (True)",
        },
        # 35. Test malformed return-median argument
        {"params": ["--returns-median"], "output": "No such option: --returns-median"},
        # 36. Test malformed return-mean argument
        {"params": ["--returns-mean"], "output": "No such option: --returns-mean"},
        # 37. Test value for return-median argument
        {
            "params": ["--return-median", "True"],
            "output": "Got unexpected extra argument (True)",
        },
        # 38. Test value for return-mean argument
        {
            "params": ["--return-mean", "False"],
            "output": "Got unexpected extra argument (False)",
        },
        # TEST OPTIONS OF METHOD-SELECTION MODES IN KERNEL-REGRESSION CLI
        # 39. Test malformed reg-type argument
        {"params": ["--reg-types"], "output": "No such option: --reg-types"},
        # 40. Test missing reg-type value
        {"params": ["-rt"], "output": "Option '-rt' requires an argument."},
        # 41. Test invalid value for reg-type argument
        {"params": ["--reg-type", "lb"], "output": "Invalid value"},
        # 42. Test malformed bandwidth-method argument
        {
            "params": ["--bandwidth-methods"],
            "output": "No such option: --bandwidth-methods",
        },
        # 43. Test missing bandwidth-method value
        {"params": ["-bm"], "output": "Option '-bm' requires an argument."},
        # 44. Test invalid value for bandwidth-method argument
        {"params": ["-bm", "goldman"], "output": "Invalid value"},
        # TEST OPTIONS OF USER-SELECTION MODES IN KERNEL-REGRESSION CLI
        # 45. Test malformed reg-type argument
        {"params": ["--reg-types"], "output": "No such option: --reg-types"},
        # 46. Test missing reg-type value
        {"params": ["-rt"], "output": "Option '-rt' requires an argument."},
        # 47. Test invalid value for reg-type argument
        {"params": ["--reg-type", "pp"], "output": "Invalid value"},
        # 48. Test malformed bandwidth-value argument
        {
            "params": ["--bandwidth-values"],
            "output": "No such option: --bandwidth-values",
        },
        # 49. Test missing bandwidth-value value
        {"params": ["-bv"], "output": "Option '-bv' requires an argument."},
        # 50. Test invalid value for bandwidth-value argument
        {"params": ["--bandwidth-value", -2], "output": "Invalid value"},
        # TEST OPTIONS OF KERNEL-RIDGE MODES IN KERNEL-REGRESSION CLI
        # 51. Test malformed gamma-range argument
        {"params": ["--gama-range"], "output": "No such option: --gama-range"},
        # 52. Test missing gamma-range value
        {"params": ["-gr"], "output": "Option '-gr' requires 2 arguments."},
        # 53. Test wrong count of value gamma-range argument
        {
            "params": ["--gamma-range", 2],
            "output": "Option '--gamma-range' requires 2 arguments.",
        },
        # 54. Test wrong type of values gamma-range argument
        {"params": ["-gr", "A", "A"], "output": "Invalid value"},
        # 55. Test invalid values gamma-range argument
        {
            "params": ["-gr", 2, 2],
            "output": "Invalid values: 1.value must be < then the 2.value",
        },
        # 56. Test malformed gamma-step argument
        {"params": ["--gamma-steps"], "output": "No such option: --gamma-steps"},
        # 57. Test missing gamma-step value
        {"params": ["-gs"], "output": "Option '-gs' requires an argument."},
        # 58. Test invalid value gamma-step argument no.1
        {"params": ["--gamma-step", 0], "output": "Invalid value"},
        # 59. Test invalid value gamma-step argument no.2
        {
            "params": ["--gamma-step", 10],
            "output": "Invalid values: step must be < then the length of the range",
        },
        # TEST OPTIONS OF KERNEL-SMOOTHING MODES IN KERNEL-REGRESSION CLI
        # 60. Test malformed kernel-type argument
        {"params": ["--kernel-typse"], "output": "No such option: --kernel-typse"},
        # 61. Test missing kernel-type value
        {"params": ["-kt"], "output": "Option '-kt' requires an argument."},
        # 62. Test invalid value of kernel-type argument
        {"params": ["--kernel-type", "epanechnikov5"], "output": "Invalid value"},
        # 63. Test malformed smoothing-method argument
        {
            "params": ["--smothing-method"],
            "output": "No such option: --smothing-method",
        },
        # 64. Test missing smoothing-method value
        {"params": ["-sm"], "output": "Option '-sm' requires an argument."},
        # 65. Test invalid value of smoothing method argument
        {"params": ["-sm", "local-constant"], "output": "Invalid value"},
        # 66. Test malformed bandwidth-value argument
        {"params": ["--bandwith-value"], "output": "No such option: --bandwith-value"},
        # 67. Test missing bandwidth-value value
        {"params": ["-bv"], "output": "Option '-bv' requires an argument."},
        # 68. Test invalid value for bandwidth-value argument
        {"params": ["-bv", -100], "output": "Invalid value"},
        # 69. Test malformed bandwidth-method argument
        {
            "params": ["--bandwidht-method"],
            "output": "No such option: --bandwidht-method",
        },
        # 70. Test missing bandwidth-method value
        {"params": ["-bm"], "output": "Option '-bm' requires an argument."},
        # 71. Test invalid value for bandwidth-method argument
        {"params": ["--bandwidth-method", "sccot"], "output": "Invalid value"},
        # 72. Test malformed polynomial-order argument
        {
            "params": ["--polynomila-order"],
            "output": "No such option: --polynomila-order",
        },
        # 73. Test missing value for polynomial-order argument
        {"params": ["-q"], "output": "Option '-q' requires an argument."},
        # 74. Test invalid value for polynomial-order argument
        {"params": ["-q", 0], "output": "Invalid value"},
    ]
    tests_edge = [14, 38, 44, 50, 59, 74]

    # Instantiate the runner first
    runner = CliRunner()

    result = runner.invoke(cli.status, [])
    match = re.search(r"([0-9]+@i).*.perf", result.output)
    assert match
    cprof_idx = match.groups(1)[0]

    # Perform the testing
    kernel_regression_runner_test(runner, incorrect_tests, tests_edge, 2, cprof_idx)


def test_kernel_regression_correct(pcs_with_root):
    """
    Test correct usages of the kernel regression cli.

    Expecting no exceptions and errors, all tests should end with status code 0.
    """
    warnings.filterwarnings("ignore")

    correct_tests = [
        # TEST KERNEL-REGRESSION COMMON OPTIONS
        # 1. Test the help printout first
        {"params": ["--help"], "output": "Usage"},
        # 2. Test default command
        {"params": []},
        # 3. Test the value of per_key parameter
        {"params": ["-per", "amount"]},
        # 4. Test the value of of_key parameter
        {"params": ["--of-key", "structure-unit-size"]},
        # 5. Test the whole set of options (per-key, of-key)
        {"params": ["-of", "structure-unit-size", "--per-key", "amount"]},
        # TEST ESTIMATOR SETTINGS OPTIONS
        # 6. Test the help printout first
        {"params": ["--help"], "output": "Usage"},
        # 7. Test the default values of whole set of options
        {"params": []},
        # 8. Test the `ll` as value for reg-type parameter
        {"params": ["--reg-type", "ll"]},
        # 9. Test the `lc` as value for reg-type parameter
        {"params": ["-rt", "lc"]},
        # 10. Test the `cv_ls as value for bandwidth-method argument
        {"params": ["-bw", "cv_ls"]},
        # 11. Test the `aic` as value for bandwidth-method argument
        {"params": ["--bandwidth-method", "aic"]},
        # 12. Test the valid value for n-sub argument
        {"params": ["--n-sub-samples", 20]},
        # 13. Test the valid value for n-res argument
        {"params": ["--n-re-samples", 10]},
        # 14. Test the efficient argument - ON
        {"params": ["--efficient"]},
        # 15. Test the uniformly argument - OFF
        {"params": ["--uniformly"]},
        # 16. Test the randomize argument - ON
        {"params": ["--randomize"]},
        # 17. Test the no-randomize argument - OFF
        {"params": ["--no-randomize"]},
        # 18. Test the return-mean argument
        {"params": ["--return-mean"]},
        # 19. Test the return-median argument
        {"params": ["--return-median"]},
        # 20. Test the complex combinations of options - no.1
        {
            "params": [
                "-rt",
                "lc",
                "--return-median",
                "--randomize",
                "--n-re-samples",
                5,
            ]
        },
        # 21. Test the complex combinations of options - no.2
        {
            "params": [
                "-bw",
                "aic",
                "-nres",
                10,
                "-nsub",
                50,
                "--randomize",
                "--efficient",
            ]
        },
        # 22. Test the complex combinations of options - no.3
        {
            "params": [
                "--reg-type",
                "ll",
                "--bandwidth-method",
                "cv_ls",
                "--efficient",
                "--randomize",
                "--n-sub-samples",
                20,
            ]
        },
        # TEST METHOD-SELECTION OPTIONS
        # 23. Test the help printout first
        {"params": ["--help"], "output": "Usage"},
        # 24. Test the default values of whole set of options
        {"params": []},
        # 25. Test `ll` as value for reg-type argument
        {"params": ["-rt", "ll"]},
        # 26. Test `lc` a value for reg-type argument
        {"params": ["--reg-type", "lc"]},
        # 27. Test `scott` method as value for bandwidth-method argument
        {"params": ["--bandwidth-method", "scott"]},
        # 28. Test `silverman` method as value for bandwidth-method argument
        {"params": ["-bm", "silverman"]},
        # 29. Test complex combination of options - no.1
        {"params": ["--reg-type", "ll", "--bandwidth-method", "scott"]},
        # 30. Test complex combination of options - no.2
        {"params": ["-rt", "lc", "-bm", "silverman"]},
        # TEST USER-SELECTION OPTIONS
        # 31. Test the help printout first
        {"params": ["--help"], "output": "Usage"},
        # 32. Test valid value for bandwidth-value argument
        {"params": ["--bandwidth-value", 0.7582]},
        # 33. Test complex combination of options - no.1
        {"params": ["--reg-type", "lc", "-bv", 2]},
        # 34. Test complex combination of option - no.2
        {"params": ["--bandwidth-value", 3e-2, "-rt", "ll"]},
        # TEST KERNEL-RIDGE OPTIONS
        # 35. Test the help printout first
        {"params": ["--help"], "output": "Usage"},
        # 36. Test the default values of whole set of options
        {"params": []},
        # 37. Test valid range values for gamma-range argument
        {"params": ["--gamma-range", 1e-5, 1e-4]},
        # 38. Test valid value for gamma-step argument
        {"params": ["--gamma-step", 5e-6]},
        # 39. Test complex combination of options - no.1
        {"params": ["--gamma-range", 1e-4, 1e-2, "--gamma-step", 1e-5]},
        # 40. Test complex combination of options - no.2
        {"params": ["-gs", 1e-2, "--gamma-range", 1e-4, 1e-1]},
        # TEST KERNEL-SMOOTHING OPTIONS
        # 41. Test the help printout first
        {"params": ["--help"], "output": "Usage"},
        # 42. Test the default values of whole set of options
        {"params": []},
        # 43. Test `normal` kernel for kernel-type argument
        {"params": ["--kernel-type", "normal"]},
        # 44. Test `normal4` kernel for kernel-type argument
        {"params": ["--kernel-type", "normal4"]},
        # 45. Test `tricube` kernel for kernel-type argument
        {"params": ["-kt", "tricube"]},
        # 46. Test `epanechnikov` kernel for kernel-type argument
        {"params": ["-kt", "epanechnikov"]},
        # 47. Test `epanechnikov4` kernel for kernel-type argument
        {"params": ["--kernel-type", "epanechnikov"]},
        # 48. Test `local-polynomial` method for smoothing-method argument
        {"params": ["--smoothing-method", "local-polynomial"]},
        # 49. Test `local-linear` method for smoothing-method argument
        {"params": ["--smoothing-method", "local-linear"]},
        # 50. Test `spatial-average` method for smoothing-method argument
        {"params": ["-sm", "spatial-average"]},
        # 51. Test `scott` method as value for bandwidth-method argument
        {"params": ["-bm", "scott"]},
        # 52. Test `silverman` method as value for bandwidth-method argument
        {"params": ["--bandwidth-method", "silverman"]},
        # 53. Test valid value for bandwidth-value argument
        {"params": ["-bv", 0.7582]},
        # 54. Test valid value for polynomial-order argument
        {"params": ["--smoothing-method", "local-polynomial", "--polynomial-order", 5]},
        # 55. Test complex combination of options - no.1
        {
            "params": [
                "--kernel-type",
                "epanechnikov",
                "--smoothing-method",
                "local-linear",
                "-bm",
                "silverman",
            ]
        },
        # 56. Test complex combination of options - no.2
        {
            "params": [
                "-kt",
                "normal",
                "-sm",
                "local-polynomial",
                "--polynomial-order",
                8,
                "-bv",
                1,
            ]
        },
        # 57. Test complex combination of options - no.3
        {
            "params": [
                "--kernel-type",
                "normal",
                "-sm",
                "local-linear",
                "--bandwidth-value",
                0.5,
            ]
        },
        # 58. Test complex combination of options - no.5
        {
            "params": [
                "--kernel-type",
                "normal",
                "-sm",
                "local-polynomial",
                "--bandwidth-value",
                1e-10,
            ]
        },
        # 59. Test complex combination of options - no.4
        {
            "params": [
                "--smoothing-method",
                "spatial-average",
                "--bandwidth-method",
                "scott",
                "--kernel-type",
                "tricube",
            ]
        },
    ]
    tests_edge = [5, 22, 30, 34, 40, 59]

    # Instantiate the runner first
    runner = CliRunner()
    pool_path = os.path.join(os.path.split(__file__)[0], "profiles", "postprocess_profiles")
    profile = os.path.join(pool_path, "kernel_datapoints.perf")

    # Perform the testing
    kernel_regression_runner_test(runner, correct_tests, tests_edge, 0, profile)


def test_reg_analysis_incorrect(pcs_single_prof):
    """Test various failure scenarios for regression analysis cli.

    Expecting no exceptions, all tests should end with status code 2.
    """
    # TODO: Cycle and dictionary reduction?

    # Instantiate the runner fist
    runner = CliRunner()

    # Test the lack of arguments passes with defaults
    result = runner.invoke(cli.postprocessby, ["0@i", "regression-analysis"])
    asserts.predicate_from_cli(result, result.exit_code == 0)

    # Test non-existing argument
    result = runner.invoke(cli.postprocessby, ["0@i", "regression-analysis", "-f"])
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, "No such option: -f" in result.output)

    # Test malformed method argument
    result = runner.invoke(cli.postprocessby, ["0@i", "regression-analysis", "--metod", "full"])
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, "No such option: --metod" in result.output)

    # Test missing method value
    result = runner.invoke(cli.postprocessby, ["0@i", "regression-analysis", "-m"])
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, "Option '-m' requires an argument." in result.output)

    # Test invalid method name
    result = runner.invoke(cli.postprocessby, ["0@i", "regression-analysis", "--method", "extra"])
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, "Invalid value" in result.output)

    # Test malformed model argument
    result = runner.invoke(
        cli.postprocessby,
        ["0@i", "regression-analysis", "--method", "full", "--regresion_models"],
    )
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, "No such option: --regresion_models" in result.output)

    # Test missing model value
    result = runner.invoke(
        cli.postprocessby, ["0@i", "regression-analysis", "--method", "full", "-r"]
    )
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, "Option '-r' requires an argument." in result.output)

    # Test invalid model name
    result = runner.invoke(
        cli.postprocessby,
        ["0@i", "regression-analysis", "-m", "full", "-r", "ultimastic"],
    )
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, "Invalid value" in result.output)

    # Test multiple models specification with one invalid value
    result = runner.invoke(
        cli.postprocessby,
        ["0@i", "regression-analysis", "-m", "full", "-r", "linear", "-r", "fail"],
    )
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, "Invalid value" in result.output)

    # Test malformed steps argument
    result = runner.invoke(
        cli.postprocessby,
        ["0@i", "regression-analysis", "-m", "full", "-r", "all", "--seps"],
    )
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, " No such option: --seps" in result.output)

    # Test missing steps value
    result = runner.invoke(
        cli.postprocessby,
        ["0@i", "regression-analysis", "-m", "full", "-r", "all", "-s"],
    )
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, "Option '-s' requires an argument." in result.output)

    # Test invalid steps type
    result = runner.invoke(
        cli.postprocessby,
        ["0@i", "regression-analysis", "-m", "full", "-r", "all", "-s", "0.5"],
    )
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, "'0.5' is not a valid integer range." in result.output)

    # Test multiple method specification resulting in extra argument
    result = runner.invoke(
        cli.postprocessby,
        ["0@i", "regression-analysis", "-dp", "snapshots", "-m", "full", "iterative"],
    )
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, "Got unexpected extra argument (iterative)" in result.output)


def test_reg_analysis_correct(pcs_single_prof):
    """Test correct usages of the regression analysis cli.

    Expecting no exceptions and errors, all tests should end with status code 0.
    """
    # TODO: Cycle and dictionary reduction?

    # Instantiate the runner first
    runner = CliRunner()

    result = runner.invoke(cli.status, [])
    match = re.search(r"([0-9]+@i).*.perf", result.output)
    assert match
    cprof_idx = match.groups(1)[0]

    # Test the help printout first
    result = runner.invoke(cli.postprocessby, [cprof_idx, "regression-analysis", "--help"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(result, "Usage" in result.output)

    # Test multiple method specifications -> the last one is chosen
    result = runner.invoke(
        cli.postprocessby,
        [cprof_idx, "regression-analysis", "-m", "full", "-m", "iterative"],
    )
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(result, "succeeded" in result.output)

    # Test the full computation method with all models set as a default value
    result = runner.invoke(cli.postprocessby, [cprof_idx, "regression-analysis", "-m", "full"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(result, "succeeded" in result.output)

    # Test the iterative method with all models
    result = runner.invoke(cli.postprocessby, [cprof_idx, "regression-analysis", "-m", "iterative"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(result, "succeeded" in result.output)

    # Test the interval method with all models
    result = runner.invoke(cli.postprocessby, [cprof_idx, "regression-analysis", "-m", "interval"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(result, "succeeded" in result.output)

    # Test the initial guess method with all models
    result = runner.invoke(
        cli.postprocessby, [cprof_idx, "regression-analysis", "-m", "initial_guess"]
    )
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(result, "succeeded" in result.output)

    # Test the bisection method with all models
    result = runner.invoke(cli.postprocessby, [cprof_idx, "regression-analysis", "-m", "bisection"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(result, "succeeded" in result.output)

    # Test the bisection method with more complex model
    pool_path = os.path.join(os.path.split(__file__)[0], "profiles", "degradation_profiles")
    complex_file = os.path.join(pool_path, "log2.perf")
    result = runner.invoke(
        cli.postprocessby, [f"{complex_file}", "regression-analysis", "-m", "bisection"]
    )
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(result, "succeeded" in result.output)

    # Test explicit models specification on full computation
    result = runner.invoke(
        cli.postprocessby, [cprof_idx, "regression-analysis", "-m", "full", "-r", "all"]
    )
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(result, "succeeded" in result.output)

    # Test explicit models specification for multiple models
    result = runner.invoke(
        cli.postprocessby,
        [
            cprof_idx,
            "regression-analysis",
            "-m",
            "full",
            "-r",
            "linear",
            "-r",
            "logarithmic",
            "-r",
            "exponential",
        ],
    )
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(result, "succeeded" in result.output)

    # Test explicit models specification for all models
    result = runner.invoke(
        cli.postprocessby,
        [
            cprof_idx,
            "regression-analysis",
            "-m",
            "full",
            "-r",
            "linear",
            "-r",
            "logarithmic",
            "-r",
            "power",
            "-r",
            "exponential",
        ],
    )
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(result, "succeeded" in result.output)

    # Test explicit models specification for all models values (also with 'all' value)
    result = runner.invoke(
        cli.postprocessby,
        [
            cprof_idx,
            "regression-analysis",
            "-m",
            "full",
            "-r",
            "linear",
            "-r",
            "logarithmic",
            "-r",
            "power",
            "-r",
            "exponential",
            "-r",
            "all",
        ],
    )
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(result, "succeeded" in result.output)

    # Test steps specification for full computation which has no effect
    result = runner.invoke(
        cli.postprocessby,
        [cprof_idx, "regression-analysis", "-m", "full", "-r", "all", "-s", "100"],
    )
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(result, "succeeded" in result.output)

    # Test reasonable steps value for iterative method
    result = runner.invoke(
        cli.postprocessby,
        [cprof_idx, "regression-analysis", "-m", "iterative", "-r", "all", "-s", "4"],
    )
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(result, result.output.count("Too few point") == 5)
    asserts.predicate_from_cli(result, "succeeded" in result.output)

    # Test too many steps output
    result = runner.invoke(
        cli.postprocessby,
        [
            cprof_idx,
            "regression-analysis",
            "-m",
            "iterative",
            "-r",
            "all",
            "-s",
            "1000",
        ],
    )
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(result, result.output.count("Too few point") == 7)
    asserts.predicate_from_cli(result, "succeeded" in result.output)

    # Test steps value clamping with iterative method
    result = runner.invoke(
        cli.postprocessby,
        [cprof_idx, "regression-analysis", "-m", "iterative", "-r", "all", "-s", "-1"],
    )
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(result, "succeeded" in result.output)

    # Test different arguments positions
    result = runner.invoke(
        cli.postprocessby,
        [cprof_idx, "regression-analysis", "-s", "2", "-r", "all", "-m", "full"],
    )
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(result, "succeeded" in result.output)


def test_status_correct(pcs_single_prof):
    """Test running perun status in perun directory, without any problems.

    Expecting no exceptions, zero status.
    """
    # Try running status without anything
    runner = CliRunner()
    result = runner.invoke(cli.status, [])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(result, "On major version" in result.output)

    short_result = runner.invoke(cli.status, ["--short"])
    asserts.predicate_from_cli(short_result, short_result.exit_code == 0)
    asserts.predicate_from_cli(short_result, len(short_result.output.split("\n")) == 6)
    assert config.lookup_key_recursively("format.sort_profiles_by") == "time"

    # Try that the sort order changed
    short_result = runner.invoke(
        cli.status, ["--short", "--sort-by", "source", "--sort-order", "desc"]
    )
    asserts.predicate_from_cli(short_result, short_result.exit_code == 0)
    assert pcs_single_prof.local_config().get("format.sort_profiles_by") == "source"
    assert pcs_single_prof.local_config().get("format.sort_profiles_order") == "desc"

    # The sort order is kept the same
    short_result = runner.invoke(cli.status, ["--short"])
    asserts.predicate_from_cli(short_result, short_result.exit_code == 0)
    assert pcs_single_prof.local_config().get("format.sort_profiles_by") == "source"


@pytest.mark.usefixtures("cleandir")
def test_init_correct():
    """Test running init from cli, without any problems

    Expecting no exceptions, no errors, zero status.
    """
    runner = CliRunner()
    dst = str(os.getcwd())
    result = runner.invoke(cli.init, [dst, "--vcs-type=git"])
    asserts.predicate_from_cli(result, result.exit_code == 0)


@pytest.mark.usefixtures("cleandir")
def test_init_correct_with_edit(monkeypatch):
    """Test running init from cli, without any problems

    Expecting no exceptions, no errors, zero status.
    """
    runner = CliRunner()
    dst = str(os.getcwd())

    def donothing(*_):
        pass

    monkeypatch.setattr("perun.utils.external.commands.run_external_command", donothing)
    result = runner.invoke(cli.init, [dst, "--vcs-type=git", "--configure"])
    asserts.predicate_from_cli(result, result.exit_code == 0)


@pytest.mark.usefixtures("cleandir")
def test_init_correct_with_incorrect_edit(monkeypatch):
    """Test running init from cli, without any problems

    Expecting no exceptions, no errors, zero status.
    """
    runner = CliRunner()
    dst = str(os.getcwd())

    def raiseexc(*_):
        raise exceptions.ExternalEditorErrorException("", "")

    monkeypatch.setattr("perun.utils.external.commands.run_external_command", raiseexc)
    result = runner.invoke(cli.init, [dst, "--vcs-type=git", "--configure"])
    asserts.predicate_from_cli(result, result.exit_code == 1)
    monkeypatch.undo()

    for stuff in os.listdir(dst):
        shutil.rmtree(stuff)

    def raiseexc(*_):
        raise PermissionError("")

    monkeypatch.setattr("perun.logic.config.write_config_to", raiseexc)
    result = runner.invoke(cli.init, [dst, "--vcs-type=git"])
    asserts.predicate_from_cli(result, result.exit_code == 1)
    monkeypatch.undo()

    for stuff in os.listdir(dst):
        shutil.rmtree(stuff)

    def raiseexc(*_):
        raise GitCommandError("git", "pit")

    monkeypatch.setattr("git.repo.base.Repo.init", raiseexc)
    result = runner.invoke(cli.init, [dst, "--vcs-type=git"])
    asserts.predicate_from_cli(result, result.exit_code == 1)


@pytest.mark.usefixtures("cleandir")
def test_init_correct_with_params():
    """Test running init from cli with parameters for git, without any problems

    Expecting no exceptions, no errors, zero status.
    """
    runner = CliRunner()
    dst = str(os.getcwd())
    result = runner.invoke(cli.init, [dst, "--vcs-type=git", "--vcs-flag", "bare"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    print(result.output)
    assert "config" in os.listdir(os.getcwd())
    with open(os.path.join(os.getcwd(), "config"), "r") as config_file:
        assert "bare = true" in "".join(config_file.readlines())


@pytest.mark.usefixtures("cleandir")
def test_init_correct_with_params_and_flags():
    """Test running init from cli with parameters and flags for git, without any problems

    Expecting no exceptions, no errors, zero status.
    """
    runner = CliRunner()
    dst = str(os.getcwd())
    result = runner.invoke(
        cli.init,
        [
            dst,
            "--vcs-type=git",
            "--vcs-flag",
            "quiet",
            "--vcs-param",
            "separate-git-dir",
            "sepdir",
        ],
    )
    asserts.predicate_from_cli(result, result.exit_code == 0)
    assert "sepdir" in os.listdir(os.getcwd())
    initialized_dir = os.path.join(os.getcwd(), "sepdir")
    asserts.git_successfully_init_at(initialized_dir, is_bare=True)


def test_add_correct(pcs_with_root):
    """Test running add from cli, without any problems

    Expecting no exceptions, no errors, zero status.
    """
    valid_profile = test_utils.load_profilename("to_add_profiles", "new-prof-2-memory-basic.perf")
    runner = CliRunner()
    added_profile = test_utils.prepare_profile(
        pcs_with_root.get_job_directory(), valid_profile, pcs.vcs().get_minor_head()
    )
    result = runner.invoke(cli.add, ["--keep-profile", f"{added_profile}"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    assert os.path.exists(added_profile)


@pytest.mark.usefixtures("cleandir")
def test_cli_outside_pcs():
    """Test running add from cli, with problems"""
    # Calling add outside of the perun repo
    runner = CliRunner()
    dst_dir = os.getcwd()
    valid_profile = test_utils.load_profilename("to_add_profiles", "new-prof-2-memory-basic.perf")
    added_profile = test_utils.prepare_profile(dst_dir, valid_profile, "")
    result = runner.invoke(cli.add, ["--keep-profile", f"{added_profile}"])
    asserts.predicate_from_cli(result, result.exit_code == 1)

    result = runner.invoke(cli.remove, [f"{added_profile}"])
    asserts.predicate_from_cli(result, result.exit_code == 1)

    result = runner.invoke(cli.log, [])
    asserts.predicate_from_cli(result, result.exit_code == 1)

    result = runner.invoke(cli.status, [])
    asserts.predicate_from_cli(result, result.exit_code == 1)

    result = runner.invoke(config_cli.config, ["--local", "reset"])
    asserts.predicate_from_cli(result, result.exit_code == 1)


def test_rm_correct(pcs_single_prof):
    """Test running rm from cli, without any problems

    Expecting no exceptions, no errors, zero status
    """
    runner = CliRunner()
    valid_profile = test_utils.load_profilename(
        "full_profiles", "prof-2-complexity-2017-03-20-21-40-42.perf"
    )
    deleted_profile = os.path.split(valid_profile)[-1]
    result = runner.invoke(cli.remove, [f"{deleted_profile}"])
    asserts.predicate_from_cli(result, result.exit_code == 0)


def test_log_correct(pcs_single_prof):
    """Test running log from cli, without any problems

    Expecting no exceptions, no errors, zero status
    """
    runner = CliRunner()
    result = runner.invoke(cli.log, [])
    asserts.predicate_from_cli(result, result.exit_code == 0)

    short_result = runner.invoke(cli.log, ["--short"])
    asserts.predicate_from_cli(result, short_result.exit_code == 0)
    asserts.predicate_from_cli(
        result, len(result.output.split("\n")) > len(short_result.output.split("\n"))
    )


def test_collect_correct(pcs_with_root):
    """Test running collector from cli, without any problems

    Expecting no exceptions, no errors, zero status
    """
    runner = CliRunner()
    result = runner.invoke(
        collect_cli.collect,
        ["-c echo", "-w hello", "-o", "prof.perf", "time", "--repeat=1", "--warmup=1"],
    )
    asserts.predicate_from_cli(result, result.exit_code == 0)
    assert "prof.perf" in os.listdir(".")

    if sys.platform != "darwin":
        current_dir = os.path.split(__file__)[0]
        src_dir = os.path.join(current_dir, "sources", "collect_bounds")
        src_file = os.path.join(src_dir, "partitioning.c")
        result = runner.invoke(
            collect_cli.collect, ["-c echo", "-w hello", "bounds", "-d", f"{src_dir}"]
        )
        asserts.predicate_from_cli(result, result.exit_code == 0)

        result = runner.invoke(
            collect_cli.collect, ["-c echo", "-w hello", "bounds", "-s", f"{src_file}"]
        )
        asserts.predicate_from_cli(result, result.exit_code == 0)

    assert len(os.listdir(os.path.join(".perun", "logs"))) == 0
    result = runner.invoke(
        cli.cli,
        [
            "--log",
            "collect",
            "-c echo",
            "-w hello",
            "-o",
            "prof3.perf",
            "time",
            "--repeat=1",
            "--warmup=1",
        ],
    )
    asserts.predicate_from_cli(result, result.exit_code == 0)
    assert "prof3.perf" in os.listdir(".")
    assert len(os.listdir(os.path.join(".perun", "logs"))) >= 1

    assert "log" not in os.listdir(".")
    result = runner.invoke(
        cli.cli,
        [
            "--log",
            "--log-dir",
            "./log",
            "collect",
            "-c echo",
            "-w hello",
            "-o",
            "prof2.perf",
            "time",
            "--repeat=1",
            "--warmup=1",
        ],
    )
    asserts.predicate_from_cli(result, result.exit_code == 0)
    assert "prof2.perf" in os.listdir(".")
    assert "log" in os.listdir(".")


def test_show_help(pcs_with_root):
    """Test running show to see if there are registered modules for showing

    Expecting no error and help outputed, where the currently supported modules will be shown
    """
    runner = CliRunner()
    result = runner.invoke(cli.show, ["--help"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(result, "bars" in result.output)
    asserts.predicate_from_cli(result, "tableof" in result.output)


def test_add_massaged_head(pcs_full_no_prof, valid_profile_pool):
    """Test running add with tags instead of profile

    Expecting no errors and profile added as it should, or errors for incorrect revs
    """
    git_repo = git.Repo(os.path.split(pcs_full_no_prof.get_path())[0])
    head = str(git_repo.head.commit)
    test_utils.populate_repo_with_untracked_profiles(
        pcs_full_no_prof.get_path(), valid_profile_pool
    )
    first_tagged = os.path.relpath(
        test_utils.prepare_profile(
            pcs_full_no_prof.get_job_directory(), valid_profile_pool[0], head
        )
    )

    runner = CliRunner()
    result = runner.invoke(cli.add, ["0@p", "--minor=HEAD"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(
        result, f"{first_tagged} - registered" in common_kit.escape_ansi(result.output)
    )

    runner = CliRunner()
    result = runner.invoke(cli.add, ["0@p", r"--minor=HEAD^{d"])
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, "Missing closing brace" in result.output)

    runner = CliRunner()
    result = runner.invoke(cli.add, ["0@p", r"--minor=HEAD^}"])
    asserts.predicate_from_cli(result, result.exit_code == 2)

    runner = CliRunner()
    result = runner.invoke(cli.add, ["0@p", "--minor=tag2"])
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, "Ref 'tag2' did not resolve to an object" in result.output)


def test_add_tag(monkeypatch, pcs_full_no_prof, valid_profile_pool):
    """Test running add with tags instead of profile

    Expecting no errors and profile added as it should
    """
    git_repo = git.Repo(os.path.split(pcs_full_no_prof.get_path())[0])
    head = str(git_repo.head.commit)
    parent = str(git_repo.head.commit.parents[0])
    test_utils.populate_repo_with_untracked_profiles(
        pcs_full_no_prof.get_path(), valid_profile_pool
    )
    first_sha = os.path.relpath(
        test_utils.prepare_profile(
            pcs_full_no_prof.get_job_directory(), valid_profile_pool[0], head
        )
    )
    second_sha = os.path.relpath(
        test_utils.prepare_profile(
            pcs_full_no_prof.get_job_directory(), valid_profile_pool[1], parent
        )
    )

    runner = CliRunner()
    result = runner.invoke(cli.add, ["0@p"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(
        result, f"{first_sha} - registered" in common_kit.escape_ansi(result.output)
    )

    runner = CliRunner()
    result = runner.invoke(cli.add, ["0@p"])
    asserts.predicate_from_cli(result, result.exit_code == 1)
    asserts.predicate_from_cli(
        result, f"Origin version - {parent}" in common_kit.escape_ansi(result.output)
    )

    # Check that force work as intented
    monkeypatch.setattr("click.confirm", lambda _: True)
    runner = CliRunner()
    result = runner.invoke(cli.add, ["--force", "0@p"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(
        result, f"{second_sha} - registered" in common_kit.escape_ansi(result.output)
    )

    result = runner.invoke(cli.add, ["10@p"])
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, "0@p" in result.output)


def test_add_tag_range(pcs_with_root, valid_profile_pool):
    """Test running add with tags instead of profile

    Expecting no errors and profile added as it should
    """
    git_repo = git.Repo(os.path.split(pcs_with_root.get_path())[0])
    head = str(git_repo.head.commit)
    test_utils.populate_repo_with_untracked_profiles(pcs_with_root.get_path(), valid_profile_pool)
    os.path.relpath(
        test_utils.prepare_profile(pcs_with_root.get_job_directory(), valid_profile_pool[0], head)
    )
    os.path.relpath(
        test_utils.prepare_profile(pcs_with_root.get_job_directory(), valid_profile_pool[1], head)
    )

    runner = CliRunner()
    result = runner.invoke(cli.add, ["10@p-0@p"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(
        result, "Registration succeeded for - 0 profiles" in common_kit.escape_ansi(result.output)
    )

    result = runner.invoke(cli.add, ["0@p-10@p"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(
        result, "Registration succeeded for - 2 profiles" in common_kit.escape_ansi(result.output)
    )

    # Nothing should remain!
    result = runner.invoke(cli.status, [])
    asserts.predicate_from_cli(result, "no untracked" in result.output)


def test_remove_tag(pcs_single_prof):
    """Test running remove with tags instead of profile

    Expecting no errors and profile removed as it should
    """
    runner = CliRunner()
    result = runner.invoke(cli.remove, ["0@i"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(result, "1/1" in result.output)
    asserts.predicate_from_cli(result, "deregistered" in result.output)


def test_remove_tag_range(pcs_full):
    """Test running remove with range of tags instead of profile

    Expecting no errors and profile removed as it should
    """
    runner = CliRunner()
    result = runner.invoke(cli.remove, ["10@i-0@i"])
    asserts.predicate_from_cli(result, result.exit_code == 0)

    result = runner.invoke(cli.remove, ["0@i-10@i"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(result, "2 profiles" in result.output)

    # Nothing should remain!
    result = runner.invoke(cli.status, [])
    asserts.predicate_from_cli(result, "no tracked" in result.output)
    asserts.predicate_from_cli(result, result.exit_code == 0)


def test_remove_pending(pcs_with_root, stored_profile_pool):
    """Test running remove with pending tags and ranges"""
    jobs_dir = pcs_with_root.get_job_directory()
    runner = CliRunner()

    test_utils.populate_repo_with_untracked_profiles(pcs_with_root.get_path(), stored_profile_pool)
    result = runner.invoke(cli.status, [])
    asserts.predicate_from_cli(result, "no untracked" not in result.output)
    asserts.predicate_from_cli(result, result.exit_code == 0)
    assert len(os.listdir(jobs_dir)) == 4
    # 3 profiles and .index

    result = runner.invoke(cli.remove, ["0@p"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    assert len(os.listdir(jobs_dir)) == 3

    result = runner.invoke(cli.remove, ["0@p"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    assert len(os.listdir(jobs_dir)) == 2

    removed_full_profile = [p for p in os.listdir(jobs_dir) if p != ".index"][0]
    removed_full_profile = os.path.join(pcs_with_root.get_job_directory(), removed_full_profile)
    result = runner.invoke(cli.remove, [removed_full_profile])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    assert len(os.listdir(jobs_dir)) == 1
    assert os.listdir(jobs_dir) == [".index"]

    result = runner.invoke(cli.status, [])
    asserts.predicate_from_cli(result, "no untracked" in result.output)
    asserts.predicate_from_cli(result, result.exit_code == 0)

    test_utils.populate_repo_with_untracked_profiles(pcs_with_root.get_path(), stored_profile_pool)
    assert len(os.listdir(jobs_dir)) == 4  # 3 profiles and .index
    result = runner.invoke(cli.remove, ["0@p-10@p"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    assert len(os.listdir(jobs_dir)) == 1


def test_postprocess_tag(pcs_single_prof, valid_profile_pool):
    """Test running postprocessby with various valid and invalid tags

    Expecting no errors (or caught errors), everything postprocessed as it should be
    """
    test_utils.populate_repo_with_untracked_profiles(pcs_single_prof.get_path(), valid_profile_pool)
    pending_dir = os.path.join(pcs_single_prof.get_path(), "jobs")
    assert len(list(filter(test_utils.index_filter, os.listdir(pending_dir)))) == 2

    runner = CliRunner()
    result = runner.invoke(cli.postprocessby, ["0@p", "regression-analysis", "-dp", "time"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    assert len(list(filter(test_utils.index_filter, os.listdir(pending_dir)))) == 3

    # Try incorrect tag -> expect failure and return code 2 (click error)
    result = runner.invoke(cli.postprocessby, ["666@p", "regression-analysis"])
    asserts.predicate_from_cli(result, result.exit_code == 2)
    assert len(list(filter(test_utils.index_filter, os.listdir(pending_dir)))) == 3

    # Try correct index tag
    result = runner.invoke(cli.postprocessby, ["0@i", "regression-analysis"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    assert len(list(filter(test_utils.index_filter, os.listdir(pending_dir)))) == 4

    # Try incorrect index tag -> expect failure and return code 2 (click error)
    result = runner.invoke(cli.postprocessby, ["1337@i", "regression-analysis"])
    asserts.predicate_from_cli(result, result.exit_code == 2)
    assert len(list(filter(test_utils.index_filter, os.listdir(pending_dir)))) == 4

    # Try absolute postprocessing
    first_in_jobs = sorted(list(filter(test_utils.index_filter, os.listdir(pending_dir))))[0]
    absolute_first_in_jobs = os.path.join(pending_dir, first_in_jobs)
    result = runner.invoke(
        cli.postprocessby, [absolute_first_in_jobs, "regression-analysis", "-dp", "time"]
    )
    asserts.predicate_from_cli(result, result.exit_code == 0)

    # Try lookup postprocessing
    result = runner.invoke(cli.postprocessby, [first_in_jobs, "regression-analysis", "-dp", "time"])
    asserts.predicate_from_cli(result, result.exit_code == 0)


def test_show_tag(pcs_single_prof, valid_profile_pool, monkeypatch):
    """Test running show with several valid and invalid tags

    Expecting no errors (or caught errors), everything shown as it should be
    """
    test_utils.populate_repo_with_untracked_profiles(pcs_single_prof.get_path(), valid_profile_pool)
    pending_dir = os.path.join(pcs_single_prof.get_path(), "jobs")

    runner = CliRunner()
    result = runner.invoke(cli.show, ["0@p", "tableof", "resources"])
    asserts.predicate_from_cli(result, result.exit_code == 0)

    # Try incorrect tag -> expect failure and return code 2 (click error)
    result = runner.invoke(cli.show, ["1337@p", "tableof", "resources"])
    asserts.predicate_from_cli(result, result.exit_code == 2)

    # Try correct index tag
    result = runner.invoke(cli.show, ["0@i", "tableof", "resources"])
    asserts.predicate_from_cli(result, result.exit_code == 0)

    # Try incorrect index tag
    result = runner.invoke(cli.show, ["666@i", "tableof", "resources"])
    asserts.predicate_from_cli(result, result.exit_code == 2)

    # Try absolute showing
    first_in_jobs = list(filter(test_utils.index_filter, os.listdir(pending_dir)))[0]
    absolute_first_in_jobs = os.path.join(pending_dir, first_in_jobs)
    result = runner.invoke(cli.show, [absolute_first_in_jobs, "tableof", "resources"])
    asserts.predicate_from_cli(result, result.exit_code == 0)

    # Try lookup showing
    result = runner.invoke(cli.show, [first_in_jobs, "tableof", "resources"])
    asserts.predicate_from_cli(result, result.exit_code == 0)

    # Try iterating through files
    monkeypatch.setattr("click.confirm", lambda *_: True)
    result = runner.invoke(cli.show, ["prof", "tableof", "resources"])
    asserts.predicate_from_cli(result, result.exit_code == 0)

    # Try iterating through files, but none is confirmed to be true
    monkeypatch.setattr("click.confirm", lambda *_: False)
    result = runner.invoke(cli.show, ["prof", "tableof", "resources"])
    asserts.predicate_from_cli(result, result.exit_code == 1)

    # Try getting something from index
    result = runner.invoke(
        cli.show, ["prof-2-complexity-2017-03-20-21-40-42.perf", "tableof", "resources"]
    )
    asserts.predicate_from_cli(result, result.exit_code == 0)


def test_config(pcs_with_root, monkeypatch):
    """Test running config

    Expecting no errors, everything shown as it should be
    """
    runner = CliRunner()

    # OK usage
    result = runner.invoke(config_cli.config, ["--local", "get", "vcs.type"])
    asserts.predicate_from_cli(result, result.exit_code == 0)

    result = runner.invoke(config_cli.config, ["--local", "set", "vcs.remote", "url"])
    asserts.predicate_from_cli(result, result.exit_code == 0)

    # Error cli usage
    result = runner.invoke(config_cli.config, ["--local", "get"])
    asserts.predicate_from_cli(result, result.exit_code == 2)

    result = runner.invoke(config_cli.config, ["--local", "get", "bogus.key"])
    asserts.predicate_from_cli(result, result.exit_code == 1)

    result = runner.invoke(config_cli.config, ["--local", "set", "key"])
    asserts.predicate_from_cli(result, result.exit_code == 2)

    result = runner.invoke(config_cli.config, ["--local", "get", "wrong,key"])
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, "invalid format" in result.output)

    # Try to run the monkey-patched editor
    def donothing(*_):
        pass

    monkeypatch.setattr("perun.utils.external.commands.run_external_command", donothing)
    result = runner.invoke(config_cli.config, ["--local", "edit"])
    asserts.predicate_from_cli(result, result.exit_code == 0)

    result = runner.invoke(config_cli.config, ["--shared", "edit"])
    asserts.predicate_from_cli(result, result.exit_code == 0)

    def raiseexc(*_):
        raise exceptions.ExternalEditorErrorException

    monkeypatch.setattr("perun.utils.external.commands.run_external_command", raiseexc)
    result = runner.invoke(config_cli.config, ["--local", "edit"])
    asserts.predicate_from_cli(result, result.exit_code == 1)


@pytest.mark.usefixtures("cleandir")
def test_reset_outside_pcs(monkeypatch):
    """Tests resetting of configuration outside of the perun scope

    Excepts error when resetting local config, and no error when resetting global config
    """
    runner = CliRunner()
    result = runner.invoke(config_cli.config, ["--local", "reset"])
    asserts.predicate_from_cli(result, result.exit_code == 1)

    monkeypatch.setattr("perun.logic.config.lookup_shared_config_dir", os.getcwd)
    result = runner.invoke(config_cli.config, ["--shared", "reset"])
    asserts.predicate_from_cli(result, result.exit_code == 0)


def test_reset(pcs_with_root):
    """Tests resetting of configuration within the perun scope

    Excepts no error at all
    """
    runner = CliRunner()
    pcs_path = os.getcwd()
    with open(os.path.join(pcs_path, ".perun", "local.yml"), "r") as local_config:
        contents = "".join(local_config.readlines())
        assert "#     - make" in contents
        assert "#   collect_before_check" in contents

    result = runner.invoke(config_cli.config, ["--local", "reset", "developer"])
    asserts.predicate_from_cli(result, result.exit_code == 0)

    with open(os.path.join(pcs_path, ".perun", "local.yml"), "r") as local_config:
        contents = "".join(local_config.readlines())
        assert "make" in contents
        assert "collect_before_check" in contents


def test_check_profiles(pcs_with_degradations):
    """Tests checking degradation between two profiles"""
    pool_path = os.path.join(os.path.split(__file__)[0], "profiles", "degradation_profiles")
    profiles = [
        os.path.join(pool_path, "linear_base.perf"),
        os.path.join(pool_path, "linear_base_degradated.perf"),
        os.path.join(pool_path, "quad_base.perf"),
    ]
    test_utils.populate_repo_with_untracked_profiles(pcs_with_degradations.get_path(), profiles)

    runner = CliRunner()
    for tag in ("0@p", "1@p", "2@p"):
        result = runner.invoke(check_cli.check_group, ["profiles", "0@i", tag])
        asserts.predicate_from_cli(result, result.exit_code == 0)


def test_model_strategies(pcs_with_degradations, monkeypatch):
    """Test checking detection model strategies

    Expecting correct behaviors
    """
    runner = CliRunner()
    # Initialize the matrix
    matrix = config.Config(
        "local",
        "",
        {
            "degradation": {"strategies": [{"method": "local_statistics"}]},
        },
    )
    monkeypatch.setattr("perun.logic.config.local", lambda _: matrix)

    pool_path = os.path.join(os.path.split(__file__)[0], "profiles", "degradation_profiles")
    profiles = [
        os.path.join(pool_path, "baseline_strategies.perf"),
        os.path.join(pool_path, "target_strategies.perf"),
    ]
    test_utils.populate_repo_with_untracked_profiles(pcs_with_degradations.get_path(), profiles)

    for model_strategy in ["best-param", "all-nonparam", "best-both"]:
        result = runner.invoke(
            check_cli.check_group,
            ["--models-type", model_strategy, "profiles", "0@p", "1@p"],
        )
        asserts.predicate_from_cli(result, result.exit_code == 0)


def test_check_head(pcs_with_degradations, monkeypatch):
    """Test checking degradation for one point of history

    Expecting correct behaviours
    """
    runner = CliRunner()

    # Initialize the matrix for the further collecting
    matrix = config.Config(
        "local",
        "",
        {
            "vcs": {"type": "git", "url": "../"},
            "cmds": ["echo"],
            "workloads": ["hello"],
            "collectors": [{"name": "time", "params": {"warmup": 1, "repeat": 1}}],
            "postprocessors": [],
        },
    )
    monkeypatch.setattr("perun.logic.config.local", lambda _: matrix)

    result = runner.invoke(check_cli.check_head, [])
    asserts.predicate_from_cli(result, result.exit_code == 0)

    # Try the precollect and various combinations of options
    result = runner.invoke(check_cli.check_group, ["-c", "head"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    assert config.runtime().get("degradation.collect_before_check")
    config.runtime().data.clear()

    # Try to sink it to black hole
    log_dir = pcs_with_degradations.get_log_directory()
    shutil.rmtree(log_dir)
    common_kit.touch_dir(log_dir)
    config.runtime().data["degradation"] = {
        "collect_before_check": "true",
        "log_collect": "false",
    }
    result = runner.invoke(cli.cli, ["--no-pager", "check", "head"])
    assert len(os.listdir(log_dir)) == 0
    asserts.predicate_from_cli(result, result.exit_code == 0)

    # First lets clear all the objects
    object_dir = pcs_with_degradations.get_object_directory()
    shutil.rmtree(object_dir)
    common_kit.touch_dir(object_dir)
    # Clear the pre_collect_profiles cache
    check.pre_collect_profiles.minor_version_cache.clear()
    assert len(os.listdir(object_dir)) == 0
    # Collect for the head commit
    result = runner.invoke(run_cli.run, ["matrix"])
    asserts.predicate_from_cli(result, result.exit_code == 0)

    config.runtime().set("degradation.log_collect", "true")
    result = runner.invoke(cli.cli, ["--no-pager", "check", "head"])
    assert len(os.listdir(log_dir)) >= 1
    asserts.predicate_from_cli(result, result.exit_code == 0)
    config.runtime().data.clear()


def test_check_all(pcs_with_degradations, monkeypatch):
    """Test checking degradation for whole history

    Expecting correct behaviours
    """
    runner = CliRunner()
    result = runner.invoke(check_cli.check_group, [])
    asserts.predicate_from_cli(result, result.exit_code == 0)

    result = runner.invoke(check_cli.check_all, [])
    asserts.predicate_from_cli(result, result.exit_code == 0)

    runner = CliRunner()
    result = runner.invoke(cli.status)
    asserts.predicate_from_cli(result, result.exit_code == 0)

    def raise_value_error(*args):
        raise ValueError

    monkeypatch.setattr("perun.logic.store.parse_changelog_line", raise_value_error)
    result = runner.invoke(cli.status)
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(result, "Malformed changelog line in " in result.output)


@pytest.mark.usefixtures("cleandir")
def test_utils_create(monkeypatch, tmpdir):
    """Tests creating stuff in the perun"""
    # Prepare different directory
    monkeypatch.setattr(
        "perun.utils.common.script_kit.__file__",
        os.path.join(str(tmpdir), "utils", "script_kit.py"),
    )
    monkeypatch.chdir(str(tmpdir))

    runner = CliRunner()
    result = runner.invoke(utils_cli.create, ["postprocess", "mypostprocessor", "--no-edit"])
    asserts.predicate_from_cli(result, result.exit_code == 1)
    asserts.predicate_from_cli(
        result,
        "cannot use" in result.output and "as target developer directory" in result.output,
    )

    # Now correctly initialize the directory structure
    tmpdir.mkdir("collect")
    tmpdir.mkdir("postprocess")
    tmpdir.mkdir("view")
    tmpdir.mkdir("check")

    # Try to successfully create the new postprocessor
    result = runner.invoke(utils_cli.create, ["postprocess", "mypostprocessor", "--no-edit"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    target_dir = os.path.join(str(tmpdir), "postprocess", "mypostprocessor")
    created_files = os.listdir(target_dir)
    assert "__init__.py" in created_files
    assert "run.py" in created_files

    # Try to successfully create the new collector
    result = runner.invoke(utils_cli.create, ["collect", "mycollector", "--no-edit"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    target_dir = os.path.join(str(tmpdir), "collect", "mycollector")
    created_files = os.listdir(target_dir)
    assert "__init__.py" in created_files
    assert "run.py" in created_files

    # Try to successfully create the new collector
    result = runner.invoke(utils_cli.create, ["view", "myview", "--no-edit"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    target_dir = os.path.join(str(tmpdir), "view", "myview")
    created_files = os.listdir(target_dir)
    assert "__init__.py" in created_files
    assert "run.py" in created_files

    # Try to successfully create the new collector
    result = runner.invoke(utils_cli.create, ["check", "mycheck", "--no-edit"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    target_dir = os.path.join(str(tmpdir), "check")
    created_files = os.listdir(target_dir)
    assert "mycheck.py" in created_files

    # Try to run the monkey-patched editor
    def donothing(*_):
        pass

    monkeypatch.setattr("perun.utils.external.commands.run_external_command", donothing)
    result = runner.invoke(utils_cli.create, ["check", "mydifferentcheck"])
    asserts.predicate_from_cli(result, result.exit_code == 0)

    def raiseexc(*_):
        raise exceptions.ExternalEditorErrorException

    monkeypatch.setattr("perun.utils.external.commands.run_external_command", raiseexc)
    result = runner.invoke(utils_cli.create, ["check", "mythirdcheck"])
    asserts.predicate_from_cli(result, result.exit_code == 1)


def test_run(pcs_with_root, monkeypatch):
    matrix = config.Config(
        "local",
        "",
        {
            "vcs": {"type": "git", "url": "../"},
            "cmds": ["ls -al"],
            "workloads": [".", ".."],
            "collectors": [{"name": "time", "params": {"warmup": 1, "repeat": 1}}],
            "postprocessors": [],
            "execute": {
                "pre_run": [
                    'ls | grep "."',
                ]
            },
        },
    )
    monkeypatch.setattr("perun.logic.config.local", lambda _: matrix)
    runner = CliRunner()
    result = runner.invoke(run_cli.run, ["-c", "matrix"])
    asserts.predicate_from_cli(result, result.exit_code == 0)

    # Test unsupported option
    result = runner.invoke(run_cli.run, ["-f", "matrix"])
    asserts.predicate_from_cli(result, result.exit_code == 1)
    asserts.predicate_from_cli(result, "is unsupported" in result.output)

    job_dir = pcs_with_root.get_job_directory()
    job_profiles = os.listdir(job_dir)
    assert len(job_profiles) >= 2

    config.runtime().set("profiles.register_after_run", "true")
    # Try to store the generated crap not in jobs
    jobs_before = len(os.listdir(job_dir))
    # Need to sleep, since in travis this could rewrite the stuff
    time.sleep(1)
    result = runner.invoke(run_cli.run, ["matrix"])
    jobs_after = len(os.listdir(job_dir))
    asserts.predicate_from_cli(result, result.exit_code == 0)
    assert jobs_before == jobs_after
    config.runtime().set("profiles.register_after_run", "false")

    script_dir = os.path.split(__file__)[0]
    source_dir = os.path.join(script_dir, "sources", "collect_trace")
    job_config_file = os.path.join(source_dir, "job.yml")
    result = runner.invoke(
        run_cli.run,
        [
            "job",
            "--cmd",
            "ls",
            "--args",
            "-al",
            "--workload",
            ".",
            "--collector",
            "time",
            "--collector-params",
            "time",
            "param: key",
            "--collector-params",
            "time",
            f"{job_config_file}",
        ],
    )
    asserts.predicate_from_cli(result, result.exit_code == 0)
    job_profiles = os.listdir(job_dir)
    assert len(job_profiles) >= 3

    # Run the matrix with error in prerun phase
    saved_func = commands.run_safely_external_command

    def run_wrapper(cmd, **kwargs):
        if cmd == 'ls | grep "."':
            return b"hello", b"world"
        else:
            return saved_func(cmd, **kwargs)

    monkeypatch.setattr("perun.utils.external.commands.run_safely_external_command", run_wrapper)
    matrix.data["execute"]["pre_run"].append("ls | grep dafad")
    result = runner.invoke(run_cli.run, ["matrix"])
    asserts.predicate_from_cli(result, result.exit_code == 1)


def test_error_runs(pcs_with_root, monkeypatch):
    """Try various error states induced by job matrix"""
    matrix = config.Config(
        "local",
        "",
        {
            "vcs": {"type": "git", "url": "../"},
            "workloads": [".", ".."],
            "postprocessors": [{"name": "fokume", "params": {}}],
            "execute": {
                "pre_run": [
                    'ls | grep "."',
                ]
            },
        },
    )
    monkeypatch.setattr("perun.logic.config.local", lambda _: matrix)
    runner = CliRunner()
    result = runner.invoke(run_cli.run, ["matrix"])
    asserts.predicate_from_cli(result, result.exit_code == 1)
    asserts.predicate_from_cli(result, "missing 'collectors'" in result.output)

    matrix.data["collectors"] = [{"name": "tome", "params": {}}]

    result = runner.invoke(run_cli.run, ["matrix"])
    asserts.predicate_from_cli(result, result.exit_code == 1)
    asserts.predicate_from_cli(result, "missing 'cmds'" in result.output)
    matrix.data["cmds"] = ["ls"]

    result = runner.invoke(run_cli.run, ["matrix", "-q"])
    asserts.predicate_from_cli(result, result.exit_code == 1)
    asserts.predicate_from_cli(result, "tome collector does not exist" in result.output)
    matrix.data["collectors"][0]["name"] = "time"

    result = runner.invoke(run_cli.run, ["matrix", "-q"])
    asserts.predicate_from_cli(result, result.exit_code == 1)
    asserts.predicate_from_cli(result, "fokume postprocessor does not exist" in result.output)

    # Test that inner run_postprocessor raises some error
    matrix.data["postprocessors"] = [{"name": "regression_analysis", "params": {}}]
    result = runner.invoke(run_cli.run, ["matrix", "-q"])
    asserts.predicate_from_cli(result, result.exit_code == 1)
    asserts.predicate_from_cli(
        result, "while postprocessing by regression_analysis" in result.output
    )
    asserts.predicate_from_cli(result, "Invalid dictionary" in result.output)

    # Test matrix with collect() that fails
    run_report = RunnerReport(None, "collector", {})
    run_report.status = CollectStatus.ERROR
    monkeypatch.setattr("perun.logic.runner.run_all_phases_for", lambda *_, **__: (run_report, {}))
    result = runner.invoke(run_cli.run, ["matrix", "-q"])
    asserts.predicate_from_cli(result, result.exit_code == 1)
    asserts.predicate_from_cli(result, "while collecting by time" in result.output)

    monkeypatch.setattr("perun.logic.runner.run_single_job", lambda *_, **__: CollectStatus.ERROR)
    result = runner.invoke(
        run_cli.run,
        [
            "job",
            "--cmd",
            "ls",
            "--args",
            "-al",
            "--workload",
            ".",
            "--collector",
            "time",
        ],
    )
    asserts.predicate_from_cli(result, result.exit_code == 1)


def test_temp(pcs_with_empty_git):
    """Test the CLI operations on the temporary files"""
    runner = CliRunner()
    files_dir = os.path.join(os.path.split(__file__)[0], "references", "tmp_files")

    # Try to list temporary files with empty tmp/ directory
    result = runner.invoke(utils_cli.temp_list, [pcs.get_tmp_directory()])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(result, "No results for the given parameters in" in result.output)

    # Try to list files in invalid path
    result = runner.invoke(utils_cli.temp_list, ["../"])
    asserts.predicate_from_cli(result, result.exit_code == 1)
    asserts.predicate_from_cli(result, "not located in" in result.output)

    # Add some files to the tmp/
    file_lock = "trace/lock.txt"
    file_records = "trace/data/records.data"
    file_deg = "degradations/results/data.out"
    file_deg2 = "degradations/results/data2.out"
    with open(os.path.join(files_dir, "tst_stap_record.txt"), "r") as records_handle:
        file_records_content = records_handle.read()
    with open(os.path.join(files_dir, "lin1.perf"), "r") as deg_handle:
        file_deg_content = deg_handle.read()
    with open(os.path.join(files_dir, "const1.perf"), "r") as deg_handle:
        file_deg2_content = deg_handle.read()
    temp.create_new_temp(file_lock, "Some important data", protect=True)
    temp.create_new_temp(file_records, file_records_content)
    temp.create_new_temp(file_deg, file_deg_content, protect=True)
    temp.create_new_temp(file_deg2, file_deg2_content)

    # List the now-nonempty tmp/ directory in colored mode
    result = runner.invoke(utils_cli.temp_list, [pcs.get_tmp_directory()])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    _compare_file_outputs(result.output, os.path.join(files_dir, "list1.ref"))

    log.COLOR_OUTPUT = False
    # From now on, the colored mode will be disabled
    # Test the file size and protection-level switches
    result = runner.invoke(
        utils_cli.temp_list,
        [pcs.get_tmp_directory(), "--no-file-size", "--no-protection-level"],
    )
    assert result.exit_code == 0
    _compare_file_outputs(result.output, os.path.join(files_dir, "list2.ref"))

    # Test the sorting by size and protection level (name is default)
    result = runner.invoke(utils_cli.temp_list, [pcs.get_tmp_directory(), "-s", "size"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    _compare_file_outputs(result.output, os.path.join(files_dir, "list3.ref"))
    result = runner.invoke(utils_cli.temp_list, [pcs.get_tmp_directory(), "-s", "protection"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    _compare_file_outputs(result.output, os.path.join(files_dir, "list4.ref"))

    # Test the protection filter
    result = runner.invoke(utils_cli.temp_list, [pcs.get_tmp_directory(), "-fp", "protected"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    _compare_file_outputs(result.output, os.path.join(files_dir, "list5.ref"))
    result = runner.invoke(utils_cli.temp_list, [pcs.get_tmp_directory(), "-fp", "unprotected"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    _compare_file_outputs(result.output, os.path.join(files_dir, "list6.ref"))
    log.COLOR_OUTPUT = True

    # Test the syncing
    # Simulate manual deletion by the user
    assert temp.exists_temp_file(file_lock)
    assert temp.get_temp_properties(file_lock) == (False, True, False)
    os.remove(os.path.join(pcs.get_tmp_directory(), file_lock))
    assert not temp.exists_temp_file(file_lock)
    # However index records are still there, sync
    assert temp.get_temp_properties(file_lock) == (False, True, False)
    result = runner.invoke(utils_cli.temp_sync, [])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    assert temp.get_temp_properties(file_lock) == (False, False, False)

    # Test the deletion
    # Try to delete non-existent directory
    result = runner.invoke(utils_cli.temp_delete, ["some/invalid/dir"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(result, "does not exist, no files deleted" in result.output)

    # Test the warning
    result = runner.invoke(utils_cli.temp_delete, [".", "-w"])
    asserts.predicate_from_cli(result, result.exit_code == 1)
    asserts.predicate_from_cli(result, "Aborted" in result.output)
    assert temp.exists_temp_file(file_deg)

    # Test single file deletion
    result = runner.invoke(utils_cli.temp_delete, [file_deg2])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    assert not temp.exists_temp_file(file_deg2)

    # Test the keep directories
    result = runner.invoke(utils_cli.temp_delete, ["trace/data", "-k"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    assert not temp.exists_temp_file(file_records)
    assert temp.exists_temp_dir("trace/data")

    # Test the force deletion of the whole tmp/ directory with keeping the empty dirs
    result = runner.invoke(utils_cli.temp_delete, [".", "-f", "-k"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    assert not temp.exists_temp_file(file_lock) and not temp.exists_temp_file(file_deg)
    assert temp.exists_temp_dir("degradations") and temp.exists_temp_dir("trace")

    # Partially repopulate the directory
    temp.create_new_temp(file_lock, "Some important data", protect=True)
    temp.create_new_temp(file_deg2, file_deg2_content)

    # Test the complete deletion of the tmp/ directory
    result = runner.invoke(utils_cli.temp_delete, [".", "-f"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    assert not temp.exists_temp_file(file_lock) and not temp.exists_temp_file(file_deg2)
    tmp_content = os.listdir(pcs.get_tmp_directory())
    assert len(tmp_content) == 1 and tmp_content[0] == ".index"


def test_stats(pcs_full_no_prof):
    """Test the CLI for stats module, mainly that all the options are working correctly."""
    runner = CliRunner()

    # Prepare some variables for versions and paths
    minor_head, minor_middle, minor_root = _get_vcs_versions()
    head_dir = os.path.join(minor_head[:2], minor_head[2:])
    middle_dir = os.path.join(minor_middle[:2], minor_middle[2:])
    root_dir = os.path.join(minor_root[:2], minor_root[2:])
    stats_dir = pcs.get_stats_directory()
    files_dir = os.path.join(os.path.split(__file__)[0], "references", "stats_files")

    # Prepare the reference values for minor versions and the valid mapping between them and the
    # actual ones during the test run
    reference_head = "a00e5a82dd8284d6b73335015867e816a1c6cbd4"
    reference_middle = "15de1b9a58807f17cf0a135146f4872752abc859"
    reference_root = "246d9a25926195cfdfb10797436d022d6f6b0a1b"
    version_mapping = [
        (minor_head, reference_head),
        (minor_middle, reference_middle),
        (minor_root, reference_root),
    ]

    # Try to list stats files with empty stats/ directory
    result = runner.invoke(utils_cli.stats_list_files, [])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(result, "No results for the given parameters in" in result.output)
    # Try it with some filtering parameters
    result = runner.invoke(utils_cli.stats_list_files, ["-N", 10, "-m", minor_middle])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(result, "No results for the given parameters in" in result.output)

    # Try to list stats minor versions with empty stats/ directory
    result = runner.invoke(utils_cli.stats_list_versions, [])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(result, "No results for the given parameters in" in result.output)
    # Try it with some filtering parameters
    result = runner.invoke(utils_cli.stats_list_versions, ["-N", 10, "-m", minor_root])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(result, "No results for the given parameters in" in result.output)

    head_custom = os.path.join(head_dir, "custom_file")
    root_custom = os.path.join(root_dir, "custom_file_2")
    head_custom_dir = os.path.join(root_dir, "custom_dir")
    stats_custom_dir = os.path.join("lower_custom", "upper_custom")

    # HEAD: head_stats, custom_file, custom_dir
    # MIDDLE: 'empty'
    # ROOT: created manually, custom_file_2
    # lower_custom/upper_custom
    stats.add_stats("head_stats", ["1"], [{"value": 1, "location": "minor_head"}])
    stats.add_stats("middle_stats", ["1"], [{"custom": 2}], minor_middle)
    stats.delete_stats_file("middle_stats", minor_middle, True)
    os.makedirs(os.path.join(stats_dir, root_dir))
    os.makedirs(os.path.join(stats_dir, stats_custom_dir))
    os.mkdir(os.path.join(stats_dir, head_custom_dir))
    common_kit.touch_file(os.path.join(stats_dir, root_custom))
    with open(os.path.join(stats_dir, root_custom), "w+") as f_handle:
        f_handle.write("Some custom data")
    common_kit.touch_file(os.path.join(stats_dir, head_custom))

    # Test the list functions on populated stats directory and some custom objects
    result = runner.invoke(utils_cli.stats_list_files, [])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    actual_output = _normalize_stats_output(result.output, version_mapping)
    _compare_file_outputs(actual_output, os.path.join(files_dir, "list1.ref"))
    # Test the list of versions
    result = runner.invoke(utils_cli.stats_list_versions, [])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    actual_output = _normalize_stats_output(result.output, version_mapping)
    _compare_file_outputs(actual_output, os.path.join(files_dir, "list2.ref"))

    # Now synchronize the stats directory and test the filtering parameters in list functions
    # Test the list of files
    runner.invoke(utils_cli.stats_sync, [])
    result = runner.invoke(utils_cli.stats_list_files, ["-N", 1, "-m", minor_middle])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    actual_output = _normalize_stats_output(result.output, version_mapping)
    _compare_file_outputs(actual_output, os.path.join(files_dir, "list3.ref"))

    log.COLOR_OUTPUT = False
    result = runner.invoke(utils_cli.stats_list_files, ["-N", 2, "-m", minor_middle])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    actual_output = _normalize_stats_output(result.output, version_mapping)
    _compare_file_outputs(actual_output, os.path.join(files_dir, "list4.ref"))
    # Test the list of versions
    result = runner.invoke(utils_cli.stats_list_versions, ["-N", 2, "-m", minor_middle])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    actual_output = _normalize_stats_output(result.output, version_mapping)
    _compare_file_outputs(actual_output, os.path.join(files_dir, "list5.ref"))

    # Test the sorting by size and omitting some properties
    result = runner.invoke(utils_cli.stats_list_files, ["-s", "-t"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    actual_output = _normalize_stats_output(result.output, version_mapping)
    _compare_file_outputs(actual_output, os.path.join(files_dir, "list6.ref"))
    result = runner.invoke(utils_cli.stats_list_versions, ["-s", "-t"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    actual_output = _normalize_stats_output(result.output, version_mapping)
    _compare_file_outputs(actual_output, os.path.join(files_dir, "list7.ref"))

    # Test the output by omitting more properties
    result = runner.invoke(utils_cli.stats_list_files, ["-i", "-f"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    actual_output = _normalize_stats_output(result.output, version_mapping)
    _compare_file_outputs(actual_output, os.path.join(files_dir, "list8.ref"))
    result = runner.invoke(utils_cli.stats_list_versions, ["-f", "-d"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    actual_output = _normalize_stats_output(result.output, version_mapping)
    _compare_file_outputs(actual_output, os.path.join(files_dir, "list9.ref"))
    log.COLOR_OUTPUT = True

    # Delete the minor_middle directory
    result = runner.invoke(utils_cli.stats_delete_minor, [minor_middle])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    assert not os.path.exists(os.path.join(stats_dir, minor_middle[:2], minor_middle[2:]))

    log.COLOR_OUTPUT = False
    # Now try lists with invalid minor values
    # Attempting to list version that doesn't have directory in stats, should display the successor
    result = runner.invoke(utils_cli.stats_list_files, ["-N", 1, "-m", minor_middle])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    actual_output = _normalize_stats_output(result.output, version_mapping)
    _compare_file_outputs(actual_output, os.path.join(files_dir, "list10.ref"))
    # Attempt to list non-existent minor version
    result = runner.invoke(utils_cli.stats_list_files, ["-N", 1, "-m", "abcdef1234"])
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, "did not resolve to an object" in result.output)
    # Try the same with version list
    result = runner.invoke(utils_cli.stats_list_versions, ["-N", 1, "-m", minor_middle])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    actual_output = _normalize_stats_output(result.output, version_mapping)
    _compare_file_outputs(actual_output, os.path.join(files_dir, "list11.ref"))
    # Attempt to list non-existent minor version
    result = runner.invoke(utils_cli.stats_list_files, ["-N", 1, "-m", "abcdef1234"])
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, "did not resolve to an object" in result.output)
    log.COLOR_OUTPUT = True

    # Recreate the middle version directory, keep it empty however
    stats.add_stats("tmp_stats", ["id_1"], [{"value": 10}], minor_middle)
    result = runner.invoke(utils_cli.stats_delete_file, ["-k", "-m", minor_middle, "tmp_stats"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    assert os.path.exists(os.path.join(stats_dir, middle_dir))
    assert not os.path.exists(os.path.join(stats_dir, middle_dir, "tmp_stats"))

    # Test the cleaning function that should be no-op
    result = runner.invoke(utils_cli.stats_clean, ["-c", "-e"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    assert os.path.exists(os.path.join(stats_dir, stats_custom_dir))

    # Try to clean the directory properly
    result = runner.invoke(utils_cli.stats_clean, [])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    assert not os.path.exists(os.path.join(stats_dir, "lower_custom"))
    assert not os.path.exists(os.path.join(stats_dir, middle_dir))

    # Try to delete file in a version that doesn't have a directory in the stats
    result = runner.invoke(utils_cli.stats_delete_file, ["-m", minor_middle, "some_file"])
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, "does not exist in the stats directory" in result.output)
    # Try to delete some file in non-existing minor version
    result = runner.invoke(utils_cli.stats_delete_file, ["-m", "abcdef12345", "some_file"])
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, "did not resolve to an object" in result.output)
    # Try deleting a file in a valid version that does not contain the file
    result = runner.invoke(utils_cli.stats_delete_file, ["-m", minor_head, "file_not_present"])
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(
        result,
        "does not exist in the stats directory for minor version" in result.output,
    )

    # Add a file to both version directories and try to delete the file across all the versions
    stats.add_stats("generic_stats", ["id_1"], [{"value": 1}])
    stats.add_stats("generic_stats", ["id_1"], [{"value": 2}], minor_root)
    assert os.path.exists(os.path.join(stats_dir, root_dir, "generic_stats"))
    result = runner.invoke(utils_cli.stats_delete_file, ["-k", "-m", ".", "generic_stats"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    assert not os.path.exists(os.path.join(stats_dir, root_dir, "generic_stats"))

    # Repopulate the middle minor version and try to delete the contents of the root version
    stats.add_stats("middle_stats", ["id_1"], [{"value": 10}], minor_middle)
    assert os.path.exists(os.path.join(stats_dir, root_dir, "custom_file_2"))
    result = runner.invoke(utils_cli.stats_delete_minor, ["-k", minor_root])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    assert not os.path.exists(os.path.join(stats_dir, root_dir, "custom_file_2"))
    assert os.path.exists(os.path.join(stats_dir, root_dir))

    # Try to clear the contents of all the version directories
    result = runner.invoke(utils_cli.stats_delete_all, ["-k"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    assert len(stats.list_stat_versions()) == 3
    assert len(stats.list_stats_for_minor(minor_head)) == 0
    assert len(stats.list_stats_for_minor(minor_middle)) == 0
    # Try to completely clear the contents of the stats directory
    result = runner.invoke(utils_cli.stats_delete_all, [])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    assert not os.listdir(stats_dir)

    # Try to add some stats file after the deletion to check that .index will be created correctly
    stats.add_stats("middle_stats", ["id_1"], [{"value": 10}], minor_middle)
    assert len(stats.list_stats_for_minor(minor_middle)) == 1


def _get_vcs_versions():
    """Obtains the VCS minor versions.

    :return: list of minor version checksums sorted as in the VCS.
    """
    return [v.checksum for v in pcs.vcs().walk_minor_versions(pcs.vcs().get_minor_head())]


def _normalize_stats_output(output, version_replacements):
    """Attempts to normalize the output of a cli command so that it can be compared.

    That includes changing the minor version values to the reference ones and setting all the
    size values to 0 since they can differ on different machines or lib versions etc.

    :param output: the command output
    :param version_replacements: list of mapping tuples (actual version, reference version)
    :return: the normalized output
    """
    # Normalize the minor versions to some comparable values
    for minor_actual, minor_reference in version_replacements:
        output = output.replace(minor_actual, minor_reference)
    # Normalize the size values
    size_matches = set(SIZE_REGEX.findall(output))
    for match, _ in size_matches:
        space_difference = len(match) - len("0 B")
        output = output.replace(match, " " * space_difference + "0 B")
    return output


def _compare_file_outputs(runner_result, reference_file):
    """Compares runner output with a file output

    :param runner_result: the output of the CLI runner
    :param reference_file: path to the reference file
    """
    with open(reference_file, "r") as f_handle:
        expected_output = f_handle.readlines()
    runner_result = runner_result.splitlines(keepends=True)
    asserts.predicate_from_cli(runner_result, sorted(runner_result) == sorted(expected_output))


@pytest.mark.usefixtures("cleandir")
def test_safe_cli(monkeypatch, capsys):
    """Test call of the safe cli, which is meant for release mostly."""

    def raise_exception():
        raise Exception("Something happened")

    monkeypatch.setattr("perun.cli.cli", raise_exception)
    monkeypatch.setattr("faulthandler.enable", lambda: None)
    cli.launch_cli()
    out, err = capsys.readouterr()
    assert "unexpected error: Exception: Something happened" in err
    assert "Saved dump" in out

    cli.DEV_MODE = True
    with pytest.raises(Exception):
        cli.launch_cli()
    cli.DEV_MODE = False

    with pytest.raises(Exception):
        cli.launch_cli_in_dev_mode()


@pytest.mark.usefixtures("cleandir")
def test_try_init(monkeypatch):
    monkeypatch.setattr("click.confirm", lambda _: False)
    runner = CliRunner()
    result = runner.invoke(cli.cli, ["status"])
    asserts.predicate_from_cli(result, result.exit_code == 1)
    assert "is not a Perun repository" in result.output

    monkeypatch.setattr("click.confirm", lambda _: True)
    result = runner.invoke(cli.cli, ["status"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    assert "Initializing Perun" in result.output
    assert "Creating empty commit" in result.output


@pytest.mark.usefixtures("cleandir")
def test_try_init_error(monkeypatch):
    monkeypatch.setattr("click.confirm", lambda _: True)

    def mock_raised_exception(*_, **__):
        raise CalledProcessError(-1, "failed")

    monkeypatch.setattr(commands, "run_safely_external_command", mock_raised_exception)
    runner = CliRunner()
    result = runner.invoke(cli.cli, ["status"])
    asserts.predicate_from_cli(result, result.exit_code == 1)
    assert "Initializing Perun" in result.output
    assert "Creating empty commit - failed" in common_kit.escape_ansi(result.output)


@pytest.mark.usefixtures("cleandir")
def test_svs():
    """Test running init from cli, without any problems

    Expecting no exceptions, no errors, zero status.
    """
    runner = CliRunner()
    dst = str(os.getcwd())
    result = runner.invoke(cli.init, [dst])
    asserts.predicate_from_cli(result, result.exit_code == 0)

    if sys.platform == "darwin":
        # Perf is unavailable on macOS
        return

    result = runner.invoke(collect_cli.collect, ["-c echo", "-w hello", "-o", "prof.perf", "kperf"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    assert "prof.perf" in os.listdir(".")

    result = runner.invoke(
        collect_cli.collect, ["-c echo", "-w world", "-o", "prof2.perf", "kperf"]
    )
    asserts.predicate_from_cli(result, result.exit_code == 0)
    assert "prof2.perf" in os.listdir(".")

    result = runner.invoke(
        cli.showdiff,
        [
            "prof.perf",
            "prof2.perf",
            "report",
            "-o",
            "diff",
            "--flamegraph-width",
            1000,
            "--flamegraph-height",
            15,
            "--flamegraph-minwidth",
            0.1,
            "--flamegraph-fontsize",
            14,
            "--flamegraph-bgcolors",
            "blue",
        ],
    )
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(result, "WARNING" not in result.output)
    assert "diff.html" in os.listdir(".")
