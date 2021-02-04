"""
Basic tests for fuzz-testing mode of perun
"""

import os
import subprocess
import pytest

from click.testing import CliRunner

import perun.cli as cli
import perun.fuzz.evaluate.by_coverage as coverage_fuzz
from perun.fuzz.structs import CoverageConfiguration

import perun.testing.asserts as asserts


@pytest.mark.usefixtures('cleandir')
def test_fuzzing_coverage(capsys):
    """Runs basic tests for fuzzing CLI """
    examples = os.path.join(os.path.dirname(__file__), 'sources', 'fuzz_examples')
    gcno_files_path = os.path.join(examples, "hang-test")
    hang_test = os.path.join(gcno_files_path, "hang")
    hang_source = os.path.join(gcno_files_path, "main.c")
    num_workload = os.path.join(examples, 'samples', 'txt', 'number.txt')
    coverage_config = CoverageConfiguration(**{
        'gcno_path': gcno_files_path,
        'source_path': gcno_files_path
    })
    coverage_config.gcov_version = coverage_fuzz.get_gcov_version()
    coverage_config.source_files.append(hang_source)

    process = subprocess.Popen(
        ["make", "-C", os.path.join(examples, "hang-test")])
    process.communicate()
    process.wait()

    coverage_fuzz.prepare_workspace(gcno_files_path)

    command = " ".join([os.path.abspath(hang_test), num_workload]).split(' ')
    out, _ = capsys.readouterr()

    exit_report = coverage_fuzz.execute_bin(command, 60)
    assert exit_report["exit_code"] == 0
    cov = coverage_fuzz.get_coverage_info(os.getcwd(), coverage_config)
    assert cov != 0


@pytest.mark.usefixtures('cleandir')
def test_fuzzing_correct(pcs_full):
    """Runs basic tests for fuzzing CLI """
    runner = CliRunner()
    examples = os.path.join(os.path.dirname(__file__), 'sources', 'fuzz_examples')

    # Testing option --help
    result = runner.invoke(cli.fuzz_cmd, ['--help'])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(result, 'Usage' in result.output)

    # building custom tail program for testing
    process = subprocess.Popen(
        ["make", "-C", os.path.join(examples, "tail")])
    process.communicate()
    process.wait()

    # path to the tail binary
    tail = os.path.join(examples, "tail", "tail")

    # 01. Testing tail with binary file
    bin_workload = os.path.join(examples, 'samples', 'binary', 'libhtab.so')

    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', tail,
        '--output-dir', '.',
        '--input-sample', bin_workload,
        '--timeout', '1',
        '--max', '10',
        '--no-plotting',
    ])
    asserts.predicate_from_cli(result, result.exit_code == 0)

    # 02. Testing tail on a directory of txt files with coverage
    txt_workload = os.path.join(examples, 'samples', 'txt')

    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', tail,
        '--output-dir', '.',
        '--input-sample', txt_workload,
        '--timeout', '1',
        '--source-path', os.path.dirname(tail),
        '--gcno-path', os.path.dirname(tail),
        '--max-size-gain', '35000',
        '--coverage-increase-rate', '1.05',
        '--interesting-files-limit', '2',
        '--workloads-filter', '(?notvalidregex?)',
        '--no-plotting',
    ])
    asserts.predicate_from_cli(result, result.exit_code == 0)

    # 03. Testing tail with xml files and regex_rules
    xml_workload = os.path.join(examples, 'samples', 'xml', 'input.xml')
    regex_file = os.path.join(examples, 'rules.yaml')

    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', tail,
        '--output-dir', '.',
        '--input-sample', xml_workload,
        '--timeout', '1',
        '--max-size-ratio', '3.5',
        '--mutations-per-rule', 'probabilistic',
        '--regex-rules', regex_file,
        '--no-plotting',
    ])
    asserts.predicate_from_cli(result, result.exit_code == 0)

    # 04. Testing tail with empty xml file
    xml_workload = os.path.join(examples, 'samples', 'xml', 'empty.xml')

    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', tail,
        '--output-dir', '.',
        '--input-sample', xml_workload,
        '--timeout', '1',
        '--no-plotting',
    ])
    asserts.predicate_from_cli(result, result.exit_code == 0)

    # 05. Testing tail with wierd file type and bad paths for coverage testing (-s, -g)
    wierd_workload = os.path.join(examples, 'samples', 'undefined', 'wierd.california')

    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', tail,
        '--output-dir', '.',
        '--input-sample', wierd_workload,
        '--timeout', '1',
        '--max-size-ratio', '3.5',
        '--source-path', '.',
        '--gcno-path', '.',
        '--no-plotting',
    ])
    asserts.predicate_from_cli(result, result.exit_code == 0)


