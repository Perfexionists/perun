"""
Basic tests for fuzz-testing mode of perun
"""

from __future__ import annotations

# Standard Imports
import os
import sys
import subprocess

# Third-Party Imports
import pytest
from click.testing import CliRunner

# Perun Imports
from perun import cli
from perun.fuzz.structs import CoverageConfiguration
from perun.testing import asserts
from perun.utils.external import commands
import perun.fuzz.evaluate.by_coverage as coverage_fuzz
import perun.fuzz.evaluate.by_perun as perun_fuzz


@pytest.mark.usefixtures("cleandir")
@pytest.mark.skipif(sys.platform == "darwin", reason="Import perf record is unsupported on macOS")
def test_fuzzing_coverage(capsys):
    """Runs basic tests for fuzzing CLI"""
    examples = os.path.join(os.path.dirname(__file__), "sources", "fuzz_examples")
    gcno_files_path = os.path.join(examples, "hang-test")
    hang_test = os.path.join(gcno_files_path, "hang")
    hang_source = os.path.join(gcno_files_path, "main.c")
    num_workload = os.path.join(examples, "samples", "txt", "number.txt")
    coverage_config = CoverageConfiguration(
        **{"gcno_path": gcno_files_path, "source_path": gcno_files_path}
    )
    coverage_config.source_files.append(hang_source)

    process = subprocess.Popen(["make", "-C", os.path.join(examples, "hang-test")])
    process.communicate()
    process.wait()

    coverage_fuzz.prepare_workspace(gcno_files_path)

    command = " ".join([os.path.abspath(hang_test), num_workload])
    _ = capsys.readouterr()

    commands.run_safely_external_command(command)
    cov = coverage_fuzz.get_coverage_from_dir(os.getcwd(), coverage_config)
    assert cov != 0


@pytest.mark.usefixtures("cleandir")
def test_fuzzing_correct(pcs_with_root):
    """Runs basic tests for fuzzing CLI"""
    runner = CliRunner()
    examples = os.path.join(os.path.dirname(__file__), "sources", "fuzz_examples")

    # Testing option --help
    result = runner.invoke(cli.fuzz_cmd, ["--help"])
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(result, "Usage" in result.output)

    # building custom tail program for testing
    process = subprocess.Popen(["make", "-C", os.path.join(examples, "tail")])
    process.communicate()
    process.wait()

    # path to the tail binary
    tail = os.path.join(examples, "tail", "tail")

    # 01. Testing tail with binary file
    bin_workload = os.path.join(examples, "samples", "binary", "libhtab.so")

    result = runner.invoke(
        cli.fuzz_cmd,
        [
            "--cmd", tail,
            "--output-dir", ".",
            "--input-sample", bin_workload,
            "--timeout", "0.25",
            "--max-size", "10",
            "--no-plotting",
            "--skip-coverage-testing",
            "--collector-params", "time", "repeat: 1",
            "--collector-params", "time", "warmup: 0",
            "--exec-limit", "10",
        ],
    )  # fmt: skip
    asserts.predicate_from_cli(result, result.exit_code == 0)

    # 02. Testing tail on a directory of txt files with coverage
    txt_workload = os.path.join(examples, "samples", "txt")

    result = runner.invoke(
        cli.fuzz_cmd,
        [
            "--cmd", tail,
            "--output-dir", ".",
            "--input-sample", txt_workload,
            "--timeout", "0.25",
            "--source-path", os.path.dirname(tail),
            "--gcno-path", os.path.dirname(tail),
            "--max-size-increase", "35000",
            "--coverage-increase-rate", "1.05",
            "--interesting-files-limit", "2",
            "--workloads-filter", "(?notvalidregex?)",
            "--no-plotting",
            "--collector-params", "time", "repeat: 1",
            "--collector-params", "time", "warmup: 0",
            "--exec-limit", "10",
        ],
    )  # fmt: skip
    asserts.predicate_from_cli(result, result.exit_code == 0)

    # 03. Testing tail with xml files and regex_rules
    xml_workload = os.path.join(examples, "samples", "xml", "input.xml")
    regex_file = os.path.join(examples, "rules.yaml")

    result = runner.invoke(
        cli.fuzz_cmd,
        [
            "--cmd", tail,
            "--output-dir", ".",
            "--input-sample", xml_workload,
            "--timeout", "0.25",
            "--max-size-ratio", "3.5",
            "--mutations-per-rule", "probabilistic",
            "--regex-rules", regex_file,
            "--no-plotting",
            "--skip-coverage-testing",
            "--collector-params", "time", "repeat: 1",
            "--collector-params", "time", "warmup: 0",
            "--exec-limit", "10",
        ],
    )  # fmt: skip
    asserts.predicate_from_cli(result, result.exit_code == 0)

    # 04. Testing tail with empty xml file
    xml_workload = os.path.join(examples, "samples", "xml", "empty.xml")

    result = runner.invoke(
        cli.fuzz_cmd,
        [
            "--cmd", tail,
            "--output-dir", ".",
            "--input-sample", xml_workload,
            "--timeout", "0.25",
            "--no-plotting",
            "--skip-coverage-testing",
            "--collector-params", "time", "repeat: 1",
            "--collector-params", "time", "warmup: 0",
            "--exec-limit", "10",
        ],
    )  # fmt: skip
    asserts.predicate_from_cli(result, result.exit_code == 0)

    # 05. Testing tail with wierd file type and bad paths for coverage testing (-s, -g)
    wierd_workload = os.path.join(examples, "samples", "undefined", "wierd.california")

    result = runner.invoke(
        cli.fuzz_cmd,
        [
            "--cmd", tail,
            "--output-dir", ".",
            "--input-sample", wierd_workload,
            "--timeout", "0.25",
            "--max-size-ratio", "3.5",
            "--source-path", ".",
            "--gcno-path", ".",
            "--no-plotting",
            "--collector-params", "time", "repeat: 1",
            "--collector-params", "time", "warmup: 0",
            "--exec-limit", "10",
        ],
    )  # fmt: skip
    asserts.predicate_from_cli(result, result.exit_code == 0)


