"""
Basic tests for fuzz-testing mode of perun
"""

import os
import subprocess

from click.testing import CliRunner

import perun.cli as cli


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
        '--input-sample', bin_workload,
        '--timeout', '1',
        '--max', '10',
        '--no-plotting',
    ])
    assert result.exit_code == 0

    # 02. Testing tail on a directory of txt files with coverage
    txt_workload = os.path.dirname(examples) + '/samples/txt'

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
    assert result.exit_code == 0

    # 03. Testing tail with xml files and regex_rules
    xml_workload = os.path.dirname(examples) + '/samples/xml/input.xml'
    regex_file = os.path.dirname(examples) + '/rules.yaml'

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
    assert result.exit_code == 0

    # 04. Testing tail with empty xml file
    xml_workload = os.path.dirname(examples) + '/samples/xml/empty.xml'

    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', tail,
        '--output-dir', '.',
        '--input-sample', xml_workload,
        '--timeout', '1',
        '--no-plotting',
    ])
    assert result.exit_code == 0

    # 05. Testing tail with wierd file type and bad paths for coverage testing (-s, -g)
    wierd_workload = os.path.dirname(
        examples) + '/samples/undefined/wierd.california'

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
    assert result.exit_code == 0

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
        '--input-sample', num_workload,
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
        '--input-sample', num_workload,
        '--timeout', '1',
        '--source-path', os.path.dirname(sigabrt_test),
        '--gcno-path', os.path.dirname(sigabrt_test),
        '--mutations-per-rule', 'unitary',
        '--exec_limit', '1',
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
        '--input-sample', num_workload,
        '--source-path', os.path.dirname(hang_init),
        '--gcno-path', os.path.dirname(hang_init),
        '--hang-timeout', '0.05',
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
        '--input-sample', num_workload,
        '--timeout', '1',
        '--source-path', os.path.dirname(hang_test),
        '--gcno-path', os.path.dirname(hang_test),
        '--mutations-per-rule', 'proportional',
        '--hang-timeout', '0.05',
        '--exec_limit', '1',
        '--no-plotting',
    ])
    assert result.exit_code == 0
    assert 'Timeout' in result.output

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
    assert result.exit_code == 0
    assert 'Founded degradation mutations: 0' not in result.output


def test_fuzzing_incorrect(pcs_full):
    """Runs basic tests for fuzzing CLI """
    runner = CliRunner()

    # Missing option --cmd
    result = runner.invoke(cli.fuzz_cmd, [
        '--args', '-al',
        '--output-dir', '.',
        '--input-sample', '.',
    ])
    assert result.exit_code == 2
    assert '--cmd' in result.output

    # Missing option --input-sample
    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', 'ls',
        '--args', '-al',
        '--output-dir', '.',
    ])
    assert result.exit_code == 2
    assert '--input-sample"' in result.output

    # Missing option --output-dir
    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', 'ls',
        '--args', '-al',
        '--input-sample', '.',
    ])
    assert result.exit_code == 2
    assert '--output-dir' in result.output

    # Wrong value for option --source-path
    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', 'ls',
        '--args', '-al',
        '--input-sample', '.',
        '--output-dir', '.',
        '--source-path', 'WTF~~notexisting'
    ])
    assert result.exit_code == 2
    assert '--source-path' in result.output

    # Wrong value for option --gcno-path
    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', 'ls',
        '--args', '-al',
        '--input-sample', '.',
        '--output-dir', '.',
        '--gcno-path', 'WTF~~notexisting'
    ])
    assert result.exit_code == 2
    assert '--gcno-path' in result.output

    # Wrong value for option --timeout
    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', 'ls',
        '--args', '-al',
        '--input-sample', '.',
        '--output-dir', '.',
        '--timeout', 'not_number'
    ])
    assert result.exit_code == 2
    assert '--timeout' in result.output

    # Wrong value for option --hang-timeout
    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', 'ls',
        '--args', '-al',
        '--input-sample', '.',
        '--output-dir', '.',
        '--hang-timeout', '0'
    ])
    assert result.exit_code == 2
    assert '--hang-timeout' in result.output

    # Wrong value for option --max
    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', 'ls',
        '--args', '-al',
        '--input-sample', '.',
        '--output-dir', '.',
        '--max', '1.5'
    ])
    assert result.exit_code == 2
    assert '--max' in result.output

    # Wrong value for option --max-size-gain
    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', 'ls',
        '--args', '-al',
        '--input-sample', '.',
        '--output-dir', '.',
        '--max-size-gain', 'ola'
    ])
    assert result.exit_code == 2
    assert '--max-size-gain' in result.output

    # Wrong value for option --max-size-ratio
    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', 'ls',
        '--args', '-al',
        '--input-sample', '.',
        '--output-dir', '.',
        '--max-size-ratio', 'two_hundred'
    ])
    assert result.exit_code == 2
    assert '--max-size-ratio' in result.output

    # Wrong value for option --exec_limit
    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', 'ls',
        '--args', '-al',
        '--input-sample', '.',
        '--output-dir', '.',
        '--exec_limit', '1.6'
    ])
    assert result.exit_code == 2
    assert '--exec_limit' in result.output

    # Wrong value for option --interesting-files-limit
    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', 'ls',
        '--args', '-al',
        '--input-sample', '.',
        '--output-dir', '.',
        '--interesting-files-limit', '-1'
    ])
    assert result.exit_code == 2
    assert '--interesting-files-limit' in result.output

    # Wrong value for option --coverage-increase-rate
    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', 'ls',
        '--args', '-al',
        '--input-sample', '.',
        '--output-dir', '.',
        '--coverage-increase-rate', 'notvalidfloat'
    ])
    assert result.exit_code == 2
    assert '--coverage-increase-rate' in result.output

    # Wrong value for option --regex-rules
    result = runner.invoke(cli.fuzz_cmd, [
        '--cmd', 'ls',
        '--args', '-al',
        '--input-sample', '.',
        '--output-dir', '.',
        '--regex-rules', 'e'
    ])
    assert result.exit_code == 1