@pytest.mark.usefixtures('cleandir')
def test_fuzzing_sigabort(pcs_full):
    """Runs basic tests for fuzzing CLI """
    runner = CliRunner()
    examples = os.path.join(os.path.dirname(__file__), 'sources', 'fuzz_examples')

    # 06. Testing for SIGABRT during init testing
    num_workload = os.path.join(examples, 'samples', 'txt', 'number.txt')
    process = subprocess.Popen(
        ["make", "-C", os.path.join(examples, "sigabrt-init")])
    process.communicate()
    process.wait()

    sigabrt_init = os.path.join(examples, "sigabrt-init", "sigabrt")

    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', sigabrt_init,
        '--output-dir', '.',
        '--input-sample', num_workload,
        '--source-path', os.path.dirname(sigabrt_init),
        '--gcno-path', os.path.dirname(sigabrt_init),
    ])
    asserts.predicate_from_cli(result, result.exit_code == 1)
    asserts.predicate_from_cli(result, 'SIGABRT' in result.output)

    # 07. Testing for SIGABRT during fuzz testing
    process = subprocess.Popen(
        ["make", "-C", os.path.join(examples, "sigabrt-test")])
    process.communicate()
    process.wait()

    sigabrt_test = os.path.join(examples, "sigabrt-test", "sigabrt")

    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', sigabrt_test,
        '--output-dir', '.',
        '--input-sample', num_workload,
        '--timeout', '1',
        '--source-path', os.path.dirname(sigabrt_test),
        '--gcno-path', os.path.dirname(sigabrt_test),
        '--mutations-per-rule', 'unitary',
        '--exec-limit', '1',
    ])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(result, 'exit status 134' in result.output)


@pytest.mark.usefixtures('cleandir')
def test_fuzzing_hangs(pcs_full):
    """Runs basic tests for fuzzing CLI """
    runner = CliRunner()
    examples = os.path.join(os.path.dirname(__file__), 'sources', 'fuzz_examples')
    num_workload = os.path.join(examples, 'samples', 'txt', 'number.txt')

    # 08. Testing for hang during init testing
    process = subprocess.Popen(
        ["make", "-C", os.path.join(examples, "hang-init")])
    process.communicate()
    process.wait()

    hang_init = os.path.join(examples, "hang-init", "hang")

    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', hang_init,
        '--output-dir', '.',
        '--input-sample', num_workload,
        '--source-path', os.path.dirname(hang_init),
        '--gcno-path', os.path.dirname(hang_init),
        '--hang-timeout', '0.05',
        '--no-plotting',
    ])
    asserts.predicate_from_cli(result, result.exit_code == 1)
    asserts.predicate_from_cli(result, 'Timeout' in result.output)

    # 09. Testing for hang during fuzz testing
    process = subprocess.Popen(
        ["make", "-C", os.path.join(examples, "hang-test")])
    process.communicate()
    process.wait()

    hang_test = os.path.join(examples,  "hang-test", "hang")

    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', hang_test,
        '--output-dir', '.',
        '--input-sample', num_workload,
        '--timeout', '1',
        '--source-path', os.path.dirname(hang_test),
        '--gcno-path', os.path.dirname(hang_test),
        '--mutations-per-rule', 'proportional',
        '--hang-timeout', '0.05',
        '--exec-limit', '1',
        '--no-plotting',
    ])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(result, 'Timeout' in result.output)