@pytest.mark.usefixtures("cleandir")
def test_fuzzing_sigabort(pcs_with_root):
    """Runs basic tests for fuzzing CLI"""
    runner = CliRunner()
    examples = os.path.join(os.path.dirname(__file__), "sources", "fuzz_examples")

    # 06. Testing for SIGABRT during init testing
    num_workload = os.path.join(examples, "samples", "txt", "number.txt")
    process = subprocess.Popen(["make", "-C", os.path.join(examples, "sigabrt-init")])
    process.communicate()
    process.wait()

    sigabrt_init = os.path.join(examples, "sigabrt-init", "sigabrt")

    result = runner.invoke(
        cli.fuzz_cmd,
        [
            "--cmd", sigabrt_init,
            "--output-dir", ".",
            "--input-sample", num_workload,
            "--source-path", os.path.dirname(sigabrt_init),
            "--gcno-path", os.path.dirname(sigabrt_init),
            "--collector-params", "time", "repeat: 1",
            "--collector-params", "time", "warmup: 0",
            "--exec-limit", "10",
            "--no-plotting",
        ],
    )  # fmt: skip
    asserts.predicate_from_cli(result, result.exit_code == 1)
    asserts.predicate_from_cli(result, "SIGABRT" in result.output)

    # 07. Testing for SIGABRT during fuzz testing
    process = subprocess.Popen(["make", "-C", os.path.join(examples, "sigabrt-test")])
    process.communicate()
    process.wait()

    sigabrt_test = os.path.join(examples, "sigabrt-test", "sigabrt")

    result = runner.invoke(
        cli.fuzz_cmd,
        [
            "--cmd", sigabrt_test,
            "--output-dir", ".",
            "--input-sample", num_workload,
            "--timeout", "1",
            "--source-path", os.path.dirname(sigabrt_test),
            "--gcno-path", os.path.dirname(sigabrt_test),
            "--mutations-per-rule", "unitary",
            "--exec-limit", "1",
            "--collector-params", "time", "repeat: 1",
            "--collector-params", "time", "warmup: 0",
        ],
    )  # fmt: skip
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(result, "exit status 134" in result.output)


