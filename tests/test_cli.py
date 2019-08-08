"""Basic tests for running the cli interface of the Perun

Note that the functionality of the commands themselves are not tested,
this is done in appropriate test files, only the API is tested."""

import os
import git
import re
import shutil
import subprocess
import time

import pytest
from click.testing import CliRunner

import perun.cli as cli
import perun.utils as utils
import perun.utils.log as log
import perun.logic.config as config
import perun.logic.store as store
import perun.logic.runner as perun_runner
import perun.utils.exceptions as exceptions
import perun.check.factory as check
import perun.vcs as vcs

__author__ = 'Tomas Fiedor'


def test_cli(pcs_full):
    """Generic tests for cli, such as testing verbosity setting etc."""
    runner = CliRunner()

    log.VERBOSITY = log.VERBOSE_RELEASE
    runner.invoke(cli.cli, ['-v', '-v', 'log'])
    assert log.VERBOSITY == log.VERBOSE_DEBUG

    # Restore the verbosity
    log.VERBOSITY = log.VERBOSE_RELEASE
    log.SUPPRESS_PAGING = True

    result = runner.invoke(cli.cli, ['--version'])
    assert result.output.startswith('Perun')
    assert result.exit_code == 0


def run_non_param_test(runner, test_params, expected_exit_code, expected_output):
    result = runner.invoke(cli.postprocessby, test_params)
    if result.exit_code != expected_exit_code:
        print(result.output)
    assert result.exit_code == expected_exit_code
    assert expected_output in result.output


def test_regressogram_incorrect(pcs_full):
    """
    Test various failure scenarios for regressogram cli.

    Expecting no exceptions, all tests should end with status code 2.
    """
    incorrect_tests = [
        # Test the lack of arguments
        {'params': [], 'output': 'Usage'},
        # Test non-existing argument
        {'params': ['-a'], 'output': 'no such option: -a'},
        # Test malformed bucket_number argument
        {'params': ['--buckets_numbers'],
            'output': 'no such option: --buckets_numbers'},
        # Test missing bucket_number value
        {'params': ['-bn'], 'output': '-bn option requires an argument'},
        # Test invalid bucket_number value
        {'params': ['-bn', 'user'],
            'output': 'Invalid value for "--bucket_number"'},
        # Test malformed bucket_method argument
        {'params': ['--buckets_methods'],
            'output': 'no such option: --buckets_methods'},
        # Test missing bucket_method value
        {'params': ['--bucket_method'],
            'output': '--bucket_method option requires an argument'},
        # Test invalid bucket_method value
        {'params': ['-bm', 'user'],
            'output': 'Invalid value for "--bucket_method"'},
        # Test malformed statistic_function argument
        {'params': ['--statistic_functions'],
            'output': 'no such option: --statistic_functions'},
        # Test missing statistic_function value
        {'params': ['--statistic_function'],
            'output': '--statistic_function option requires an argument'},
        # Test invalid model name
        {'params': ['-sf', 'max'],
            'output': 'Invalid value for "--statistic_function"'}
    ]
    # TODO: multiple values check

    # Instantiate the runner fist
    runner = CliRunner()

    # Set stable parameters at all tests
    regressogram_params = ['1@i', 'regressogram']
    # Executing the testing
    for incorrect_test in incorrect_tests:
        run_non_param_test(runner, regressogram_params +
                           incorrect_test['params'], 2, incorrect_test['output'])


def test_regressogram_correct(pcs_full):
    """
    Test correct usages of the regressogram cli.

    Expecting no exceptions and errors, all tests should end with status code 0.
    """
    # Instantiate the runner first
    runner = CliRunner()

    result = runner.invoke(cli.status, [])
    match = re.search(r'([0-9]+@i).*mixed', result.output)
    assert match
    cprof_idx = match.groups(1)[0]

    correct_tests = [
        # Test the help printout first
        {'params': ['--help'], 'output': 'Usage'},
        # Test default values of parameters (buckets, statistic_function)
        {'params': []},
        # Test first acceptable value for statistic_function parameter (mean)
        {'params': ['--statistic_function', 'mean']},
        # Test second acceptable value for statistic_function parameter (median)
        {'params': ['-sf', 'median']},
        # Test integer variant as value for bucket_number parameter
        {'params': ['--bucket_number', '10']},
        # Test 'auto' method as value for bucket_method parameter
        {'params': ['-bm', 'auto']},
        # Test 'fd' method as value for bucket_method parameter
        {'params': ['-bm', 'fd']},
        # Test 'doane' method as value for bucket_method parameter
        {'params': ['--bucket_method', 'doane']},
        # Test 'scott' method as value for bucket_method parameter
        {'params': ['--bucket_method', 'scott']},
        # Test 'sturges' method as value for bucket_method parameter
        {'params': ['-bm', 'sturges']},
        # Test 'rice' method as value for bucket_method parameter
        {'params': ['-bm', 'rice']},
        # Test 'sqrt' method as value for bucket_method parameter
        {'params': ['--bucket_method', 'sqrt']},
        # Test complex variant for regressogram method
        {'params': ['--bucket_method', 'doane',
                    '--statistic_function', 'mean']},
        # Test bucket_method and bucket_number parameters common
        {'params': ['--bucket_method', 'sqrt', '--bucket_number', 10]},
    ]

    # Set stable parameters at all tests
    regressogram_params = [cprof_idx, 'regressogram']
    # Performing tests
    for _, correct_test in enumerate(correct_tests):
        run_non_param_test(runner, regressogram_params + correct_test['params'], 0,
                           correct_test.get('output', 'Successfully postprocessed'))


def moving_average_runner_test(runner, tests_set, tests_edge, exit_code, cprof_idx):
    # Set stable parameters at all tests
    moving_average_params = [cprof_idx, 'moving-average']
    # Set the supported methods at moving average postprocessor
    moving_average_methods = {0: [], 1: ['smm'], 2: ['sma'], 3: ['ema'], 4: []}
    # Executing the testing
    method_idx = 0
    for idx, test in enumerate(tests_set):
        if method_idx == 1:
            for n in range(method_idx, 3):
                run_non_param_test(runner, moving_average_params + moving_average_methods[n] + test['params'],
                                   exit_code, test.get('output', 'Successfully postprocessed'))
        else:
            run_non_param_test(runner, moving_average_params + moving_average_methods[method_idx] + test['params'],
                               exit_code, test.get('output', 'Successfully postprocessed'))
        method_idx += 1 if idx + 1 == tests_edge[method_idx] else 0


def test_moving_average_incorrect(pcs_full):
    """
    Test various failure scenarios for moving average cli.

    Expecting no exceptions, all tests should end with status code 2.
    """
    incorrect_tests = [
        # TESTS MOVING AVERAGE COMMAND AND OPTIONS
        # 1. Test non-existing argument
        {'params': ['--abcd'], 'output': 'no such option: --abcd'},
        # 2. Test non-existing command
        {'params': ['cma'], 'output': 'No such command "cma"'},
        # 3. Test non-existing argument
        {'params': ['-b'], 'output': 'no such option: -b'},
        # 4. Test malformed min_periods argument
        {'params': ['--min_period'], 'output': 'no such option: --min_period'},
        # 5. Test missing min_period value
        {'params': ['-mp'], 'output': '-mp option requires an argument'},
        # 6. Test invalid range min_periods value
        {'params': ['--min_periods', 0],
            'output': 'Invalid value for "--min_periods"'},
        # 7. Test invalid value type min_periods value
        {'params': ['-mp', 'A'],
            'output': 'Invalid value for "--min_periods"'},
        # 8. Test malformed per_key argument
        {'params': ['--per-keys'], 'output': 'no such option: --per-keys'},
        # 9. Test missing per_key value
        {'params': ['-per'], 'output': '-per option requires an argument'},
        # 10. Test invalid value per_key arguments
        {'params': ['--per-key', 'unknown'],
            'output': 'Invalid value for "--per-key"'},
        # 11. Test malformed of_key argument
        {'params': ['--off'], 'output': 'no such option: --off'},
        # 12. Test missing of_key value
        {'params': ['--of-key'],
            'output': '--of-key option requires an argument'},
        # 13. Test invalid value of_key arguments
        {'params': ['-of', 'unknown'],
            'output': 'Invalid value for "--of-key"'},

        # TESTS SIMPLE MOVING AVERAGE COMMAND AND SIMPLE MOVING MEDIAN COMMAND
        # 14. Test malformed window-width argument
        {'params': ['--window_widh'],
            'output': 'no such option: --window_widh'},
        # 15. Test missing window-width value
        {'params': ['-ww'], 'output': '-ww option requires an argument'},
        # 16. Test invalid range window-width argument
        {'params': ['-ww', -1],
            'output': 'Invalid value for "--window_width"'},
        # 17. Test invalid value type window-width argument
        {'params': ['--window_width', 0.5],
            'output': 'Invalid value for "--window_width"'},
        # 18. Test malformed center argument
        {'params': ['--centers'], 'output': 'no such option: --centers'},
        # 19. Test malformed no-center argument
        {'params': ['--mo-center'], 'output': 'no such option: --mo-center'},
        # 20. Test value for center argument
        {'params': ['--center', 'True'],
            'output': 'Got unexpected extra argument (True)'},
        # 21. Test value for no-center argument
        {'params': ['--no-center', 'False'],
            'output': 'Got unexpected extra argument (False)'},

        # TESTS SIMPLE MOVING AVERAGE COMMAND
        # 22. Test malformed window-type argument
        {'params': ['--windov_type'],
            'output': 'no such option: --windov_type'},
        # 23. Test missing window-type value
        {'params': ['--window_type'],
            'output': '--window_type option requires an argument'},
        # 24. Test invalid range window-type argument
        {'params': ['-wt', "boxcars"],
            'output': 'Invalid value for "--window_type"'},

        # TESTS EXPONENTIAL MOVING AVERAGE COMMAND
        # 25. Test malformed decay argument
        {'params': ['--decays'], 'output': 'no such option: --decays'},
        # 26. Test missing decay value
        {'params': ['-d'], 'output': '-d option requires 2 arguments'},
        # 27. Test invalid type of first value in decay argument
        {'params': ['--decay', 'spam', 3],
            'output': 'Invalid value for "--decay"'},
        # 28. Test invalid type of second value in decay argument
        {'params': ['--decay', 'span', "A"],
            'output': 'Invalid value for "--decay"'},
        # 29. Test invalid range for `com` value in decay argument
        {'params': ['--decay', 'com', -1], 'output': ' Invalid value for com'},
        # 30. Test invalid range for `span` value in decay argument
        {'params': ['--decay', 'span', 0],
            'output': ' Invalid value for span'},
        # 31. Test invalid range for `halflife` value in decay argument
        {'params': ['--decay', 'halflife', 0],
            'output': 'Invalid value for halflife'},
        # 32. Test invalid range for `com` value in decay argument
        {'params': ['--decay', 'alpha', 0],
            'output': ' Invalid value for alpha'},
    ]
    # edge of test groups for different commands group or individual commands
    tests_edge = [13, 21, 24, 32]

    # Instantiate the runner first
    runner = CliRunner()

    result = runner.invoke(cli.status, [])
    match = re.search(r'([0-9]+@i).*mixed', result.output)
    assert match
    cprof_idx = match.groups(1)[0]

    # Perform the testing
    moving_average_runner_test(
        runner, incorrect_tests, tests_edge, 2, cprof_idx)