@pytest.mark.usefixtures('cleandir')
def test_fuzzing_degradation(pcs_full):
    """Runs basic tests for fuzzing CLI """
    runner = CliRunner()
    examples = os.path.join(os.path.dirname(__file__), 'sources', 'fuzz_examples')
    hang_test = os.path.join(examples,  "hang-test", "hang")
    num_workload = os.path.join(examples, 'samples', 'txt', 'number.txt')

    # 10. Testing for performance degradations during fuzz testing
    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', hang_test,
        '--output-dir', '.',
        '--input-sample', num_workload,
        '--timeout', '1',
        '--source-path', os.path.dirname(hang_test),
        '--gcno-path', os.path.dirname(hang_test),
        '--no-plotting',
        '--interesting-files-limit', '1'
    ])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(result, 'Founded degradation mutations: 0' not in result.output)


@pytest.mark.usefixtures('cleandir')
def test_fuzzing_incorrect(pcs_full):
    """Runs basic tests for fuzzing CLI """
    runner = CliRunner()

    # Missing option --cmd
    result = runner.invoke(cli.fuzz_cmd, [
        '--args', '-al',
        '--output-dir', '.',
        '--input-sample', '.',
    ])
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, '--cmd' in result.output)

    # Missing option --input-sample
    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', 'ls',
        '--args', '-al',
        '--output-dir', '.',
    ])
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, '--input-sample' in result.output)

    # Missing option --output-dir
    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', 'ls',
        '--args', '-al',
        '--input-sample', '.',
    ])
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, '--output-dir' in result.output)

    # Wrong value for option --source-path
    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', 'ls',
        '--args', '-al',
        '--input-sample', '.',
        '--output-dir', '.',
        '--source-path', 'WTF~~notexisting'
    ])
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, '--source-path' in result.output)

    # Wrong value for option --gcno-path
    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', 'ls',
        '--args', '-al',
        '--input-sample', '.',
        '--output-dir', '.',
        '--gcno-path', 'WTF~~notexisting'
    ])
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, '--gcno-path' in result.output)

    # Wrong value for option --timeout
    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', 'ls',
        '--args', '-al',
        '--input-sample', '.',
        '--output-dir', '.',
        '--timeout', 'not_number'
    ])
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, '--timeout' in result.output)

    # Wrong value for option --hang-timeout
    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', 'ls',
        '--args', '-al',
        '--input-sample', '.',
        '--output-dir', '.',
        '--hang-timeout', '0'
    ])
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, '--hang-timeout' in result.output)

    # Wrong value for option --max
    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', 'ls',
        '--args', '-al',
        '--input-sample', '.',
        '--output-dir', '.',
        '--max', '1.5'
    ])
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, '--max' in result.output)

    # Wrong value for option --max-size-gain
    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', 'ls',
        '--args', '-al',
        '--input-sample', '.',
        '--output-dir', '.',
        '--max-size-gain', 'ola'
    ])
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, '--max-size-gain' in result.output)

    # Wrong value for option --max-size-ratio
    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', 'ls',
        '--args', '-al',
        '--input-sample', '.',
        '--output-dir', '.',
        '--max-size-ratio', 'two_hundred'
    ])
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, '--max-size-ratio' in result.output)

    # Wrong value for option --exec-limit
    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', 'ls',
        '--args', '-al',
        '--input-sample', '.',
        '--output-dir', '.',
        '--exec-limit', '1.6'
    ])
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, '--exec-limit' in result.output)

    # Wrong value for option --interesting-files-limit
    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', 'ls',
        '--args', '-al',
        '--input-sample', '.',
        '--output-dir', '.',
        '--interesting-files-limit', '-1'
    ])
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, '--interesting-files-limit' in result.output)

    # Wrong value for option --coverage-increase-rate
    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', 'ls',
        '--args', '-al',
        '--input-sample', '.',
        '--output-dir', '.',
        '--coverage-increase-rate', 'notvalidfloat'
    ])
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, '--coverage-increase-rate' in result.output)

    # Wrong value for option --regex-rules
    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', 'ls',
        '--args', '-al',
        '--input-sample', '.',
        '--output-dir', '.',
        '--regex-rules', 'e'
    ])
    asserts.predicate_from_cli(result, result.exit_code == 1)