@pytest.mark.usefixtures("cleandir")
@pytest.mark.skipif(sys.platform == "darwin", reason="Import perf record is unsupported on macOS")
def test_fuzzing_hangs(pcs_with_root, monkeypatch):
    """Runs basic tests for fuzzing CLI"""
    runner = CliRunner()
    examples = os.path.join(os.path.dirname(__file__), "sources", "fuzz_examples")
    num_workload = os.path.join(examples, "samples", "txt", "number.txt")

    # 08. Testing for hang during init testing
    process = subprocess.Popen(["make", "-C", os.path.join(examples, "hang-init")])
    process.communicate()
    process.wait()

    hang_init = os.path.join(examples, "hang-init", "hang")

    result = runner.invoke(
        cli.fuzz_cmd,
        [
            "--cmd", hang_init,
            "--output-dir", ".",
            "--input-sample", num_workload,
            "--source-path", os.path.dirname(hang_init),
            "--gcno-path", os.path.dirname(hang_init),
            "--hang-timeout", "0.01",
            "--no-plotting",
            "--collector-params", "time", "repeat: 1",
            "--collector-params", "time", "warmup: 0",
        ],
    )  # fmt: skip
    asserts.predicate_from_cli(result, result.exit_code == 1)
    asserts.predicate_from_cli(result, "Timeout" in result.output)

    # 09. Testing for hang during fuzz testing
    process = subprocess.Popen(["make", "-C", os.path.join(examples, "hang-test")])
    process.communicate()
    process.wait()

    hang_test = os.path.join(examples, "hang-test", "hang")

    # Fixme: This test is shaky, and should be implemented in different way; it can sometimes fail with error
    old_run_process = commands.run_safely_external_command

    def patched_run_process(*_, **__):
        caller = sys._getframe().f_back.f_code.co_name
        if caller == "target_testing":
            raise subprocess.TimeoutExpired("./hang-test", 10)
        else:
            return old_run_process(*_, **__)

    monkeypatch.setattr(commands, "run_safely_external_command", patched_run_process)

    # during the initial testing
    result = runner.invoke(
        cli.fuzz_cmd,
        [
            "--cmd", hang_test,
            "--output-dir", ".",
            "--input-sample", num_workload,
            "--timeout", "1",
            "--source-path", os.path.dirname(hang_test),
            "--gcno-path", os.path.dirname(hang_test),
            "--mutations-per-rule", "proportional",
            "--hang-timeout", "1",
            "--exec-limit", "1",
            "--no-plotting",
            "--collector-params", "time", "repeat: 1",
            "--collector-params", "time", "warmup: 0",
        ],
    )  # fmt: skip
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(result, "Timeout" in result.output)


@pytest.mark.usefixtures("cleandir")
@pytest.mark.skipif(sys.platform == "darwin", reason="Import perf record is unsupported on macOS")
def test_fuzzing_degradation(pcs_with_root, monkeypatch):
    """Runs basic tests for fuzzing CLI"""
    runner = CliRunner()
    examples = os.path.join(os.path.dirname(__file__), "sources", "fuzz_examples")
    hang_test = os.path.join(examples, "hang-test", "hang")
    num_workload = os.path.join(examples, "samples", "txt", "number.txt")

    def always_true(*_, **__):
        return True

    original_target_testing = perun_fuzz.target_testing
    monkeypatch.setattr(perun_fuzz, "target_testing", always_true)
    # 10. Testing for performance degradations during fuzz testing
    result = runner.invoke(
        cli.fuzz_cmd,
        [
            "--cmd", hang_test,
            "--output-dir", ".",
            "--input-sample", num_workload,
            "--timeout", "1",
            "--source-path", os.path.dirname(hang_test),
            "--gcno-path", os.path.dirname(hang_test),
            "--no-plotting",
            "--interesting-files-limit", "1",
            "--collector-params", "time", "repeat: 1",
            "--collector-params", "time", "warmup: 0",
            "--mutations-per-rule", "unitary",
            "--exec-limit", "1",
        ],
    )  # fmt: skip
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(result, "Founded degradation mutations: 0" not in result.output)
    monkeypatch.setattr(perun_fuzz, "target_testing", original_target_testing)