def test_moving_average_correct(pcs_full):
    """
    Test correct usages of the moving average cli.

    Expecting no exceptions and errors, all tests should end with status code 0.
    """
    correct_tests = [
        # TESTS MOVING AVERAGE COMMAND AND OPTIONS
        # 1. Test the help printout first
        {'params': ['--help'], 'output': 'Usage'},
        # 2. Test default command
        {'params': []},
        # 3. Test the help printout firsts
        {'params': ['--help'], 'output': 'Usage'},
        # 4. Test default value of parameters
        {'params': []},
        # 5. Test the value of min_periods parameter
        {'params': ['--min_periods', 1]},
        # 6. Test the value of per_key parameter
        {'params': ['--per-key', 'amount']},
        # 7. Test the value of of_key parameter
        {'params': ['-of', 'structure-unit-size']},

        # TESTS SIMPLE MOVING AVERAGE COMMAND AND SIMPLE MOVING MEDIAN COMMAND
        # 8. Test the value of window_width_parameter
        {'params': ['--window_width', 10]},
        # 9. Test center parameter
        {'params': ['--center']},
        # 10. Test no-center parameter
        {'params': ['--no-center']},

        # TESTS SIMPLE MOVING AVERAGE COMMAND
        # 11. Test `boxcar` as value for window-type parameter
        {'params': ['--window_type', 'boxcar']},
        # 12. Test `triang` as value for window-type parameter
        {'params': ['-wt', 'triang']},
        # 13. Test `blackman` as value for window-type parameter
        {'params': ['-wt', 'blackman']},
        # 14. Test `hamming` as value for window-type parameter
        {'params': ['--window_type', 'hamming']},
        # 15. Test `bartlett` as value for window-type parameter
        {'params': ['--window_type', 'bartlett']},
        # 16. Test `parzen` as value for window-type parameter
        {'params': ['-wt', 'parzen']},
        # 17. Test `blackmanharris` as value for window-type parameter
        {'params': ['--window_type', 'blackmanharris']},
        # 18. Test `bohman` as value for window-type parameter
        {'params': ['-wt', 'bohman']},
        # 19. Test `nuttall` as value for window-type parameter
        {'params': ['--window_type', 'nuttall']},
        # 20. Test `barthann` as value for window-type parameter
        {'params': ['-wt', 'barthann']},
        # 21. Test complex combination of parameters no.1
        {'params': ['--window_type', 'blackmanharris', '-ww', 10]},
        # 22. Test complex combination of parameters no.2
        {'params': ['--no-center', '--window_type', 'triang']},
        # 23. Test complex combination of parameters no.3
        {'params': ['--window_width', 5, '--center', '-wt', 'parzen']},

        # TESTS EXPONENTIAL MOVING AVERAGE COMMAND
        # 24. Test valid value for `com` value in decay argument
        {'params': ['--decay', 'com', 2]},
        # 25. Test valid value for `span` value in decay argument
        {'params': ['--decay', 'span', 2]},
        # 26. Test valid value for `halflife` value in decay argument
        {'params': ['--decay', 'halflife', 2]},
        # 27. Test valid value for `com` value in decay argument
        {'params': ['--decay', 'alpha', .5]},

        # COMPLEX TESTS - addition of 'min_periods' argument
        # 28. test complex combination of parameters no.1 - EMA
        {'params': ['--min_periods', 5, 'ema', '--decay', 'alpha', .5]},
        # 29. test complex combination of parameters no.2 - EMA
        {'params': ['-mp', 2, 'ema', '--decay', 'com', 5]},
        # 30. Test complex combination of parameters no.1 - SMA
        {'params': ['-mp', 1, 'sma', '--window_type', 'blackmanharris']},
        # 31. Test complex combination of parameters no.2 - SMA
        {'params': ['--min_periods', 1, 'sma',
                    '--no-center', '--window_type', 'triang']},
        # 32. Test complex combination of parameters no.3 - SMA
        {'params': ['--min_periods', 3, 'sma',
                    '--window_width', 5, '--center', '-wt', 'parzen']},
        # 33. Test complex combination of parameters no.1 - SMM
        {'params': ['-mp', 2, 'smm', '--window_width', 5, '--center']},
        # 34. Test complex combination of parameters no.1 - SMM
        {'params': ['--min_periods', 3, 'smm',
                    '--no-center', '--window_width', 15]},
    ]
    tests_edge = [7, 10, 23, 27, 34]

    # Instantiate the runner first
    runner = CliRunner()

    result = runner.invoke(cli.status, [])
    match = re.search(r'([0-9]+@i).*mixed', result.output)
    assert match
    cprof_idx = match.groups(1)[0]

    # Perform the testing
    moving_average_runner_test(runner, correct_tests, tests_edge, 0, cprof_idx)


def kernel_regression_runner_test(runner, tests_set, tests_edge, exit_code, cprof_idx):
    # Set stable parameters at all tests
    kernel_regression_params = [cprof_idx, 'kernel-regression']
    # Set the supported methods at moving average postprocessor
    kernel_regression_modes = {0: [], 1: ['estimator-settings'], 2: ['method-selection'], 3: ['user-selection'],
                               4: ['kernel-ridge'], 5: ['kernel-smoothing']}
    # Executing the testing
    mode_idx = 0
    for idx, test in enumerate(tests_set):
        run_non_param_test(runner, kernel_regression_params + kernel_regression_modes[mode_idx] + test['params'],
                           exit_code, test.get('output', 'Successfully postprocessed'))
        mode_idx += 1 if idx + 1 == tests_edge[mode_idx] else 0