@pytest.mark.usefixtures("cleandir")
def test_fuzzing_incorrect(pcs_with_root):
    """Runs basic tests for fuzzing CLI"""
    runner = CliRunner()

    # Missing option --cmd
    result = runner.invoke(
        cli.fuzz_cmd,
        [
            "--output-dir", ".",
            "--input-sample", ".",
        ],
    )  # fmt: skip
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, "--cmd" in result.output)

    # Missing option --input-sample
    result = runner.invoke(
        cli.fuzz_cmd,
        [
            "--cmd", "ls",
            "--output-dir", ".",
        ],
    )  # fmt: skip
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, "--input-sample" in result.output)

    # Missing option --output-dir
    result = runner.invoke(
        cli.fuzz_cmd,
        [
            "--cmd", "ls",
            "--input-sample", ".",
        ],
    )  # fmt: skip
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, "--output-dir" in result.output)

    # Wrong value for option --source-path
    result = runner.invoke(
        cli.fuzz_cmd,
        [
            "--cmd", "ls",
            "--input-sample", ".",
            "--output-dir", ".",
            "--source-path", "WTF~~notexisting",
        ],
    )  # fmt: skip
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, "--source-path" in result.output)

    # Wrong value for option --gcno-path
    result = runner.invoke(
        cli.fuzz_cmd,
        [
            "--cmd", "ls",
            "--input-sample", ".",
            "--output-dir", ".",
            "--gcno-path", "WTF~~notexisting",
        ],
    )  # fmt: skip
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, "--gcno-path" in result.output)

    # Wrong value for option --timeout
    result = runner.invoke(
        cli.fuzz_cmd,
        [
            "--cmd", "ls",
            "--input-sample", ".",
            "--output-dir", ".",
            "--timeout", "not_number",
        ],
    )  # fmt: skip
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, "--timeout" in result.output)

    # Wrong value for option --hang-timeout
    result = runner.invoke(
        cli.fuzz_cmd,
        [
            "--cmd", "ls",
            "--input-sample", ".",
            "--output-dir", ".",
            "--hang-timeout", "0",
        ],
    )  # fmt: skip
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, "--hang-timeout" in result.output)

    # Wrong value for option --max
    result = runner.invoke(
        cli.fuzz_cmd,
        [
            "--cmd", "ls",
            "--input-sample", ".",
            "--output-dir", ".",
            "--max-size", "1.5",
        ],
    )  # fmt: skip
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, "--max-size" in result.output)

    # Wrong value for option --max-size-increase
    result = runner.invoke(
        cli.fuzz_cmd,
        [
            "--cmd", "ls",
            "--input-sample", ".",
            "--output-dir", ".",
            "--max-size-increase", "ola",
        ],
    )  # fmt: skip
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, "--max-size-increase" in result.output)

    # Wrong value for option --max-size-ratio
    result = runner.invoke(
        cli.fuzz_cmd,
        [
            "--cmd", "ls",
            "--input-sample", ".",
            "--output-dir", ".",
            "--max-size-ratio", "two_hundred",
        ],
    )  # fmt: skip
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, "--max-size-ratio" in result.output)

    # Wrong value for option --exec-limit
    result = runner.invoke(
        cli.fuzz_cmd,
        [
            "--cmd", "ls",
            "--input-sample", ".",
            "--output-dir", ".",
            "--exec-limit", "1.6",
        ],
    )  # fmt: skip
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, "--exec-limit" in result.output)

    # Wrong value for option --interesting-files-limit
    result = runner.invoke(
        cli.fuzz_cmd,
        [
            "--cmd", "ls",
            "--input-sample", ".",
            "--output-dir", ".",
            "--interesting-files-limit", "-1",
        ],
    )  # fmt: skip
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, "--interesting-files-limit" in result.output)

    # Wrong value for option --coverage-increase-rate
    result = runner.invoke(
        cli.fuzz_cmd,
        [
            "--cmd", "ls",
            "--input-sample", ".",
            "--output-dir", ".",
            "--coverage-increase-rate", "notvalidfloat",
        ],
    )  # fmt: skip
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, "--coverage-increase-rate" in result.output)

    # Wrong value for option --regex-rules
    result = runner.invoke(
        cli.fuzz_cmd,
        [
            "--cmd", "ls",
            "--input-sample", ".",
            "--output-dir", ".",
            "--regex-rules", "e",
        ],
    )  # fmt: skip
    asserts.predicate_from_cli(result, result.exit_code == 1)