def test_kernel_regression_incorrect(pcs_full):
    """
    Test various failure scenarios for kernel regression cli.

    Expecting no exceptions, all tests should end with status code 2.
    """
    incorrect_tests = [
        # TEST COMMON OPTIONS OF KERNEL-REGRESSION CLI AND IT COMMANDS
        # 1. Test non-existing argument
        {'params': ['--ajax'], 'output': 'no such option: --ajax'},
        # 2. Test non-existing command
        {'params': ['my-selection'],
            'output': 'No such command "my-selection"'},
        # 3. Test non-existing argument
        {'params': ['-c'], 'output': 'no such option: -c'},
        # 4. Test malformed per-key argument
        {'params': ['--per-keys'], 'output': 'no such option: --per-keys'},
        # 5. Test missing per-key value
        {'params': ['-per'], 'output': '-per option requires an argument'},
        # 6. Test invalid value for per-key argument
        {'params': ['--per-key', 'randomize'],
            'output': 'Invalid value for "--per-key"'},
        # 7. Test malformed of-key argument
        {'params': ['--off-key'], 'output': 'no such option: --off-key'},
        # 8. Test missing of-key value
        {'params': ['-of'], 'output': '-of option requires an argument'},
        # 9. Test invalid value for per-key argument
        {'params': ['-of', 'invalid'],
            'output': 'Invalid value for "--of-key"'},
        # 10. Test malformed estimator-settings command
        {'params': ['estimator-setting'],
            'output': 'No such command "estimator-setting"'},
        # 11. Test malformed user-selection command
        {'params': ['user_selection'],
            'output': 'No such command "user_selection"'},
        # 12. Test malformed method-selection command
        {'params': ['method-selections'],
            'output': 'No such command "method-selections"'},
        # 13. Test malformed kernel-smoothing command
        {'params': ['krnel-smoothing'],
            'output': 'No such command "krnel-smoothing"'},
        # 14. Test malformed kernel-ridge command
        {'params': ['kernel-rigde'],
            'output': 'No such command "kernel-rigde"'},

        # TEST OPTIONS OF ESTIMATOR-SETTINGS MODES IN KERNEL-REGRESSION CLI
        # 15. Test malformed reg-type argument
        {'params': ['--reg-types'], 'output': 'no such option: --reg-types'},
        # 16. Test missing reg-type value
        {'params': ['-rt'], 'output': '-rt option requires an argument'},
        # 17. Test invalid value for reg-type argument
        {'params': ['--reg-type', 'lp'],
            'output': 'Invalid value for "--reg-type"'},
        # 18. Test malformed bandwidth-method argument
        {'params': ['--bandwidht-method'],
            'output': 'no such option: --bandwidht-method'},
        # 19. Test missing bandwidth-value value
        {'params': ['-bw'], 'output': '-bw option requires an argument'},
        # 20. Test invalid value for bandwidth-value argument
        {'params': ['-bw', 'cv-ls'],
            'output': 'Invalid value for "--bandwidth-method"'},
        # 21. Test malformed n-sub argument
        {'params': ['--n-sub-sample'],
            'output': 'no such option: --n-sub-sample'},
        # 22. Test missing n-sub argument
        {'params': ['-nsub'], 'output': '-nsub option requires an argument'},
        # 23. Test invalid value for n-sub argument
        {'params': ['-nsub', 0],
            'output': 'Invalid value for "--n-sub-samples"'},
        # 24. Test malformed n-res argument
        {'params': ['--n-re-sample'],
            'output': 'no such option: --n-re-sample'},
        # 25. Test missing n-sub argument
        {'params': ['-nres'], 'output': '-nres option requires an argument'},
        # 26. Test invalid value for n-sub argument
        {'params': ['--n-re-samples', 0],
            'output': 'Invalid value for "--n-re-samples"'},
        # 27. Test malformed efficient argument
        {'params': ['--eficient'], 'output': 'no such option: --eficient'},
        # 28. Test malformed no-uniformly argument
        {'params': ['--uniformlys'], 'output': 'no such option: --uniformlys'},
        # 29. Test value for efficient argument
        {'params': ['--efficient', 'True'],
            'output': 'Got unexpected extra argument (True)'},
        # 30. Test value for uniformly argument
        {'params': ['--uniformly', 'False'],
            'output': 'Got unexpected extra argument (False)'},
        # 31. Test malformed randomize argument
        {'params': ['--randomized'], 'output': 'no such option: --randomized'},
        # 32. Test malformed no-randomize argument
        {'params': ['--no-randomized'],
            'output': 'no such option: --no-randomized'},
        # 33. Test value for randomize argument
        {'params': ['--randomize', 'False'],
            'output': 'Got unexpected extra argument (False)'},
        # 34. Test value for no-randomize argument
        {'params': ['--no-randomize', 'True'],
            'output': 'Got unexpected extra argument (True)'},
        # 35. Test malformed return-median argument
        {'params': ['--returns-median'],
            'output': 'no such option: --returns-median'},
        # 36. Test malformed return-mean argument
        {'params': ['--returns-mean'],
            'output': 'no such option: --returns-mean'},
        # 37. Test value for return-median argument
        {'params': ['--return-median', 'True'],
            'output': 'Got unexpected extra argument (True)'},
        # 38. Test value for return-mean argument
        {'params': ['--return-mean', 'False'],
            'output': 'Got unexpected extra argument (False)'},

        # TEST OPTIONS OF METHOD-SELECTION MODES IN KERNEL-REGRESSION CLI
        # 39. Test malformed reg-type argument
        {'params': ['--reg-types'], 'output': 'no such option: --reg-types'},
        # 40. Test missing reg-type value
        {'params': ['-rt'], 'output': '-rt option requires an argument'},
        # 41. Test invalid value for reg-type argument
        {'params': ['--reg-type', 'lb'],
            'output': 'Invalid value for "--reg-type"'},
        # 42. Test malformed bandwidth-method argument
        {'params': ['--bandwidth-methods'],
            'output': 'no such option: --bandwidth-methods'},
        # 43. Test missing bandwidth-method value
        {'params': ['-bm'], 'output': '-bm option requires an argument'},
        # 44. Test invalid value for bandwidth-method argument
        {'params': ['-bm', 'goldman'],
            'output': 'Invalid value for "--bandwidth-method"'},

        # TEST OPTIONS OF USER-SELECTION MODES IN KERNEL-REGRESSION CLI
        # 45. Test malformed reg-type argument
        {'params': ['--reg-types'], 'output': 'no such option: --reg-types'},
        # 46. Test missing reg-type value
        {'params': ['-rt'], 'output': '-rt option requires an argument'},
        # 47. Test invalid value for reg-type argument
        {'params': ['--reg-type', 'pp'],
            'output': 'Invalid value for "--reg-type"'},
        # 48. Test malformed bandwidth-value argument
        {'params': ['--bandwidth-values'],
            'output': 'no such option: --bandwidth-values'},
        # 49. Test missing bandwidth-value value
        {'params': ['-bv'], 'output': '-bv option requires an argument'},
        # 50. Test invalid value for bandwidth-value argument
        {'params': ['--bandwidth-value', -2],
            'output': 'Invalid value for "--bandwidth-value"'},

        # TEST OPTIONS OF KERNEL-RIDGE MODES IN KERNEL-REGRESSION CLI
        # 51. Test malformed gamma-range argument
        {'params': ['--gama-range'], 'output': 'no such option: --gama-range'},
        # 52. Test missing gamma-range value
        {'params': ['-gr'], 'output': '-gr option requires 2 arguments'},
        # 53. Test wrong count of value gamma-range argument
        {'params': ['--gamma-range', 2],
            'output': '--gamma-range option requires 2 arguments'},
        # 54. Test wrong type of values gamma-range argument
        {'params': ['-gr', 'A', 'A'],
            'output': 'Invalid value for "--gamma-range"'},
        # 55. Test invalid values gamma-range argument
        {'params': ['-gr', 2, 2],
            'output': 'Invalid values: 1.value must be < then the 2.value'},
        # 56. Test malformed gamma-step argument
        {'params': ['--gamma-steps'],
            'output': 'no such option: --gamma-steps'},
        # 57. Test missing gamma-step value
        {'params': ['-gs'], 'output': '-gs option requires an argument'},
        # 58. Test invalid value gamma-step argument no.1
        {'params': ['--gamma-step', 0],
            'output': 'Invalid value for "--gamma-step"'},
        # 59. Test invalid value gamma-step argument no.2
        {'params': ['--gamma-step', 10],
            'output': 'Invalid values: step must be < then the length of the range'},

        # TEST OPTIONS OF KERNEL-SMOOTHING MODES IN KERNEL-REGRESSION CLI
        # 60. Test malformed kernel-type argument
        {'params': ['--kernel-typse'],
            'output': 'no such option: --kernel-typse'},
        # 61. Test missing kernel-type value
        {'params': ['-kt'], 'output': '-kt option requires an argument'},
        # 62. Test invalid value of kernel-type argument
        {'params': ['--kernel-type', 'epanechnikov5'],
            'output': 'Invalid value for "--kernel-type"'},
        # 63. Test malformed smoothing-method argument
        {'params': ['--smothing-method'],
            'output': 'no such option: --smothing-method'},
        # 64. Test missing smoothing-method value
        {'params': ['-sm'], 'output': '-sm option requires an argument'},
        # 65. Test invalid value of smoothing method argument
        {'params': ['-sm', 'local-constant'],
            'output': 'Invalid value for "--smoothing-method"'},
        # 66. Test malformed bandwidth-value argument
        {'params': ['--bandwith-value'],
            'output': 'no such option: --bandwith-value'},
        # 67. Test missing bandwidth-value value
        {'params': ['-bv'], 'output': '-bv option requires an argument'},
        # 68. Test invalid value for bandwidth-value argument
        {'params': ['-bv', -100],
            'output': 'Invalid value for "--bandwidth-value"'},
        # 69. Test malformed bandwidth-method argument
        {'params': ['--bandwidht-method'],
            'output': 'no such option: --bandwidht-method'},
        # 70. Test missing bandwidth-method value
        {'params': ['-bm'], 'output': '-bm option requires an argument'},
        # 71. Test invalid value for bandwidth-method argument
        {'params': ['--bandwidth-method', 'sccot'],
            'output': 'Invalid value for "--bandwidth-method"'},
        # 72. Test malformed polynomial-order argument
        {'params': ['--polynomila-order'],
            'output': 'no such option: --polynomila-order'},
        # 73. Test missing value for polynomial-order argument
        {'params': ['-q'], 'output': '-q option requires an argument'},
        # 74. Test invalid value for polynomial-order argument
        {'params': ['-q', 0],
            'output': 'Invalid value for "--polynomial-order"'},
    ]
    tests_edge = [14, 38, 44, 50, 59, 74]

    # Instantiate the runner first
    runner = CliRunner()

    result = runner.invoke(cli.status, [])
    match = re.search(r'([0-9]+@i).*mixed', result.output)
    assert match
    cprof_idx = match.groups(1)[0]

    # Perform the testing
    kernel_regression_runner_test(
        runner, incorrect_tests, tests_edge, 2, cprof_idx)


def test_kernel_regression_correct(pcs_full):
    """
    Test correct usages of the kernel regression cli.

    Expecting no exceptions and errors, all tests should end with status code 0.
    """
    correct_tests = [
        # TEST KERNEL-REGRESSION COMMON OPTIONS
        # 1. Test the help printout first
        {'params': ['--help'], 'output': 'Usage'},
        # 2. Test default command
        {'params': []},
        # 3. Test the value of per_key parameter
        {'params': ['-per', 'amount']},
        # 4. Test the value of of_key parameter
        {'params': ['--of-key', 'structure-unit-size']},
        # 5. Test the whole set of options (per-key, of-key)
        {'params': ['-of', 'structure-unit-size', '--per-key', 'amount']},

        # TEST ESTIMATOR SETTINGS OPTIONS
        # 6. Test the help printout first
        {'params': ['--help'], 'output': 'Usage'},
        # 7. Test the default values of whole set of options
        {'params': []},
        # 8. Test the `ll` as value for reg-type parameter
        {'params': ['--reg-type', 'll']},
        # 9. Test the `lc` as value for reg-type parameter
        {'params': ['-rt', 'lc']},
        # 10. Test the `cv_ls as value for bandwidth-method argument
        {'params': ['-bw', 'cv_ls']},
        # 11. Test the `aic` as value for bandwidth-method argument
        {'params': ['--bandwidth-method', 'aic']},
        # 12. Test the valid value for n-sub argument
        {'params': ['--n-sub-samples', 20]},
        # 13. Test the valid value for n-res argument
        {'params': ['--n-re-samples', 10]},
        # 14. Test the efficient argument - ON
        {'params': ['--efficient']},
        # 15. Test the uniformly argument - OFF
        {'params': ['--uniformly']},
        # 16. Test the randomize argument - ON
        {'params': ['--randomize']},
        # 17. Test the no-randomize argument - OFF
        {'params': ['--no-randomize']},
        # 18. Test the return-mean argument
        {'params': ['--return-mean']},
        # 19. Test the return-median argument
        {'params': ['--return-median']},
        # 20. Test the complex combinations of options - no.1
        {'params': ['-rt', 'lc', '--return-median',
                    '--randomize', '--n-re-samples', 5]},
        # 21. Test the complex combinations of options - no.2
        {'params': ['-bw', 'aic', '-nres', 10, '-nsub',
                    50, '--randomize', '--efficient']},
        # 22. Test the complex combinations of options - no.3
        {'params': [
            '--reg-type', 'll', '--bandwidth-method', 'cv_ls', '--efficient', '--randomize', '--n-sub-samples', 20
        ]},

        # TEST METHOD-SELECTION OPTIONS
        # 23. Test the help printout first
        {'params': ['--help'], 'output': 'Usage'},
        # 24. Test the default values of whole set of options
        {'params': []},
        # 25. Test `ll` as value for reg-type argument
        {'params': ['-rt', 'll']},
        # 26. Test `lc` a value for reg-type argument
        {'params': ['--reg-type', 'lc']},
        # 27. Test `scott` method as value for bandwidth-method argument
        {'params': ['--bandwidth-method', 'scott']},
        # 28. Test `silverman` method as value for bandwidth-method argument
        {'params': ['-bm', 'silverman']},
        # 29. Test complex combination of options - no.1
        {'params': ['--reg-type', 'll', '--bandwidth-method', 'scott']},
        # 30. Test complex combination of options - no.2
        {'params': ['-rt', 'lc', '-bm', 'silverman']},

        # TEST USER-SELECTION OPTIONS
        # 31. Test the help printout first
        {'params': ['--help'], 'output': 'Usage'},
        # 32. Test valid value for bandwidth-value argument
        {'params': ['--bandwidth-value', .7582]},
        # 33. Test complex combination of options - no.1
        {'params': ['--reg-type', 'lc', '-bv', 2]},
        # 34. Test complex combination of option - no.2
        {'params': ['--bandwidth-value', 3e-2, '-rt', 'll']},

        # TEST KERNEL-RIDGE OPTIONS
        # 35. Test the help printout first
        {'params': ['--help'], 'output': 'Usage'},
        # 36. Test the default values of whole set of options
        {'params': []},
        # 37. Test valid range values for gamma-range argument
        {'params': ['--gamma-range', 1e-5, 1e-1]},
        # 38. Test valid value for gamma-step argument
        {'params': ['--gamma-step', 3e-2]},
        # 39. Test complex combination of options - no.1
        {'params': ['--gamma-range', 1e-4, 1e-2, '--gamma-step', 1e-5]},
        # 40. Test complex combination of options - no.2
        {'params': ['-gs', 1e-2, '--gamma-range', 1e-4, 1e-1]},

        # TEST KERNEL-SMOOTHING OPTIONS
        # 41. Test the help printout first
        {'params': ['--help'], 'output': 'Usage'},
        # 42. Test the default values of whole set of options
        {'params': []},
        # 43. Test `normal` kernel for kernel-type argument
        {'params': ['--kernel-type', 'normal']},
        # 44. Test `normal4` kernel for kernel-type argument
        {'params': ['--kernel-type', 'normal4']},
        # 45. Test `tricube` kernel for kernel-type argument
        {'params': ['-kt', 'tricube']},
        # 46. Test `epanechnikov` kernel for kernel-type argument
        {'params': ['-kt', 'epanechnikov']},
        # 47. Test `epanechnikov4` kernel for kernel-type argument
        {'params': ['--kernel-type', 'epanechnikov']},
        # 48. Test `local-polynomial` method for smoothing-method argument
        {'params': ['--smoothing-method', 'local-polynomial']},
        # 49. Test `local-linear` method for smoothing-method argument
        {'params': ['--smoothing-method', 'local-linear']},
        # 50. Test `spatial-average` method for smoothing-method argument
        {'params': ['-sm', 'spatial-average']},
        # 51. Test `scott` method as value for bandwidth-method argument
        {'params': ['-bm', 'scott']},
        # 52. Test `silverman` method as value for bandwidth-method argument
        {'params': ['--bandwidth-method', 'silverman']},
        # 53. Test valid value for bandwidth-value argument
        {'params': ['-bv', .7582]},
        # 54. Test valid value for polynomial-order argument
        {'params': ['--smoothing-method',
                    'local-polynomial', '--polynomial-order', 5]},
        # 55. Test complex combination of options - no.1
        {'params': ['--kernel-type', 'epanechnikov',
                    '--smoothing-method', 'local-linear', '-bm', 'silverman']},
        # 56. Test complex combination of options - no.2
        {'params': ['-kt', 'normal', '-sm', 'local-polynomial',
                    '--polynomial-order', 8, '-bv', 1]},
        # 57. Test complex combination of options - no.3
        {'params': ['--kernel-type', 'normal', '-sm',
                    'local-linear', '--bandwidth-value', .5]},
        # 58. Test complex combination of options - no.5
        {'params': ['--kernel-type', 'normal', '-sm',
                    'local-polynomial', '--bandwidth-value', 1e-10]},
        # 59. Test complex combination of options - no.4
        {'params': ['--smoothing-method', 'spatial-average',
                    '--bandwidth-method', 'scott', '--kernel-type', 'tricube']}
    ]
    tests_edge = [5, 22, 30, 34, 40, 59]

    # Instantiate the runner first
    runner = CliRunner()

    result = runner.invoke(cli.status, [])
    match = re.search(r'([0-9]+@i).*mixed', result.output)
    assert match
    cprof_idx = match.groups(1)[0]

    # Perform the testing
    kernel_regression_runner_test(
        runner, correct_tests, tests_edge, 0, cprof_idx)


def test_reg_analysis_incorrect(pcs_full):
    """Test various failure scenarios for regression analysis cli.

    Expecting no exceptions, all tests should end with status code 2.
    """
    # TODO: Cycle and dictionary reduction?

    # Instantiate the runner fist
    runner = CliRunner()

    # Test the lack of arguments
    result = runner.invoke(cli.postprocessby, ['1@i', 'regression-analysis'])
    assert result.exit_code == 2
    assert 'Usage' in result.output

    # Test non-existing argument
    result = runner.invoke(cli.postprocessby, [
                           '1@i', 'regression-analysis', '-f'])
    assert result.exit_code == 2
    assert 'no such option: -f' in result.output

    # Test malformed method argument
    result = runner.invoke(cli.postprocessby, [
                           '1@i', 'regression-analysis', '--metod', 'full'])
    assert result.exit_code == 2
    assert 'no such option: --metod' in result.output

    # Test missing method value
    result = runner.invoke(cli.postprocessby, [
                           '1@i', 'regression-analysis', '-m'])
    assert result.exit_code == 2
    assert '-m option requires an argument' in result.output

    # Test invalid method name
    result = runner.invoke(cli.postprocessby, [
                           '1@i', 'regression-analysis', '--method', 'extra'])
    assert result.exit_code == 2
    assert 'Invalid value for "--method"' in result.output

    # Test malformed model argument
    result = runner.invoke(cli.postprocessby, ['1@i', 'regression-analysis', '--method', 'full',
                                               '--regresion_models'])
    assert result.exit_code == 2
    assert 'no such option: --regresion_models' in result.output

    # Test missing model value
    result = runner.invoke(cli.postprocessby, ['1@i', 'regression-analysis', '--method', 'full',
                                               '-r'])
    assert result.exit_code == 2
    assert '-r option requires an argument' in result.output

    # Test invalid model name
    result = runner.invoke(cli.postprocessby, ['1@i', 'regression-analysis', '-m', 'full', '-r',
                                               'ultimastic'])
    assert result.exit_code == 2
    assert 'Invalid value for "--regression_models"' in result.output

    # Test multiple models specification with one invalid value
    result = runner.invoke(cli.postprocessby, ['1@i', 'regression-analysis', '-m', 'full',
                                               '-r', 'linear', '-r', 'fail'])
    assert result.exit_code == 2
    assert 'Invalid value for "--regression_models"' in result.output

    # Test malformed steps argument
    result = runner.invoke(cli.postprocessby, ['1@i', 'regression-analysis', '-m', 'full',
                                               '-r', 'all', '--seps'])
    assert result.exit_code == 2
    assert ' no such option: --seps' in result.output

    # Test missing steps value
    result = runner.invoke(cli.postprocessby, ['1@i', 'regression-analysis', '-m', 'full',
                                               '-r', 'all', '-s'])
    assert result.exit_code == 2
    assert '-s option requires an argument' in result.output

    # Test invalid steps type
    result = runner.invoke(cli.postprocessby, ['1@i', 'regression-analysis', '-m', 'full', '-r',
                                               'all', '-s', '0.5'])
    assert result.exit_code == 2
    assert '0.5 is not a valid integer' in result.output

    # Test multiple method specification resulting in extra argument
    result = runner.invoke(cli.postprocessby, ['1@i', 'regression-analysis', '-dp', 'snapshots',
                                               '-m', 'full', 'iterative'])
    assert result.exit_code == 2
    assert 'Got unexpected extra argument (iterative)' in result.output


def test_reg_analysis_correct(pcs_full):
    """Test correct usages of the regression analysis cli.

    Expecting no exceptions and errors, all tests should end with status code 0.
    """
    # TODO: Cycle and dictionary reduction?

    # Instantiate the runner first
    runner = CliRunner()

    result = runner.invoke(cli.status, [])
    match = re.search(r"([0-9]+@i).*mixed", result.output)
    assert match
    cprof_idx = match.groups(1)[0]

    # Test the help printout first
    result = runner.invoke(cli.postprocessby, [
                           cprof_idx, 'regression-analysis', '--help'])
    assert result.exit_code == 0
    assert 'Usage' in result.output

    # Test multiple method specifications -> the last one is chosen
    result = runner.invoke(cli.postprocessby, [cprof_idx, 'regression-analysis', '-m', 'full',
                                               '-m', 'iterative'])
    assert result.exit_code == 0
    assert 'Successfully postprocessed' in result.output

    # Test the full computation method with all models set as a default value
    result = runner.invoke(cli.postprocessby, [
                           cprof_idx, 'regression-analysis', '-m', 'full'])
    assert result.exit_code == 0
    assert 'Successfully postprocessed' in result.output

    # Test the iterative method with all models
    result = runner.invoke(cli.postprocessby, [
                           cprof_idx, 'regression-analysis', '-m', 'iterative'])
    assert result.exit_code == 0
    assert 'Successfully postprocessed' in result.output

    # Test the interval method with all models
    result = runner.invoke(cli.postprocessby, [
                           cprof_idx, 'regression-analysis', '-m', 'interval'])
    assert result.exit_code == 0
    assert 'Successfully postprocessed' in result.output

    # Test the initial guess method with all models
    result = runner.invoke(cli.postprocessby, [cprof_idx, 'regression-analysis',
                                               '-m', 'initial_guess'])
    assert result.exit_code == 0
    assert 'Successfully postprocessed' in result.output

    # Test the bisection method with all models
    result = runner.invoke(cli.postprocessby, [
                           cprof_idx, 'regression-analysis', '-m', 'bisection'])
    assert result.exit_code == 0
    assert 'Successfully postprocessed' in result.output

    # Test explicit models specification on full computation
    result = runner.invoke(cli.postprocessby, [cprof_idx, 'regression-analysis', '-m', 'full',
                                               '-r', 'all'])
    assert result.exit_code == 0
    assert 'Successfully postprocessed' in result.output

    # Test explicit models specification for multiple models
    result = runner.invoke(cli.postprocessby, [cprof_idx, 'regression-analysis', '-m', 'full',
                                               '-r', 'linear', '-r', 'logarithmic', '-r',
                                               'exponential'])
    assert result.exit_code == 0
    assert 'Successfully postprocessed' in result.output

    # Test explicit models specification for all models
    result = runner.invoke(cli.postprocessby, [cprof_idx, 'regression-analysis', '-m', 'full',
                                               '-r', 'linear', '-r', 'logarithmic', '-r', 'power',
                                               '-r', 'exponential'])
    assert result.exit_code == 0
    assert 'Successfully postprocessed' in result.output

    # Test explicit models specification for all models values (also with 'all' value)
    result = runner.invoke(cli.postprocessby, [cprof_idx, 'regression-analysis', '-m', 'full',
                                               '-r', 'linear', '-r', 'logarithmic', '-r', 'power',
                                               '-r', 'exponential', '-r', 'all'])
    assert result.exit_code == 0
    assert 'Successfully postprocessed' in result.output

    # Test steps specification for full computation which has no effect
    result = runner.invoke(cli.postprocessby, [cprof_idx, 'regression-analysis', '-m', 'full',
                                               '-r', 'all', '-s', '100'])
    assert result.exit_code == 0
    assert 'Successfully postprocessed' in result.output

    # Test reasonable steps value for iterative method
    result = runner.invoke(cli.postprocessby, [cprof_idx, 'regression-analysis', '-m', 'iterative',
                                               '-r', 'all', '-s', '4'])
    assert result.exit_code == 0
    assert result.output.count('Too few points') == 5
    assert 'Successfully postprocessed' in result.output

    # Test too many steps output
    result = runner.invoke(cli.postprocessby, [cprof_idx, 'regression-analysis', '-m', 'iterative',
                                               '-r', 'all', '-s', '1000'])
    assert result.exit_code == 0
    assert result.output.count('Too few points') == 7
    assert 'Successfully postprocessed' in result.output

    # Test steps value clamping with iterative method
    result = runner.invoke(cli.postprocessby, [cprof_idx, 'regression-analysis', '-m', 'iterative',
                                               '-r', 'all', '-s', '-1'])
    assert result.exit_code == 0
    assert 'Successfully postprocessed' in result.output

    # Test different arguments positions
    result = runner.invoke(cli.postprocessby, [cprof_idx, 'regression-analysis', '-s', '2',
                                               '-r', 'all', '-m', 'full'])
    assert result.exit_code == 0
    assert 'Successfully postprocessed' in result.output