@pytest.mark.usefixtures("cleandir")
def test_fuzzing_errors(pcs_with_root, monkeypatch):
    """Test various error states"""
    runner = CliRunner()
    examples = os.path.join(os.path.dirname(__file__), "sources", "fuzz_examples")
    txt_workload = os.path.join(examples, "samples", "txt", "simple.txt")
    tail = os.path.join(examples, "tail", "tail")

    # Test when target testing returns error
    old_run_process = commands.run_safely_external_command

    def patched_run_process(*_, **__):
        caller = sys._getframe().f_back.f_code.co_name
        if caller == "target_testing":
            raise subprocess.CalledProcessError(1, "")
        else:
            return old_run_process(*_, **__)

    old_check_output = commands.get_stdout_from_external_command

    def patched_check_output(*_, **__):
        return "real 0.01\nuser 0.00\nsys 0.00"

    monkeypatch.setattr(commands, "run_safely_external_command", patched_run_process)
    monkeypatch.setattr(commands, "get_stdout_from_external_command", patched_check_output)
    result = runner.invoke(
        cli.fuzz_cmd,
        [
            "--cmd", tail,
            "--output-dir", ".",
            "--input-sample", txt_workload,
            "--timeout", "0.25",
            "--source-path", os.path.dirname(tail),
            "--gcno-path", os.path.dirname(tail),
            "--max-size-increase", "35000",
            "--coverage-increase-rate", "1.05",
            "--interesting-files-limit", "1",
            "--no-plotting",
            "--collector-params", "time", "repeat: 1",
            "--collector-params", "time", "warmup: 0",
        ],
    )  # fmt: skip
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(result, "Faults: 0" not in result.output)
    monkeypatch.setattr(commands, "run_safely_external_command", old_run_process)

    # Test when target testing returns error
    old_target_perun_testing = perun_fuzz.target_testing

    def patched_target_testing(*_, **__):
        raise subprocess.CalledProcessError(1, "")

    monkeypatch.setattr(perun_fuzz, "target_testing", patched_target_testing)
    result = runner.invoke(
        cli.fuzz_cmd,
        [
            "--cmd", tail,
            "--output-dir", ".",
            "--input-sample", txt_workload,
            "--timeout", "1",
            "--source-path", os.path.dirname(tail),
            "--gcno-path", os.path.dirname(tail),
            "--max-size-increase", "35000",
            "--coverage-increase-rate", "1.05",
            "--interesting-files-limit", "1",
            "--no-plotting",
            "--collector-params", "time", "repeat: 1",
            "--collector-params", "time", "warmup: 0",
        ],
    )  # fmt: skip
    asserts.predicate_from_cli(result, result.exit_code == 0)
    monkeypatch.setattr(coverage_fuzz, "target_testing", old_target_perun_testing)
    monkeypatch.setattr(commands, "get_stdout_from_external_command", old_check_output)