def test_status_correct(pcs_full):
    """Test running perun status in perun directory, without any problems.

    Expecting no exceptions, zero status.
    """
    # Try running status without anything
    runner = CliRunner()
    result = runner.invoke(cli.status, [])
    assert result.exit_code == 0
    assert "On major version" in result.output

    short_result = runner.invoke(cli.status, ['--short'])
    assert short_result.exit_code == 0
    assert len(short_result.output.split("\n")) == 6
    assert config.lookup_key_recursively('format.sort_profiles_by') == 'time'

    # Try that the sort order changed
    short_result = runner.invoke(
        cli.status, ['--short', '--sort-by', 'source'])
    assert short_result.exit_code == 0
    assert pcs_full.local_config().get('format.sort_profiles_by') == 'source'

    # The sort order is kept the same
    short_result = runner.invoke(cli.status, ['--short'])
    assert short_result.exit_code == 0
    assert pcs_full.local_config().get('format.sort_profiles_by') == 'source'


@pytest.mark.usefixtures('cleandir')
def test_init_correct():
    """Test running init from cli, without any problems

    Expecting no exceptions, no errors, zero status.
    """
    runner = CliRunner()
    dst = str(os.getcwd())
    result = runner.invoke(cli.init, [dst, '--vcs-type=git'])
    assert result.exit_code == 0


@pytest.mark.usefixtures('cleandir')
def test_init_correct_with_edit(monkeypatch):
    """Test running init from cli, without any problems

    Expecting no exceptions, no errors, zero status.
    """
    runner = CliRunner()
    dst = str(os.getcwd())

    def donothing(*_):
        pass

    monkeypatch.setattr('perun.utils.run_external_command', donothing)
    result = runner.invoke(cli.init, [dst, '--vcs-type=git', '--configure'])
    assert result.exit_code == 0


@pytest.mark.usefixtures('cleandir')
def test_init_correct_with_incorrect_edit(monkeypatch):
    """Test running init from cli, without any problems

    Expecting no exceptions, no errors, zero status.
    """
    runner = CliRunner()
    dst = str(os.getcwd())

    def raiseexc(*_):
        raise exceptions.ExternalEditorErrorException("", "")

    monkeypatch.setattr('perun.utils.run_external_command', raiseexc)
    result = runner.invoke(cli.init, [dst, '--vcs-type=git', '--configure'])
    assert result.exit_code == 1
    monkeypatch.undo()

    for stuff in os.listdir(dst):
        shutil.rmtree(stuff)

    def raiseexc(*_):
        raise PermissionError('')

    monkeypatch.setattr('perun.logic.config.write_config_to', raiseexc)
    result = runner.invoke(cli.init, [dst, '--vcs-type=git'])
    assert result.exit_code == 1
    monkeypatch.undo()

    for stuff in os.listdir(dst):
        shutil.rmtree(stuff)

    def raiseexc(*_):
        raise exceptions.UnsupportedModuleFunctionException('git', 'shit')

    monkeypatch.setattr('perun.vcs.git._init', raiseexc)
    result = runner.invoke(cli.init, [dst, '--vcs-type=git'])
    assert result.exit_code == 1


@pytest.mark.usefixtures('cleandir')
def test_init_correct_with_params():
    """Test running init from cli with parameters for git, without any problems

    Expecting no exceptions, no errors, zero status.
    """
    runner = CliRunner()
    dst = str(os.getcwd())
    result = runner.invoke(
        cli.init, [dst, '--vcs-type=git', '--vcs-flag', 'bare'])
    assert result.exit_code == 0
    assert 'config' in os.listdir(os.getcwd())
    with open(os.path.join(os.getcwd(), 'config'), 'r') as config_file:
        assert "bare = true" in "".join(config_file.readlines())


@pytest.mark.usefixtures('cleandir')
def test_init_correct_with_params_and_flags(helpers):
    """Test running init from cli with parameters and flags for git, without any problems

    Expecting no exceptions, no errors, zero status.
    """
    runner = CliRunner()
    dst = str(os.getcwd())
    result = runner.invoke(cli.init, [dst, '--vcs-type=git', '--vcs-flag', 'quiet',
                                      '--vcs-param', 'separate-git-dir', 'sepdir'])
    assert result.exit_code == 0
    assert 'sepdir' in os.listdir(os.getcwd())
    initialized_dir = os.path.join(os.getcwd(), 'sepdir')
    dir_content = os.listdir(initialized_dir)

    # Should be enough for sanity check
    assert 'HEAD' in dir_content
    assert 'refs' in dir_content
    assert 'branches' in dir_content


def test_add_correct(helpers, pcs_full, valid_profile_pool):
    """Test running add from cli, without any problems

    Expecting no exceptions, no errors, zero status.
    """
    runner = CliRunner()
    added_profile = helpers.prepare_profile(
        pcs_full.get_job_directory(), valid_profile_pool[0],
        vcs.get_minor_head()
    )
    result = runner.invoke(
        cli.add, ['--keep-profile', '{}'.format(added_profile)])
    assert result.exit_code == 0
    assert os.path.exists(added_profile)


@pytest.mark.usefixtures('cleandir')
def test_cli_outside_pcs(helpers, valid_profile_pool):
    """Test running add from cli, with problems"""
    # Calling add outside of the perun repo
    runner = CliRunner()
    dst_dir = os.getcwd()
    added_profile = helpers.prepare_profile(dst_dir, valid_profile_pool[0], "")
    result = runner.invoke(
        cli.add, ['--keep-profile', '{}'.format(added_profile)])
    assert result.exit_code == 1

    result = runner.invoke(cli.remove, ['{}'.format(added_profile)])
    assert result.exit_code == 1

    result = runner.invoke(cli.log, [])
    assert result.exit_code == 1

    result = runner.invoke(cli.status, [])
    assert result.exit_code == 1


def test_rm_correct(helpers, pcs_full, stored_profile_pool):
    """Test running rm from cli, without any problems

    Expecting no exceptions, no errors, zero status
    """
    runner = CliRunner()
    deleted_profile = os.path.split(stored_profile_pool[1])[-1]
    result = runner.invoke(cli.remove, ['{}'.format(deleted_profile)])
    assert result.exit_code == 0


def test_log_correct(pcs_full):
    """Test running log from cli, without any problems

    Expecting no exceptions, no errors, zero status
    """
    runner = CliRunner()
    result = runner.invoke(cli.log, [])
    assert result.exit_code == 0

    short_result = runner.invoke(cli.log, ['--short'])
    assert short_result.exit_code == 0
    assert len(result.output.split('\n')) > len(
        short_result.output.split('\n'))


def test_collect_correct(pcs_full):
    """Test running collector from cli, without any problems

    Expecting no exceptions, no errors, zero status
    """
    runner = CliRunner()
    result = runner.invoke(cli.collect, ['-c echo', '-w hello', 'time'])
    assert result.exit_code == 0


def test_show_help(pcs_full):
    """Test running show to see if there are registered modules for showing

    Expecting no error and help outputed, where the currently supported modules will be shown
    """
    runner = CliRunner()
    result = runner.invoke(cli.show, ['--help'])
    assert result.exit_code == 0
    assert 'heapmap' in result.output
    assert 'raw' in result.output


def test_add_massaged_head(helpers, pcs_full, valid_profile_pool):
    """Test running add with tags instead of profile

    Expecting no errors and profile added as it should, or errors for incorrect revs
    """
    git_repo = git.Repo(os.path.split(pcs_full.get_path())[0])
    head = str(git_repo.head.commit)
    helpers.populate_repo_with_untracked_profiles(
        pcs_full.get_path(), valid_profile_pool)
    first_tagged = os.path.relpath(
        helpers.prepare_profile(
            pcs_full.get_job_directory(), valid_profile_pool[0], head
        )
    )

    runner = CliRunner()
    result = runner.invoke(cli.add, ['0@p', '--minor=HEAD'])
    assert result.exit_code == 0
    assert "'{}' successfully registered".format(first_tagged) in result.output

    runner = CliRunner()
    result = runner.invoke(cli.add, ['0@p', r"--minor=HEAD^{d"])
    assert result.exit_code == 2
    assert "Missing closing brace"

    runner = CliRunner()
    result = runner.invoke(cli.add, ['0@p', r"--minor=HEAD^}"])
    assert result.exit_code == 2

    runner = CliRunner()
    result = runner.invoke(cli.add, ['0@p', '--minor=tag2'])
    assert result.exit_code == 2
    assert "Ref 'tag2' did not resolve to object"


def test_add_tag(monkeypatch, helpers, pcs_full, valid_profile_pool):
    """Test running add with tags instead of profile

    Expecting no errors and profile added as it should
    """
    git_repo = git.Repo(os.path.split(pcs_full.get_path())[0])
    head = str(git_repo.head.commit)
    parent = str(git_repo.head.commit.parents[0])
    helpers.populate_repo_with_untracked_profiles(
        pcs_full.get_path(), valid_profile_pool)
    first_sha = os.path.relpath(helpers.prepare_profile(
        pcs_full.get_job_directory(), valid_profile_pool[0], head)
    )
    second_sha = os.path.relpath(helpers.prepare_profile(
        pcs_full.get_job_directory(), valid_profile_pool[1], parent)
    )

    runner = CliRunner()
    result = runner.invoke(cli.add, ['0@p'])
    assert result.exit_code == 0
    assert "'{}' successfully registered".format(first_sha) in result.output

    runner = CliRunner()
    result = runner.invoke(cli.add, ['0@p'])
    assert result.exit_code == 1
    assert "originates from minor version '{}'".format(parent) in result.output

    # Check that force work as intented
    monkeypatch.setattr('click.confirm', lambda _: True)
    runner = CliRunner()
    result = runner.invoke(cli.add, ['--force', '0@p'])
    assert result.exit_code == 0
    assert "'{}' successfully registered".format(second_sha) in result.output

    result = runner.invoke(cli.add, ['10@p'])
    assert result.exit_code == 2
    assert '0@p' in result.output


def test_add_tag_range(helpers, pcs_full, valid_profile_pool):
    """Test running add with tags instead of profile

    Expecting no errors and profile added as it should
    """
    git_repo = git.Repo(os.path.split(pcs_full.get_path())[0])
    head = str(git_repo.head.commit)
    helpers.populate_repo_with_untracked_profiles(
        pcs_full.get_path(), valid_profile_pool)
    os.path.relpath(helpers.prepare_profile(
        pcs_full.get_job_directory(), valid_profile_pool[0], head)
    )
    os.path.relpath(helpers.prepare_profile(
        pcs_full.get_job_directory(), valid_profile_pool[1], head)
    )

    runner = CliRunner()
    result = runner.invoke(cli.add, ['10@p-0@p'])
    assert result.exit_code == 0
    assert 'successfully registered 0 profiles in index'

    result = runner.invoke(cli.add, ['0@p-10@p'])
    print(result.output)
    assert result.exit_code == 0
    assert 'successfully registered 2 profiles in index'

    # Nothing should remain!
    result = runner.invoke(cli.status, [])
    assert "no untracked" in result.output


def test_remove_tag(pcs_full):
    """Test running remove with tags instead of profile

    Expecting no errors and profile removed as it should
    """
    runner = CliRunner()
    result = runner.invoke(cli.remove, ['0@i'])
    assert result.exit_code == 0
    assert "removed" in result.output


def test_remove_tag_range(helpers, pcs_full):
    """Test running remove with range of tags instead of profile

    Expecting no errors and profile removed as it should
    """
    runner = CliRunner()
    result = runner.invoke(cli.remove, ['10@i-0@i'])
    assert result.exit_code == 0
    assert "removed 0 from index" in result.output

    result = runner.invoke(cli.remove, ['0@i-10@i'])
    assert result.exit_code == 0
    assert "removed 2 from index" in result.output

    # Nothing should remain!
    result = runner.invoke(cli.status, [])
    assert "no tracked" in result.output
    assert result.exit_code == 0


def test_postprocess_tag(helpers, pcs_full, valid_profile_pool):
    """Test running postprocessby with various valid and invalid tags

    Expecting no errors (or caught errors), everything postprocessed as it should be
    """
    helpers.populate_repo_with_untracked_profiles(
        pcs_full.get_path(), valid_profile_pool)
    pending_dir = os.path.join(pcs_full.get_path(), 'jobs')
    assert len(list(filter(helpers.index_filter, os.listdir(pending_dir)))) == 2

    runner = CliRunner()
    result = runner.invoke(cli.postprocessby, ['0@p', 'normalizer'])
    assert result.exit_code == 0
    assert len(list(filter(helpers.index_filter, os.listdir(pending_dir)))) == 3

    # Try incorrect tag -> expect failure and return code 2 (click error)
    result = runner.invoke(cli.postprocessby, ['666@p', 'normalizer'])
    assert result.exit_code == 2
    assert len(list(filter(helpers.index_filter, os.listdir(pending_dir)))) == 3

    # Try correct index tag
    result = runner.invoke(cli.postprocessby, ['1@i', 'normalizer'])
    assert result.exit_code == 0
    assert len(list(filter(helpers.index_filter, os.listdir(pending_dir)))) == 4

    # Try incorrect index tag -> expect failure and return code 2 (click error)
    result = runner.invoke(cli.postprocessby, ['1337@i', 'normalizer'])
    assert result.exit_code == 2
    assert len(list(filter(helpers.index_filter, os.listdir(pending_dir)))) == 4

    # Try absolute postprocessing
    first_in_jobs = list(
        filter(helpers.index_filter, os.listdir(pending_dir)))[0]
    absolute_first_in_jobs = os.path.join(pending_dir, first_in_jobs)
    result = runner.invoke(cli.postprocessby, [
                           absolute_first_in_jobs, 'normalizer'])
    assert result.exit_code == 0

    # Try lookup postprocessing
    result = runner.invoke(cli.postprocessby, [first_in_jobs, 'normalizer'])
    assert result.exit_code == 0


def test_show_tag(helpers, pcs_full, valid_profile_pool, monkeypatch):
    """Test running show with several valid and invalid tags

    Expecting no errors (or caught errors), everythig shown as it should be
    """
    helpers.populate_repo_with_untracked_profiles(
        pcs_full.get_path(), valid_profile_pool)
    pending_dir = os.path.join(pcs_full.get_path(), 'jobs')

    runner = CliRunner()
    result = runner.invoke(cli.show, ['0@p', 'raw'])
    assert result.exit_code == 0

    # Try incorrect tag -> expect failure and return code 2 (click error)
    result = runner.invoke(cli.show, ['1337@p', 'raw'])
    assert result.exit_code == 2

    # Try correct index tag
    result = runner.invoke(cli.show, ['0@i', 'raw'])
    assert result.exit_code == 0

    # Try incorrect index tag
    result = runner.invoke(cli.show, ['666@i', 'raw'])
    assert result.exit_code == 2

    # Try absolute showing
    first_in_jobs = list(
        filter(helpers.index_filter, os.listdir(pending_dir)))[0]
    absolute_first_in_jobs = os.path.join(pending_dir, first_in_jobs)
    result = runner.invoke(cli.show, [absolute_first_in_jobs, 'raw'])
    assert result.exit_code == 0

    # Try lookup showing
    result = runner.invoke(cli.show, [first_in_jobs, 'raw'])
    assert result.exit_code == 0

    # Try iterating through files
    monkeypatch.setattr('click.confirm', lambda *_: True)
    result = runner.invoke(cli.show, ['prof', 'raw'])
    assert result.exit_code == 0

    # Try iterating through files, but none is confirmed to be true
    monkeypatch.setattr('click.confirm', lambda *_: False)
    result = runner.invoke(cli.show, ['prof', 'raw'])
    assert result.exit_code == 1

    # Try getting something from index
    result = runner.invoke(
        cli.show, ['prof-2-2017-03-20-21-40-42.perf', 'raw'])
    assert result.exit_code == 0


def test_config(pcs_full, monkeypatch):
    """Test running config

    Expecting no errors, everything shown as it should be
    """
    runner = CliRunner()

    # OK usage
    result = runner.invoke(cli.config, ['--local', 'get', 'vcs.type'])
    assert result.exit_code == 0

    result = runner.invoke(cli.config, ['--local', 'set', 'vcs.remote', 'url'])
    assert result.exit_code == 0

    # Error cli usage
    result = runner.invoke(cli.config, ['--local', 'get'])
    assert result.exit_code == 2

    result = runner.invoke(cli.config, ['--local', 'get', 'bogus.key'])
    assert result.exit_code == 1

    result = runner.invoke(cli.config, ['--local', 'set', 'key'])
    assert result.exit_code == 2

    result = runner.invoke(cli.config, ['--local', 'get', 'wrong,key'])
    assert result.exit_code == 2
    assert "invalid format" in result.output

    # Try to run the monkey-patched editor
    def donothing(*_):
        pass

    monkeypatch.setattr('perun.utils.run_external_command', donothing)
    result = runner.invoke(cli.config, ['--local', 'edit'])
    assert result.exit_code == 0

    def raiseexc(*_):
        raise exceptions.ExternalEditorErrorException

    monkeypatch.setattr('perun.utils.run_external_command', raiseexc)
    result = runner.invoke(cli.config, ['--local', 'edit'])
    assert result.exit_code == 1


@pytest.mark.usefixtures('cleandir')
def test_reset_outside_pcs(monkeypatch):
    """Tests resetting of configuration outside of the perun scope

    Excepts error when resetting local config, and no error when resetting global config
    """
    runner = CliRunner()
    result = runner.invoke(cli.config, ['--local', 'reset'])
    assert result.exit_code == 1
    assert "could not reset" in result.output

    monkeypatch.setattr(
        'perun.logic.config.lookup_shared_config_dir', lambda: os.getcwd())
    result = runner.invoke(cli.config, ['--shared', 'reset'])
    assert result.exit_code == 0


def test_reset(pcs_full):
    """Tests resetting of configuration within the perun scope

    Excepts no error at all
    """
    runner = CliRunner()
    pcs_path = os.getcwd()
    with open(os.path.join(pcs_path, '.perun', 'local.yml'), 'r') as local_config:
        contents = "".join(local_config.readlines())
        assert '#     - make' in contents
        assert '#   collect_before_check' in contents

    result = runner.invoke(cli.config, ['--local', 'reset', 'developer'])
    assert result.exit_code == 0

    with open(os.path.join(pcs_path, '.perun', 'local.yml'), 'r') as local_config:
        contents = "".join(local_config.readlines())
        assert 'make' in contents
        assert 'collect_before_check' in contents


def test_check_profiles(helpers, pcs_with_degradations):
    """Tests checking degradation between two profiles"""
    pool_path = os.path.join(os.path.split(
        __file__)[0], 'degradation_profiles')
    profiles = [
        os.path.join(pool_path, 'linear_base.perf'),
        os.path.join(pool_path, 'linear_base_degradated.perf'),
        os.path.join(pool_path, 'quad_base.perf')
    ]
    helpers.populate_repo_with_untracked_profiles(
        pcs_with_degradations.get_path(), profiles)

    runner = CliRunner()
    for tag in ("0@p", "1@p", "2@p"):
        result = runner.invoke(cli.check_profiles, ["0@i", tag])
        assert result.exit_code == 0


def test_check_head(pcs_with_degradations, monkeypatch):
    """Test checking degradation for one point of history

    Expecting correct behaviours
    """
    runner = CliRunner()

    # Initialize the matrix for the further collecting
    matrix = config.Config('local', '', {
        'vcs': {'type': 'git', 'url': '../'},
        'cmds': ['ls'],
        'args': ['-al'],
        'workloads': ['.', '..'],
        'collectors': [
            {'name': 'time', 'params': {}}
        ],
        'postprocessors': [],
    })
    monkeypatch.setattr("perun.logic.config.local", lambda _: matrix)

    result = runner.invoke(cli.check_head, [])
    assert result.exit_code == 0

    # Try the precollect and various combinations of options
    result = runner.invoke(cli.check_group, ['-c', 'head'])
    assert result.exit_code == 0
    assert config.runtime().get('degradation.collect_before_check')
    config.runtime().data.clear()

    # Try to sink it to black hole
    log_dir = pcs_with_degradations.get_log_directory()
    shutil.rmtree(log_dir)
    store.touch_dir(log_dir)
    config.runtime().set('degradation', {})
    config.runtime().set('degradation.collect_before_check', 'true')
    config.runtime().set('degradation.log_collect', 'false')
    result = runner.invoke(cli.cli, ['--no-pager', 'check', 'head'])
    assert len(os.listdir(log_dir)) == 0
    assert result.exit_code == 0

    # First lets clear all the objects
    object_dir = pcs_with_degradations.get_object_directory()
    shutil.rmtree(object_dir)
    store.touch_dir(object_dir)
    # Clear the pre_collect_profiles cache
    check.pre_collect_profiles.minor_version_cache.clear()
    assert len(os.listdir(object_dir)) == 0
    # Collect for the head commit
    result = runner.invoke(cli.run, ['matrix'])
    assert result.exit_code == 0

    config.runtime().set('degradation.log_collect', 'true')
    result = runner.invoke(cli.cli, ['--no-pager', 'check', 'head'])
    assert len(os.listdir(log_dir)) >= 1
    assert result.exit_code == 0
    config.runtime().data.clear()


def test_check_all(pcs_with_degradations):
    """Test checking degradation for whole history

    Expecting correct behaviours
    """
    runner = CliRunner()
    result = runner.invoke(cli.check_group, [])
    assert result.exit_code == 0

    result = runner.invoke(cli.check_all, [])
    assert result.exit_code == 0


@pytest.mark.usefixtures('cleandir')
def test_utils_create(monkeypatch, tmpdir):
    """Tests creating stuff in the perun"""
    # Prepare different directory
    monkeypatch.setattr('perun.utils.script_helpers.__file__', os.path.join(
        str(tmpdir), "utils", "script_helpers.py"))
    monkeypatch.chdir(str(tmpdir))

    runner = CliRunner()
    result = runner.invoke(
        cli.create, ['postprocess', 'mypostprocessor', '--no-edit'])
    assert result.exit_code == 1
    assert "cannot use" in result.output and "as target developer directory" in result.output

    # Now correctly initialize the directory structure
    tmpdir.mkdir('collect')
    tmpdir.mkdir('postprocess')
    tmpdir.mkdir('view')
    tmpdir.mkdir('check')

    # Try to successfully create the new postprocessor
    result = runner.invoke(
        cli.create, ['postprocess', 'mypostprocessor', '--no-edit'])
    assert result.exit_code == 0
    target_dir = os.path.join(str(tmpdir), 'postprocess', 'mypostprocessor')
    created_files = os.listdir(target_dir)
    assert '__init__.py' in created_files
    assert 'run.py' in created_files

    # Try to successfully create the new collector
    result = runner.invoke(cli.create, ['collect', 'mycollector', '--no-edit'])
    assert result.exit_code == 0
    target_dir = os.path.join(str(tmpdir), 'collect', 'mycollector')
    created_files = os.listdir(target_dir)
    assert '__init__.py' in created_files
    assert 'run.py' in created_files

    # Try to successfully create the new collector
    result = runner.invoke(cli.create, ['view', 'myview', '--no-edit'])
    assert result.exit_code == 0
    target_dir = os.path.join(str(tmpdir), 'view', 'myview')
    created_files = os.listdir(target_dir)
    assert '__init__.py' in created_files
    assert 'run.py' in created_files

    # Try to successfully create the new collector
    result = runner.invoke(cli.create, ['check', 'mycheck', '--no-edit'])
    assert result.exit_code == 0
    target_dir = os.path.join(str(tmpdir), 'check')
    created_files = os.listdir(target_dir)
    assert 'mycheck.py' in created_files

    # Try to run the monkey-patched editor
    def donothing(*_):
        pass

    monkeypatch.setattr('perun.utils.run_external_command', donothing)
    result = runner.invoke(cli.create, ['check', 'mydifferentcheck'])
    assert result.exit_code == 0

    def raiseexc(*_):
        raise exceptions.ExternalEditorErrorException

    monkeypatch.setattr('perun.utils.run_external_command', raiseexc)
    result = runner.invoke(cli.create, ['check', 'mythirdcheck'])
    assert result.exit_code == 1


def test_run(pcs_full, monkeypatch):
    matrix = config.Config('local', '', {
        'vcs': {'type': 'git', 'url': '../'},
        'cmds': ['ls'],
        'args': ['-al'],
        'workloads': ['.', '..'],
        'collectors': [
            {'name': 'time', 'params': {}}
        ],
        'postprocessors': [],
        'execute': {
            'pre_run': [
                'ls | grep "."',
            ]
        }
    })
    monkeypatch.setattr("perun.logic.config.local", lambda _: matrix)
    runner = CliRunner()
    result = runner.invoke(cli.run, ['-c', 'matrix'])
    assert result.exit_code == 0

    # Test unsupported option
    result = runner.invoke(cli.run, ['-f', 'matrix'])
    assert result.exit_code == 1
    assert "is unsupported" in result.output

    job_dir = pcs_full.get_job_directory()
    job_profiles = os.listdir(job_dir)
    assert len(job_profiles) >= 2

    config.runtime().set('profiles.register_after_run', 'true')
    # Try to store the generated crap not in jobs
    jobs_before = len(os.listdir(job_dir))
    # Need to sleep, since in travis this could rewrite the stuff
    time.sleep(1)
    result = runner.invoke(cli.run, ['matrix'])
    jobs_after = len(os.listdir(job_dir))
    assert result.exit_code == 0
    assert jobs_before == jobs_after
    config.runtime().set('profiles.register_after_run', 'false')

    script_dir = os.path.split(__file__)[0]
    source_dir = os.path.join(script_dir, 'collect_trace')
    job_config_file = os.path.join(source_dir, 'job.yml')
    result = runner.invoke(cli.run, [
        'job',
        '--cmd', 'ls',
        '--args', '-al',
        '--workload', '.',
        '--collector', 'time',
        '--collector-params', 'time', 'param: key',
        '--collector-params', 'time', '{}'.format(job_config_file)
    ])
    assert result.exit_code == 0
    job_profiles = os.listdir(job_dir)
    assert len(job_profiles) >= 3

    # Run the matrix with error in prerun phase
    saved_func = utils.run_safely_external_command

    def run_wrapper(cmd):
        if cmd == 'ls | grep "."':
            return b"hello", b"world"
        else:
            return saved_func(cmd)

    monkeypatch.setattr('perun.utils.run_safely_external_command', run_wrapper)
    matrix.data['execute']['pre_run'].append('ls | grep dafad')
    result = runner.invoke(cli.run, ['matrix'])
    assert result.exit_code == 1


def test_fuzzing_correct(pcs_full):
    """Runs basic tests for fuzzing CLI """
    runner = CliRunner()
    examples = os.path.dirname(__file__) + '/fuzz_example/'

    # Testing option --help
    result = runner.invoke(cli.fuzz_cmd, ['--help'])
    assert result.exit_code == 0
    assert 'Usage' in result.output

    # building custom tail program for testing
    process = subprocess.Popen(
        ["make", "-C", os.path.dirname(examples)+"/tail"])
    process.communicate()
    process.wait()

    # path to the tail binary
    tail = os.path.dirname(examples) + "/tail/tail"

    # 01. Testing tail with binary file
    bin_workload = os.path.dirname(examples) + '/samples/binary/libhtab.so'

    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', tail,
        '--output-dir', '.',
        '--initial-workload', bin_workload,
        '--timeout', '1',
        '--max', '10',
        '--no-plotting',
    ])
    assert result.exit_code == 0
    assert 'Fuzzing successfully finished' in result.output

    # 02. Testing tail on a directory of txt files with coverage
    txt_workload = os.path.dirname(examples) + '/samples/txt'

    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', tail,
        '--output-dir', '.',
        '--initial-workload', txt_workload,
        '--timeout', '1',
        '--source-path', os.path.dirname(tail),
        '--gcno-path', os.path.dirname(tail),
        '--max-size-adjunct', '35000',
        '--icovr', '1.05',
        '--interesting-files-limit', '2',
        '--workloads-filter', '(?notvalidregex?)',
        '--no-plotting',
    ])
    assert result.exit_code == 0
    assert 'Fuzzing successfully finished' in result.output

    # 03. Testing tail with xml files and regex_rules
    xml_workload = os.path.dirname(examples) + '/samples/xml/input.xml'
    regex_file = os.path.dirname(examples) + '/rules.yaml'

    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', tail,
        '--output-dir', '.',
        '--initial-workload', xml_workload,
        '--timeout', '1',
        '--max-size-percentual', '3.5',
        '--mut-count-strategy', 'probabilistic',
        '--regex-rules', regex_file,
        '--no-plotting',
    ])
    assert result.exit_code == 0
    assert 'Fuzzing successfully finished' in result.output

    # 04. Testing tail with empty xml file
    xml_workload = os.path.dirname(examples) + '/samples/xml/empty.xml'

    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', tail,
        '--output-dir', '.',
        '--initial-workload', xml_workload,
        '--timeout', '1',
        '--no-plotting',
    ])
    assert result.exit_code == 0
    assert 'Fuzzing successfully finished' in result.output

    # 05. Testing tail with wierd file type and bad paths for coverage testing (-s, -g)
    wierd_workload = os.path.dirname(
        examples) + '/samples/undefined/wierd.california'

    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', tail,
        '--output-dir', '.',
        '--initial-workload', wierd_workload,
        '--timeout', '1',
        '--max-size-percentual', '3.5',
        '--mut-count-strategy', 'proportional',
        '--source-path', '.',
        '--gcno-path', '.',
        '--no-plotting',
    ])
    assert result.exit_code == 0
    assert 'Fuzzing successfully finished' in result.output

    # 06. Testing for SIGABRT during init testing
    num_workload = os.path.dirname(examples) + '/samples/txt/number.txt'
    process = subprocess.Popen(
        ["make", "-C", os.path.dirname(examples)+"/sigabrt-init"])
    process.communicate()
    process.wait()

    sigabrt_init = os.path.dirname(examples) + "/sigabrt-init/sigabrt"

    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', sigabrt_init,
        '--output-dir', '.',
        '--initial-workload', num_workload,
        '--source-path', os.path.dirname(sigabrt_init),
        '--gcno-path', os.path.dirname(sigabrt_init),
    ])
    assert result.exit_code == 1
    assert 'SIGABRT' in result.output

    # 07. Testing for SIGABRT during fuzz testing
    process = subprocess.Popen(
        ["make", "-C", os.path.dirname(examples)+"/sigabrt-test"])
    process.communicate()
    process.wait()

    sigabrt_test = os.path.dirname(examples) + "/sigabrt-test/sigabrt"

    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', sigabrt_test,
        '--output-dir', '.',
        '--initial-workload', num_workload,
        '--timeout', '1',
        '--source-path', os.path.dirname(sigabrt_test),
        '--gcno-path', os.path.dirname(sigabrt_test),
        '--mut-count-strategy', 'unitary',
        '--execs', '1',
    ])
    assert result.exit_code == 0
    assert 'SIGABRT' in result.output

    # 08. Testing for hang during init testing
    process = subprocess.Popen(
        ["make", "-C", os.path.dirname(examples)+"/hang-init"])
    process.communicate()
    process.wait()

    hang_init = os.path.dirname(examples) + "/hang-init/hang"

    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', hang_init,
        '--output-dir', '.',
        '--initial-workload', num_workload,
        '--source-path', os.path.dirname(hang_init),
        '--gcno-path', os.path.dirname(hang_init),
        '--hang-timeout', '0.001',
        '--no-plotting',
    ])
    assert result.exit_code == 1
    assert 'Timeout' in result.output

    # 09. Testing for hang during fuzz testing
    process = subprocess.Popen(
        ["make", "-C", os.path.dirname(examples)+"/hang-test"])
    process.communicate()
    process.wait()

    hang_test = os.path.dirname(examples) + "/hang-test/hang"

    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', hang_test,
        '--output-dir', '.',
        '--initial-workload', num_workload,
        '--timeout', '1',
        '--source-path', os.path.dirname(hang_test),
        '--gcno-path', os.path.dirname(hang_test),
        '--hang-timeout', '0.001',
        '--execs', '1',
        '--no-plotting',
    ])
    assert result.exit_code == 0
    assert 'Timeout' in result.output

    # 10. Testing UBT for degs
    process = subprocess.Popen(
        ["make", "-C", os.path.dirname(examples)+"/UBT"])
    process.communicate()
    process.wait()

    ubt_test = os.path.dirname(examples) + "/UBT/build/ubt"

    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', ubt_test,
        '--output-dir', '.',
        '--initial-workload', os.path.dirname(examples) + '/UBT/input.txt',
        '--timeout', '1',
        '--hang-timeout', '1',
        '--source-path', os.path.dirname(examples) + '/UBT/src',
        '--gcno-path', os.path.dirname(examples) + '/UBT/build',
        '--max-size-percentual', '1',
        '--mut-count-strategy', 'unitary',
        '--execs', '1',
        '--no-plotting',
    ])
    assert result.exit_code == 0
    assert 'Fuzzing successfully finished' in result.output

    # 11. Testing UBT for deg in initial test

    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', ubt_test,
        '--output-dir', '.',
        '--initial-workload', os.path.dirname(examples) +
        '/UBT/a_small_input.txt',
        '--initial-workload', os.path.dirname(examples) +
        '/UBT/sorted_input.txt',
        '--timeout', '1',
        '--hang-timeout', '0.01',
        '--max-size-percentual', '2',
        '--mut-count-strategy', 'unitary',
        '--no-plotting',
    ])
    assert result.exit_code == 0
    assert 'Fuzzing successfully finished' in result.output


def test_fuzzing_incorrect(pcs_full):
    """Runs basic tests for fuzzing CLI """
    runner = CliRunner()

    # Missing option --cmd
    result = runner.invoke(cli.fuzz_cmd, [
        '--args', '-al',
        '--output-dir', '.',
        '--initial-workload', '.',
    ])
    assert result.exit_code == 2
    assert '--cmd' in result.output

    # Missing option --initial-workload
    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', 'ls',
        '--args', '-al',
        '--output-dir', '.',
    ])
    assert result.exit_code == 2
    assert '--initial-workload"' in result.output

    # Missing option --output-dir
    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', 'ls',
        '--args', '-al',
        '--initial-workload', '.',
    ])
    assert result.exit_code == 2
    assert '--output-dir' in result.output

    # Wrong value for option --source-path
    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', 'ls',
        '--args', '-al',
        '--initial-workload', '.',
        '--output-dir', '.',
        '--source-path', 'WTF~~notexisting'
    ])
    assert result.exit_code == 2
    assert '--source-path' in result.output

    # Wrong value for option --gcno-path
    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', 'ls',
        '--args', '-al',
        '--initial-workload', '.',
        '--output-dir', '.',
        '--gcno-path', 'WTF~~notexisting'
    ])
    assert result.exit_code == 2
    assert '--gcno-path' in result.output

    # Wrong value for option --timeout
    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', 'ls',
        '--args', '-al',
        '--initial-workload', '.',
        '--output-dir', '.',
        '--timeout', 'not_number'
    ])
    assert result.exit_code == 2
    assert '--timeout' in result.output

    # Wrong value for option --hang-timeout
    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', 'ls',
        '--args', '-al',
        '--initial-workload', '.',
        '--output-dir', '.',
        '--hang-timeout', '0'
    ])
    assert result.exit_code == 2
    assert '--hang-timeout' in result.output

    # Wrong value for option --max
    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', 'ls',
        '--args', '-al',
        '--initial-workload', '.',
        '--output-dir', '.',
        '--max', '1.5'
    ])
    assert result.exit_code == 2
    assert '--max' in result.output

    # Wrong value for option --max-size-adjunct
    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', 'ls',
        '--args', '-al',
        '--initial-workload', '.',
        '--output-dir', '.',
        '--max-size-adjunct', 'ola'
    ])
    assert result.exit_code == 2
    assert '--max-size-adjunct' in result.output

    # Wrong value for option --max-size-percentual
    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', 'ls',
        '--args', '-al',
        '--initial-workload', '.',
        '--output-dir', '.',
        '--max-size-percentual', 'two_hundred'
    ])
    assert result.exit_code == 2
    assert '--max-size-percentual' in result.output

    # Wrong value for option --execs
    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', 'ls',
        '--args', '-al',
        '--initial-workload', '.',
        '--output-dir', '.',
        '--execs', '1.6'
    ])
    assert result.exit_code == 2
    assert '--execs' in result.output

    # Wrong value for option --interesting-files-limit
    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', 'ls',
        '--args', '-al',
        '--initial-workload', '.',
        '--output-dir', '.',
        '--interesting-files-limit', '-1'
    ])
    assert result.exit_code == 2
    assert '--interesting-files-limit' in result.output

    # Wrong value for option --icovr
    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', 'ls',
        '--args', '-al',
        '--initial-workload', '.',
        '--output-dir', '.',
        '--icovr', 'notvalidfloat'
    ])
    assert result.exit_code == 2
    assert '--icovr' in result.output

    # Wrong value for option --regex-rules
    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', 'ls',
        '--args', '-al',
        '--initial-workload', '.',
        '--output-dir', '.',
        '--regex-rules', 'e'
    ])
    assert result.exit_code == 1


def test_error_runs(pcs_full, monkeypatch):
    """Try various error states induced by job matrix"""
    matrix = config.Config('local', '', {
        'vcs': {'type': 'git', 'url': '../'},
        'args': ['-al'],
        'workloads': ['.', '..'],
        'postprocessors': [
            {'name': 'fokume', 'params': {}}
        ],
        'execute': {
            'pre_run': [
                'ls | grep "."',
            ]
        }
    })
    monkeypatch.setattr("perun.logic.config.local", lambda _: matrix)
    runner = CliRunner()
    result = runner.invoke(cli.run, ['matrix'])
    assert result.exit_code == 1
    assert "missing 'collectors'" in result.output

    matrix.data['collectors'] = [
        {'name': 'tome', 'params': {}}
    ]

    result = runner.invoke(cli.run, ['matrix'])
    assert result.exit_code == 1
    assert "missing 'cmds'" in result.output
    matrix.data['cmds'] = ['ls']

    result = runner.invoke(cli.run, ['matrix', '-q'])
    assert result.exit_code == 1
    assert "tome collector does not exist" in result.output
    matrix.data['collectors'][0]['name'] = 'time'

    result = runner.invoke(cli.run, ['matrix', '-q'])
    assert result.exit_code == 1
    assert "fokume postprocessor does not exist" in result.output

    monkeypatch.setattr('perun.logic.runner.run_single_job',
                        lambda *_, **__: perun_runner.CollectStatus.ERROR)
    result = runner.invoke(cli.run, ['job', '--cmd', 'ls',
                                     '--args', '-al', '--workload', '.',
                                     '--collector', 'time'
                                     ])
    assert result.exit_code == 1
