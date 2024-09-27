"""Collection of tests for testing tracer"""

from __future__ import annotations

# Standard Imports
import glob
import json
import os
import re
import shutil

# Third-Party Imports
from click.testing import CliRunner
from elftools.dwarf.compileunit import CompileUnit
import pytest
from pprint import pprint

# Perun Imports
from perun import cli
from perun.collect.trace.values import TraceRecord, RecordType, FileSize
from perun.logic import config, locks, temp, pcs
from perun.utils import decorators
from perun.utils.exceptions import SystemTapStartupException
from perun.utils.structs import CollectStatus
from perun.profile.factory import Profile
import perun.collect.trace.run as trace_run
import perun.collect.trace.systemtap.engine as stap
import perun.collect.trace.pin.engine as pin
from perun.collect.trace.pin.parse import parser, instructions_parser
import perun.testing.utils as test_utils


_mocked_stap_code = 0
_mocked_stap_file = "tst_stap_record.txt"


def _mocked_stap(_, **__):
    """System tap mock that does nothing"""
    return


def _mocked_stap2(self, **_):
    """System tap mock, provide OK code and pre-fabricated collection output"""
    data_file = os.path.join(
        os.path.dirname(__file__), "sources", "collect_trace", _mocked_stap_file
    )
    target_file = os.path.join(pcs.get_tmp_directory(), "trace", "files", _mocked_stap_file)
    shutil.copyfile(data_file, target_file)
    if self.data is not None:
        os.remove(self.data)
    self.data = target_file
    if _mocked_stap_code != 0:
        raise SystemTapStartupException("fake")


def _mocked_collect(**kwargs):
    return CollectStatus.OK, "", dict(kwargs)


def _mocked_after(**kwargs):
    return CollectStatus.OK, "", dict(kwargs)


def _mocked_check_dependencies(_):
    return


def _mocked_stap_extraction(_):
    return (
        'process("/home/jirka/perun/tests/sources/collect_trace/tst").mark("BEFORE_CYCLE")\n'
        'process("/home/jirka/perun/tests/sources/collect_trace/tst").mark("BEFORE_CYCLE_end")\n'
        'process("/home/jirka/perun/tests/sources/collect_trace/tst").mark("INSIDE_CYCLE")\n'
    )


def _mocked_stap_extraction2(_):
    """Static probes in ruby code enhanced with some artificial one to trigger all pairing
    possibilities.
    """
    return (
        'process("/home/jirka/perun/experiments/ruby/ruby").mark("array__create")\n'
        'process("/home/jirka/perun/experiments/ruby/ruby").mark("array__end")\n'
        'process("/home/jirka/perun/experiments/ruby/ruby").mark("cmethod__entry")\n'
        'process("/home/jirka/perun/experiments/ruby/ruby").mark("cmethod__return")\n'
        'process("/home/jirka/perun/experiments/ruby/ruby").mark("cmethod__deconstruct")\n'
        'process("/home/jirka/perun/experiments/ruby/ruby").mark("find__require__entry")\n'
        'process("/home/jirka/perun/experiments/ruby/ruby").mark("find__require__return")\n'
        'process("/home/jirka/perun/experiments/ruby/ruby").mark("find__require__begin")\n'
        'process("/home/jirka/perun/experiments/ruby/ruby").mark("gc__mark__begin")\n'
        'process("/home/jirka/perun/experiments/ruby/ruby").mark("gc__mark__end")\n'
        'process("/home/jirka/perun/experiments/ruby/ruby").mark("gc__sweep__begin")\n'
        'process("/home/jirka/perun/experiments/ruby/ruby").mark("gc__sweep__end")\n'
        'process("/home/jirka/perun/experiments/ruby/ruby").mark("hash__create")\n'
        'process("/home/jirka/perun/experiments/ruby/ruby").mark("load__entry")\n'
        'process("/home/jirka/perun/experiments/ruby/ruby").mark("load__return")\n'
        'process("/home/jirka/perun/experiments/ruby/ruby").mark("method__cache__clear")\n'
        'process("/home/jirka/perun/experiments/ruby/ruby").mark("method__entry")\n'
        'process("/home/jirka/perun/experiments/ruby/ruby").mark("method__return")\n'
        'process("/home/jirka/perun/experiments/ruby/ruby").mark("object__create")\n'
        'process("/home/jirka/perun/experiments/ruby/ruby").mark("parse__begin")\n'
        'process("/home/jirka/perun/experiments/ruby/ruby").mark("parse__end")\n'
        'process("/home/jirka/perun/experiments/ruby/ruby").mark("raise")\n'
        'process("/home/jirka/perun/experiments/ruby/ruby").mark("require__entry")\n'
        'process("/home/jirka/perun/experiments/ruby/ruby").mark("require__return")\n'
        'process("/home/jirka/perun/experiments/ruby/ruby").mark("string__create")\n'
        'process("/home/jirka/perun/experiments/ruby/ruby").mark("symbol__create")\n'
        'process("/home/jirka/perun/experiments/ruby/ruby").mark("symbol__deconstruct")\n'
    )


def _mocked_trace_stack(_, __):
    """Provides trace stack for exception output"""
    trace_stack = {
        "func": {
            5983: (
                [
                    TraceRecord(RecordType.FUNC_BEGIN, 0, "ruby_init", 0, 5983, 0),
                    TraceRecord(RecordType.FUNC_BEGIN, 1, "ruby_setup", 3, 5983, 0),
                    TraceRecord(
                        RecordType.FUNC_BEGIN,
                        2,
                        "rb_define_global_function",
                        53036,
                        5983,
                        1,
                    ),
                    TraceRecord(
                        RecordType.FUNC_BEGIN,
                        3,
                        "rb_define_module_function",
                        53041,
                        5983,
                        1,
                    ),
                    TraceRecord(
                        RecordType.FUNC_BEGIN,
                        4,
                        "rb_define_private_method",
                        53045,
                        5983,
                        12,
                    ),
                    TraceRecord(RecordType.FUNC_BEGIN, 5, "rb_intern", 53049, 5983, 63),
                    TraceRecord(RecordType.FUNC_BEGIN, 6, "rb_intern2", 53053, 5983, 70),
                    TraceRecord(RecordType.FUNC_BEGIN, 7, "rb_intern3", 53062, 5983, 70),
                ],
                [],
            )
        },
        "static": {
            5983: {
                "array__create": [
                    TraceRecord(RecordType.StaticSingle, 3, "array__create", 5023, 5983, 3)
                ],
                "string__create": [
                    TraceRecord(RecordType.StaticSingle, 9, "string__create", 53135, 5983, 329)
                ],
                "symbol__create": [
                    TraceRecord(RecordType.StaticSingle, 8, "symbol__create", 52637, 5983, 166)
                ],
                "method__cache__clear": [
                    TraceRecord(
                        RecordType.StaticSingle,
                        7,
                        "method__cache__clear",
                        53006,
                        5983,
                        57,
                    )
                ],
            }
        },
    }
    return trace_stack, {}


def _mocked_parse_record(_):
    raise KeyError


def _mocked_stap_extraction_empty(_):
    return "Tip: /usr/share/doc/systemtap/README.Debian should help you get started."


def _compare_collect_scripts(new_script, reference_script):
    """Compares collect script with its reference scripts

    :param new_script: path to the script to compare
    :param reference_script: path to the reference script
    :return: True if scripts are the same (except machine specific values in the script),
                  False otherwise
    """
    # Replace the machine-specific path to the binary with some generic text to allow for comparison
    with open(new_script, "r") as script:
        content = script.read()
    sub_content = re.sub(r"\(\".*?/tst(\\n)?\"\)", '("cmp")', content)
    with open(reference_script, "r") as cmp:
        cmp_content = cmp.read()
    return sub_content == cmp_content


def _get_latest_collect_script():
    """Return name of the latest collect script from the script directory

    :return: path to the latest trace collector script
    """

    def extract_timestamp(file_name):
        """Extracts the timestamp from the file name

        :param file_name: the name of the file
        :return: the extracted timestamp as int
        """
        _, _, timestamp_block, _ = os.path.basename(file_name).split("_")
        return int("".join(timestamp_block.split("-")))

    # Get all stap script in the directory and find the last one,
    # which will be then analyzed for correctness
    script_dir = os.path.join(pcs.get_tmp_directory(), "trace", "files")
    scripts = glob.glob(os.path.join(script_dir, "collect_script_*.stp"))
    # Find the newest script in the directory
    latest = scripts[0]
    # Extract timestamp from the first script
    latest_timestamp = extract_timestamp(scripts[0])
    for script in scripts:
        # Check every script file and find the biggest timestamp
        timestamp = extract_timestamp(script)
        if timestamp >= latest_timestamp:
            latest_timestamp = timestamp
            latest = script
    return latest


def test_collect_trace_cli_no_stap(monkeypatch, pcs_full):
    """Test the trace collector cli options without SystemTap present"""
    runner = CliRunner()
    target_dir = os.path.join(os.path.split(__file__)[0], "sources", "collect_trace")
    target = os.path.join(target_dir, "tst")

    # Patch the collect and after so that the missing stap doesn't break the test
    monkeypatch.setattr(trace_run, "collect", _mocked_collect)
    monkeypatch.setattr(trace_run, "after", _mocked_after)
    # Patch dependency check for SystemTap engine
    monkeypatch.setattr(stap.SystemTapEngine, "check_dependencies", _mocked_check_dependencies)
    result = runner.invoke(
        cli.cli,
        [
            "-vv",
            "collect",
            f"-c{target}",
            "trace",
            "-f", "main",
            "-f", "main#2",
            "-u", "BEFORE_CYCLE",
            "-u", "BEFORE_CYCLE_end#3",
            "-d", "none",
            "-d", "none_again#2",
            "-g", 2,
            "--no-usdt",
            "-b", target,
            "-t", 2,
            "-z",
            "-k",
            "-vt",
            "-q",
            "-w",
            "-o", "suppress",
            "-i",
        ],
    )  # fmt: skip
    assert result.exit_code == 0

    # Test that non-existing command is not accepted
    monkeypatch.setattr(shutil, "which", lambda *_: None)
    result = runner.invoke(
        cli.collect,
        [
            f"-c{os.path.join('invalid', 'executable', 'path')}",
            "trace",
            "-f",
            "main",
        ],
    )
    assert result.exit_code == 1
    assert "Supplied binary" in result.output

    # Test that non-elf files are not accepted
    not_elf = os.path.join(target_dir, "job.yml")
    result = runner.invoke(cli.collect, [f"-c{not_elf}", "trace", "-f", "main"])
    assert result.exit_code == 1
    assert "Supplied binary" in result.output


def test_collect_trace_utils(pcs_with_root):
    """Test some utility function cases that are hard to reproduce in the usual collector runs."""
    # Skip this test if stap is not present
    if not shutil.which("stap"):
        return

    # Test some lock-related functions
    assert locks.LockType.suffix_to_type(".u_lock") is None
    assert locks.ResourceLock.fromfile("invalid:54321.u_lock") is None
    assert locks.ResourceLock.fromfile("invalid:as445.m_lock") is None

    # Test get_last_line scenario where the last line is also the first
    target_dir = os.path.join(os.path.split(__file__)[0], "sources", "collect_trace")
    target = os.path.join(target_dir, "last_line_test.txt")

    last_line = stap._get_last_line_of(target, FileSize.LONG)
    assert last_line[1] == "end /home/jirka/perun/experiments/quicksort\n"

    # Attempt the locking with another conflicting lock already present
    runner = CliRunner()
    target = os.path.join(target_dir, "tst")
    locks_dir = temp.temp_path(os.path.join("trace", "locks"))
    lock_file = f"tst:1.b_lock"

    temp.touch_temp_dir(locks_dir)
    temp.touch_temp_file(os.path.join(locks_dir, lock_file), protect=True)
    result = runner.invoke(cli.collect, [f"-c{target}", "trace", "-f", "main", "-w"])
    assert result.exit_code == 0


def test_collect_trace(pcs_with_root, trace_collect_job):
    """Test running the trace collector from the CLI with parameter handling

    Expecting no errors
    """
    runner = CliRunner()

    target_dir = os.path.join(os.path.split(__file__)[0], "sources", "collect_trace")
    target = os.path.join(target_dir, "tst")
    job_params = trace_collect_job[4]["collector_params"]["trace"]

    # Test loading the trace parameters
    func = [f"-f{func}" for func in job_params["func"]]
    usdt = [f"-u{usdt}" for usdt in job_params["usdt"]]
    binary = [f"-b{target}"]

    # Test the suppress output handling and that missing stap actually terminates the collection
    result = runner.invoke(
        cli.collect,
        [f"-c{target}", "trace", "-o", "suppress"] + func + usdt + binary,
    )

    if not shutil.which("stap"):
        assert result.exit_code == 1
        assert "Missing dependency command" in result.output
    else:
        assert result.exit_code == 0

    # Running the collection itself requires SystemTap support
    if not shutil.which("stap"):
        return

    # Test running the job from the params using the job file
    # Fixme: yaml parameters applied after the cli, thus cli reports missing parameters
    # script_dir = os.path.split(__file__)[0]
    # source_dir = os.path.join(script_dir, 'sources', 'collect_trace')
    # job_config_file = os.path.join(source_dir, 'job.yml')
    # result = runner.invoke(cli.collect, ['-c{}'.format(target), '-p{}'.format(job_config_file),
    #                                      'trace'])
    # assert result.exit_code == 0

    # Test running the job from the params using the yaml string
    result = runner.invoke(
        cli.collect,
        [f"-c{target}", '-p"global_sampling: 2"', "trace"] + func + usdt + binary,
    )
    assert result.exit_code == 0

    # Try different template
    result = runner.invoke(
        cli.collect,
        [
            "-ot",
            "%collector%-profile",
            f"-c{target}",
            '-p"method: custom"',
            "trace",
        ]
        + func
        + usdt
        + binary,
    )
    del config.runtime().data["format"]
    decorators.remove_from_function_args_cache("lookup_key_recursively")
    assert result.exit_code == 0
    pending_profiles = os.listdir(os.path.join(os.getcwd(), ".perun", "jobs"))
    assert "trace-profile.perf" in pending_profiles

    # Test duplicity detection and pairing
    result = runner.invoke(
        cli.collect,
        [
            f"-c{target}",
            "trace",
            "-f", "main",
            "-f", "main",
            "-f", "main#2",
            "-f", "main#2",
            "-u", "BEFORE_CYCLE",
            "-u", "BEFORE_CYCLE#3",
            "-u", "BEFORE_CYCLE_end",
            "-u", "BEFORE_CYCLE;BEFORE_CYCLE_end",
            "-u", "TEST_SINGLE#4",
            "-u", "TEST_SINGLE2",
            "-f", "test#-3",
            "-k",
        ]
        + binary,
    )  # fmt: skip
    assert result.exit_code == 0
    print(f"TRACE OUTPUT: {result.output}")
    # Compare the created script with the correct one
    assert _compare_collect_scripts(
        _get_latest_collect_script(), os.path.join(target_dir, "cmp_script.txt")
    )

    # Test negative global sampling, it should be converted to no sampling
    # Also test that watchdog and quiet works
    result = runner.invoke(
        cli.collect,
        [f"-c{target}", "trace", "-g", "-2", "-w", "-q", "-k"] + binary + func,
    )
    log_path = os.path.join(pcs.get_log_directory(), "trace")
    logs = glob.glob(os.path.join(log_path, "trace_*.txt"))
    assert len(logs) == 1
    assert "Attempting to build the probes configuration" not in result.output
    assert "SystemTap collection process is up and running" not in result.output
    assert result.exit_code == 0

    # Try missing parameter -c but with 'binary' present
    # This should use the binary parameter as executable
    result = runner.invoke(cli.collect, ["trace", "-i"] + binary + func)
    archives = glob.glob(os.path.join(log_path, "collect_files_*.zip.lzma"))
    assert len(archives) == 1
    assert result.exit_code == 0
    # Try it the other way around
    result = runner.invoke(cli.collect, [f"-c{target}", "trace", "-o", "capture", "-k"] + func)
    files_path = os.path.join(pcs.get_tmp_directory(), "trace", "files")
    capture = glob.glob(os.path.join(files_path, "collect_capture_*.txt"))
    # Two previous tests and this one kept the capture files
    assert len(capture) == 3
    assert result.exit_code == 0

    # Try timeout parameter which actually interrupts a running program
    wait_target = os.path.join(target_dir, "tst_waiting")
    result = runner.invoke(cli.collect, ["-c", wait_target, "trace", "-w", "-f", "main", "-t", 1])
    assert result.exit_code == 0


def test_collect_trace_strategies(monkeypatch, pcs_full):
    """Test various trace collector strategies

    Expecting no errors and correctly generated scripts
    """
    if not shutil.which("stap"):
        return

    # Skip the collection itself since it's not important here
    monkeypatch.setattr(stap.SystemTapEngine, "collect", _mocked_stap)
    runner = CliRunner()

    target_dir = os.path.join(os.path.split(__file__)[0], "sources", "collect_trace")
    target = os.path.join(target_dir, "tst")

    # Test simple userspace strategy without external modification or sampling
    result = runner.invoke(cli.collect, [f"-c{target}", "trace", "-s", "userspace", "-k"])
    assert result.exit_code == 0
    assert _compare_collect_scripts(
        _get_latest_collect_script(), os.path.join(target_dir, "strategy1_script.txt")
    )
    # Test simple u_sampled strategy without external modification
    result = runner.invoke(cli.collect, [f"-c{target}", "trace", "-s", "u_sampled", "-k"])
    assert result.exit_code == 0
    assert _compare_collect_scripts(
        _get_latest_collect_script(), os.path.join(target_dir, "strategy2_script.txt")
    )
    # Test simple all strategy without external modification or sampling
    result = runner.invoke(cli.collect, [f"-c{target}", "trace", "-s", "all", "-k"])
    assert result.exit_code == 0
    assert _compare_collect_scripts(
        _get_latest_collect_script(), os.path.join(target_dir, "strategy3_script.txt")
    )
    # Test simple a_sampled strategy with verbose trace and without external modification
    result = runner.invoke(cli.collect, [f"-c{target}", "trace", "-s", "a_sampled", "-vt", "-k"])
    assert result.exit_code == 0
    assert _compare_collect_scripts(
        _get_latest_collect_script(), os.path.join(target_dir, "strategy4_script.txt")
    )

    # Change the mocked static extractor to empty one
    monkeypatch.setattr(stap, "_extract_usdt_probes", _mocked_stap_extraction_empty)
    # Test userspace strategy without static probes and added global_sampling
    result = runner.invoke(
        cli.collect,
        [
            f"-c{target}",
            "trace",
            "-s", "userspace",
            "--no-usdt",
            "-g", "10",
            "-k",
        ],
    )  # fmt: skip
    assert result.exit_code == 0
    assert _compare_collect_scripts(
        _get_latest_collect_script(), os.path.join(target_dir, "strategy5_script.txt")
    )
    # Test u_sampled strategy without static probes and overriden global_sampling
    # The output should be exactly the same as the previous
    result = runner.invoke(
        cli.collect,
        [
            f"-c{target}",
            "trace",
            "-s", "u_sampled",
            "--no-usdt",
            "-g", "10",
            "-k",
        ],
    )  # fmt: skip
    assert result.exit_code == 0
    assert _compare_collect_scripts(
        _get_latest_collect_script(), os.path.join(target_dir, "strategy5_script.txt")
    )
    # Test userspace strategy with overridden function, respecified function and invalid function
    result = runner.invoke(
        cli.collect,
        [
            f"-c{target}",
            "trace",
            "-s", "userspace",
            "-f", "main#4",
            "-f", "_Z12QuickSortBadPii",
            "-f", "invalid",
            "-k",
        ],
    )  # fmt: skip
    assert result.exit_code == 0
    assert _compare_collect_scripts(
        _get_latest_collect_script(), os.path.join(target_dir, "strategy6_script.txt")
    )
    # Test userspace strategy with invalid static probe (won't be detected as --no-static is used)
    result = runner.invoke(
        cli.collect,
        [
            f"-c{target}",
            "trace",
            "-s", "userspace",
            "--no-usdt",
            "-u", "INVALID",
            "-k",
        ],
    )  # fmt: skip
    assert result.exit_code == 0
    assert _compare_collect_scripts(
        _get_latest_collect_script(), os.path.join(target_dir, "strategy7_script.txt")
    )
    # Test u_sampled strategy with more static probes to check correct pairing
    monkeypatch.setattr(stap, "_extract_usdt_probes", _mocked_stap_extraction2)
    result = runner.invoke(cli.collect, [f"-c{target}", "trace", "-s", "u_sampled", "-k"])
    assert result.exit_code == 0
    assert _compare_collect_scripts(
        _get_latest_collect_script(), os.path.join(target_dir, "strategy8_script.txt")
    )


def test_collect_trace_fail(monkeypatch, pcs_full, trace_collect_job):
    """Test failed collecting using trace collector"""

    if not shutil.which("stap"):
        return
    global _mocked_stap_code
    global _mocked_stap_file

    before_object_count = test_utils.count_contents_on_path(pcs_full.get_path())[0]

    runner = CliRunner()

    target_dir = os.path.join(os.path.split(__file__)[0], "sources", "collect_trace")
    target = os.path.join(target_dir, "tst")

    # Try missing 'command' and 'binary'
    result = runner.invoke(cli.collect, ["trace"])
    assert result.exit_code == 1
    assert "does not exist or is not an executable ELF file" in result.output
    # Try missing probe points
    result = runner.invoke(cli.collect, ["trace", f"-b{target}"])
    assert result.exit_code == 1
    assert "No profiling probes created" in result.output

    # Try invalid parameter --strategy
    result = runner.invoke(cli.collect, [f"-c{target}", "trace", "-sinvalid", "-b", target])
    assert result.exit_code == 2

    # Try binary parameter that is actually not executable ELF
    invalid_target = os.path.join(target_dir, "cpp_sources", "tst.cpp")
    result = runner.invoke(cli.collect, [f"-c{invalid_target}", "trace"])
    assert result.exit_code == 1
    assert "is not an executable ELF file." in result.output

    monkeypatch.setattr(stap.SystemTapEngine, "collect", _mocked_stap2)
    # Test malformed file that ends in unexpected way
    _mocked_stap_file = "record_malformed.txt"
    result = runner.invoke(cli.collect, [f"-c{target}", "-w 1", "trace", "-s", "userspace"])
    # However, the collector should still be able to correctly process it
    assert result.exit_code == 0
    after_object_count = test_utils.count_contents_on_path(pcs_full.get_path())[0]
    # 4 new objects - three indexes and resulting profile
    assert before_object_count + 4 == after_object_count
    before_object_count = after_object_count

    # Test malformed file that ends in another unexpected way
    _mocked_stap_file = "record_malformed2.txt"
    result = runner.invoke(cli.collect, [f"-c{target}", "-w 2", "trace", "-s", "userspace"])
    # Check if the collector managed to process the file
    assert result.exit_code == 0
    after_object_count = test_utils.count_contents_on_path(pcs_full.get_path())[0]
    assert before_object_count + 1 == after_object_count
    before_object_count = after_object_count

    # Test malformed file that has corrupted record
    _mocked_stap_file = "record_malformed3.txt"
    result = runner.invoke(cli.collect, [f"-c{target}", "-w 3", "trace", "-s", "userspace"])
    # Check if the collector managed to process the file
    assert result.exit_code == 0
    after_object_count = test_utils.count_contents_on_path(pcs_full.get_path())[0]
    assert before_object_count + 1 == after_object_count

    before_object_count = after_object_count

    # Test malformed file that has misplaced data chunk
    _mocked_stap_file = "record_malformed4.txt"
    result = runner.invoke(cli.collect, [f"-c{target}", "-w 4", "trace", "-s", "userspace"])
    # Check if the collector managed to process the file
    assert result.exit_code == 0
    after_object_count = test_utils.count_contents_on_path(pcs_full.get_path())[0]
    assert before_object_count + 1 == after_object_count
    before_object_count = after_object_count

    # Simulate the failure of the systemTap
    _mocked_stap_code = 1
    runner.invoke(cli.collect, [f"-c{target}", "trace", "-s", "userspace"])
    # Assert that nothing was added
    after_object_count = test_utils.count_contents_on_path(pcs_full.get_path())[0]
    assert before_object_count == after_object_count
    _mocked_stap_code = 0

    # TODO: needs rework
    # # Simulate the failure during trace processing and stacks output
    # monkeypatch.setattr(parse, '_init_stack_and_map', _mocked_trace_stack)
    # monkeypatch.setattr(parse, '_parse_record', _mocked_parse_record)
    # result = runner.invoke(
    #     cli.collect, ['-c{}'.format(target), '-w 4', 'trace', '-s', 'userspace', '-w']
    # )
    # assert result.exit_code == 1
    # assert 'Error while parsing the raw trace record' in result.output


@pytest.mark.parametrize(
    "mode, additional_arguments",
    [
        ("time", []),
        ("time", ["--collect-arguments"]),
        ("time", ["--collect-basic-blocks"]),
        ("time", ["--collect-basic-blocks-only"]),
        ("time", ["--collect-arguments", "--collect-basic-blocks"]),
        ("instructions", []),
        ("memory", []),
    ],
)
def test_collect_trace_pin_engine(pcs_full, mode, additional_arguments):
    expected_functions = ["main", "QuickSortBad", "BadPartition", "Swap"]
    memory_mode_expected_functions = ["new", "free", "malloc"]
    profiles_path = os.path.join(os.getcwd(), ".perun", "jobs")
    trace_files_path = os.path.join(pcs_full.get_tmp_directory(), "trace", "files")

    runner = CliRunner()
    target = os.path.join(os.path.split(__file__)[0], "sources", "collect_trace", "tst")

    args_as_str = "_".join(arg[2:] for arg in additional_arguments)
    current_profile_name = f"pin_trace_{mode}_{args_as_str}.perf"

    result = runner.invoke(
        cli.collect,
        [
            "--profile-name", current_profile_name,
            "--cmd", target,
            "trace",
            "--engine", "pin",
            "--mode", mode,
            "--keep-temps",
        ]
        + additional_arguments,
    )  # fmt: skip
    pprint(result.output)

    generated_profiles = [file for file in os.listdir(profiles_path) if not file.startswith(".")]
    trace_files = [file for file in os.listdir(trace_files_path) if not file.startswith(".")]

    pin_root = os.environ["PIN_ROOT"] if "PIN_ROOT" in os.environ else ""
    if not pin_root or not os.path.isdir(pin_root):
        assert "Undefined or invalid pin root!" in result.output
        assert len(generated_profiles) == 0
        assert len(trace_files) == 2
        assert all(
            os.stat(os.path.join(trace_files_path, trace_file)).st_size == 0
            for trace_file in trace_files
        )
        assert result.exit_code == 1
        return

    assert current_profile_name in generated_profiles
    assert len(generated_profiles) == 1
    generated_profile_name = generated_profiles[0]
    assert len(trace_files) == 2
    assert any(file.startswith("collect_dynamic-data") for file in trace_files)
    assert any(file.startswith("collect_static-data") for file in trace_files)

    for trace_file in trace_files:
        trace_file_path = os.path.join(trace_files_path, trace_file)
        memory_mode_static_data = mode == "memory" and trace_file.startswith("collect_static-data")
        # Note: special case - memory mode does not produce static data
        assert os.stat(trace_file_path).st_size > 0 or (
            os.stat(trace_file_path).st_size == 0 and memory_mode_static_data
        )
    assert result.exit_code == 0

    generated_profile_path = os.path.join(profiles_path, generated_profile_name)
    with open(generated_profile_path) as profile:
        profile_contents = json.load(profile)

    expected_function_names = expected_functions
    if mode == "memory":
        expected_function_names = memory_mode_expected_functions
    for expected_function_name in expected_function_names:
        any(key.startswith(expected_function_name) for key in profile_contents["resources"])

    if "--collect-arguments" in additional_arguments:
        # Check if some arguments have been collected and that their name and type is present as well
        found_arg_value = False
        for resource_key, resource_values in profile_contents["resources"].items():
            if any(key.startswith("arg_value") for key in resource_values):
                found_arg_value = True
                keys = profile_contents["resource_type_map"][resource_key].keys()
                keys = [key.split("#", 1)[0] for key in keys if "#" in key]
                assert "arg_name" in keys and "arg_type" in keys
        assert found_arg_value

    if any(x.startswith("--collect-basic-blocks") for x in additional_arguments):
        assert any(key.startswith("BBL") for key in profile_contents["resources"])


@pytest.mark.parametrize("target_binary", ["nonexistent", "tst-no-debug"])
def test_collect_trace_pin_engine_wrong_target_binary(monkeypatch, pcs_full, target_binary):
    runner = CliRunner()
    target = os.path.join(os.path.split(__file__)[0], "sources", "collect_trace", target_binary)
    pin_root = os.environ["PIN_ROOT"] if "PIN_ROOT" in os.environ else ""
    if not pin_root or not os.path.isdir(pin_root):
        # assign a fake directory to the PIN_ROOT
        os.environ["PIN_ROOT"] = os.path.abspath(os.path.dirname(__file__))

    result = runner.invoke(
        cli.collect, [
            "--cmd", target,
            "trace",
            "--engine", "pin",
        ]
    )  # fmt: skip

    # revert the fake PIN_ROOT
    os.environ["PIN_ROOT"] = pin_root

    assert "does not exist or is not an executable ELF" in result.output
    assert result.exit_code == 1
    return


def test_collect_trace_pin_engine_invalid_pin_root_path(pcs_full):
    runner = CliRunner()
    target = os.path.join(os.path.split(__file__)[0], "sources", "collect_trace", "tst")
    original_pin_root = os.environ["PIN_ROOT"] if "PIN_ROOT" in os.environ else ""

    os.environ["PIN_ROOT"] = "/invalid/pin/root/path"
    result = runner.invoke(
        cli.collect, [
            "--cmd", target,
            "trace",
            "--engine", "pin",
        ],
    )  # fmt: skip
    os.environ["PIN_ROOT"] = original_pin_root
    pprint(result.output)

    assert "Undefined or invalid pin root!" in result.output
    assert result.exit_code == 1
    return


def test_collect_trace_pin_engine_invalid_mode(pcs_full):
    runner = CliRunner()
    target = os.path.join(os.path.split(__file__)[0], "sources", "collect_trace", "tst")
    pin_root = os.environ["PIN_ROOT"] if "PIN_ROOT" in os.environ else ""
    if not pin_root or not os.path.isdir(pin_root):
        # skip the test when pin is not available
        return

    result = runner.invoke(
        cli.collect, [
            "--cmd", target,
            "trace",
            "--engine", "pin",
            "--mode", "nonexistent",
        ],
    )  # fmt: skip
    pprint(result.output)

    assert result.exit_code == 1
    assert "Unknown pin engine mode!" in result.output
    return


def test_collect_trace_pin_engine_fail_instrumentation(monkeypatch, pcs_full):
    runner = CliRunner()
    target = os.path.join(os.path.split(__file__)[0], "sources", "collect_trace", "tst")
    pin_root = os.environ["PIN_ROOT"] if "PIN_ROOT" in os.environ else ""
    if not pin_root or not os.path.isdir(pin_root):
        # skip the test when pin is not available
        return

    monkeypatch.setattr(pin.PinEngine, "assemble_collect_program", lambda self, **_: None)

    result = runner.invoke(
        cli.collect, [
            "--cmd", target,
            "trace",
            "--engine", "pin",
        ]
    )  # fmt: skip
    pprint(result.output)

    assert result.exit_code == 1
    assert "Failed to instrument the program!" in result.output
    return


def test_pin_parsing_instructions_mode_dynamic_data_has_only_basic_blocks(pcs_full, monkeypatch):
    runner = CliRunner()
    target = os.path.join(os.path.split(__file__)[0], "sources", "collect_trace", "tst")

    def _mocked_collect(self, **_):
        # Write to the file so that the parsing executes
        with open(self.dynamic_data, "w") as dynamic_data_file:
            dynamic_data_file.write("00;123;123;123")

    def _mocked_parse_current_dynamic_entry(self):
        dummy_entry = {
            "granularity": parser.Granularity.RTN,
            "location": parser.InstrumentationLocation.BEFORE,
            "id": 123,
            "tid": 123,
            "pid": 123,
        }
        return instructions_parser.InstructionDataEntry(**dummy_entry)

    monkeypatch.setattr(pin.PinEngine, "check_dependencies", lambda _: None)
    monkeypatch.setattr(pin.PinEngine, "assemble_collect_program", lambda self, **_: None)
    monkeypatch.setattr(pin.PinEngine, "collect", _mocked_collect)
    monkeypatch.setattr(
        instructions_parser.PinInstructionOutputParser,
        "_parse_current_dynamic_entry",
        _mocked_parse_current_dynamic_entry,
    )

    result = runner.invoke(
        cli.collect, [
            "--cmd", target,
            "trace",
            "--engine", "pin",
            "--mode", "instructions"
        ]
    )  # fmt: skip
    pprint(result.output)

    expected_error_msg = "expects only basic blocks in the dynamic data file"
    assert expected_error_msg in result.output
    assert result.exit_code == 1
    return


@pytest.mark.parametrize(
    "mode, entry_index",
    [
        ("instructions", -2),
        ("instructions", -1),
        ("memory", -2),
        ("memory", -1),
        ("time", 0),
        ("time", -1),
    ],
)
def test_pin_parsing_dynamic_data_missing_pair_entries(pcs_full, monkeypatch, mode, entry_index):
    runner = CliRunner()
    target = os.path.join(os.path.split(__file__)[0], "sources", "collect_trace", "tst")

    static_data_contents_instructions = (
        "#Files\n"
        "/home/jirka/perun/tests/collect_trace/cpp_sources/tst.cpp;1\n"
        ";0\n"
        "#Basic blocks\n"
        "94025837187843;main;1;7;1;9;11;12\n"
        "94025837187869;main;1;6;1;13;14\n"
    )
    dynamic_data_contents_instructions = [
        "10;94025837187843;0;1205897\n",
        "11;94025837187843;0;1205897\n",
        "10;94025837187869;0;1205897\n",
        "11;94025837187869;0;1205897\n",
    ]

    static_data_contents_time = (
        "#Files\n"
        "/home/jirka/perun/tests/collect_trace/cpp_sources/sorts.h;1\n"
        ";0\n"
        "#Routines\n"
        "0;Swap;1;77;81\n"
        "1;BadPartition;1;104;120\n"
    )
    dynamic_data_contents_time = [
        "00;1;0;1201051;1724240590601647\n",
        "00;0;0;1201051;1724240590601880\n",
        "01;0;0;1201051;1724240590601888\n",
        "01;1;0;1201051;1724240590601965\n",
    ]

    dynamic_data_contents_memory = [
        "140061472141296;malloc;140061474240492;operator new;0;1206663;/path/file.cpp;0;20\n",
        "140061472141296;malloc;0;1206663;0x5585a9dc62b0\n",
        "140061472143008;free;94031851818233;QuickSortBad;0;1206663;/path/file.cpp;74;0x5585a9dc62d0\n",
        "140061474240464;new;94031851819838;main;0;1206663;/path/file.cpp;14;80\n",
        "140061474240464;new;0;1206663;0x5585a9dc63f0\n",
    ]

    expected_resources_count = 1
    basic_blocks_backlog_unpaired = 1
    functions_backlog_unpaired = 1
    if mode == "instructions":
        dynamic_data_contents = dynamic_data_contents_instructions
        static_data_contents = static_data_contents_instructions

    if mode == "memory":
        dynamic_data_contents = dynamic_data_contents_memory
        static_data_contents = ""
        expected_resources_count = 2

    if mode == "time":
        dynamic_data_contents = dynamic_data_contents_time
        static_data_contents = static_data_contents_time
        basic_blocks_backlog_unpaired = 0

    dynamic_data_contents.pop(entry_index)

    def _mocked_collect(self, **_):
        with open(self.dynamic_data, "w") as dynamic_data_file:
            dynamic_data_file.write("".join(dynamic_data_contents))
        if mode != "memory":
            with open(self.static_data, "w") as static_data_file:
                static_data_file.write(static_data_contents)

    def _mocked_after(**kwargs):
        resources = list(kwargs["config"].engine.transform(**kwargs))
        assert len(resources) == expected_resources_count
        kwargs["profile"] = Profile()
        kwargs["profile"].update_resources({"resources": resources}, "global")
        return CollectStatus.OK, "", dict(kwargs)

    monkeypatch.setattr(pin.PinEngine, "check_dependencies", lambda _: None)
    monkeypatch.setattr(pin.PinEngine, "assemble_collect_program", lambda self, **_: None)
    monkeypatch.setattr(pin.PinEngine, "collect", _mocked_collect)
    monkeypatch.setattr(trace_run, "after", _mocked_after)

    result = runner.invoke(
        cli.cli, [
            "-vvv",
            "-d",
            "collect",
            "--cmd", target,
            "trace",
            "--engine", "pin",
            "--mode", mode
        ],
    )  # fmt: skip
    pprint(result.output)

    assert result.exit_code == 0

    # check some debug messages
    if entry_index == -2 or entry_index == 0:  # if removing the opening entry
        basic_blocks_backlog_unpaired = 0
        functions_backlog_unpaired = 0
        assert "Closing entry does not have a pair in the backlog" in result.output

    unpaired_entries_in_backlogs_cnt = basic_blocks_backlog_unpaired + functions_backlog_unpaired
    if mode in ["instructions", "time"] and unpaired_entries_in_backlogs_cnt > 0:
        assert (
            f"Unpaired entries in backlogs: Functions - {functions_backlog_unpaired} "
            f"and Basic blocks - {basic_blocks_backlog_unpaired}"
        ) in result.output
    if mode == "memory" and entry_index == -1:
        assert "Unpaired memory entries in backlog: 1" in result.output


def test_pin_parsing_malformed_static_data(pcs_full, monkeypatch):
    runner = CliRunner()
    target = os.path.join(os.path.split(__file__)[0], "sources", "collect_trace", "tst")

    static_data_contents = (
        "\n\n#Files\n"
        "/home/jirka/perun/tests/collect_trace/cpp_sources/tst.cpp;1\n"
        ";0\n\n\n\n"
        "#Basic blocks\n"
        "94025837187843;main;1;7;1;9;11;12\n"
        "94025837187869;main;1;6;1;13;14\n"
        "#Invalid table header 123\n"
    )
    dynamic_data_contents = [
        "10;94025837187843;0;1205897\n",
        "11;94025837187843;0;1205897\n",
    ]

    def _mocked_collect(self, **_):
        with open(self.dynamic_data, "w") as dynamic_data_file:
            dynamic_data_file.write("".join(dynamic_data_contents))
        with open(self.static_data, "w") as static_data_file:
            static_data_file.write(static_data_contents)

    monkeypatch.setattr(pin.PinEngine, "check_dependencies", lambda _: None)
    monkeypatch.setattr(pin.PinEngine, "assemble_collect_program", lambda self, **_: None)
    monkeypatch.setattr(pin.PinEngine, "collect", _mocked_collect)

    result = runner.invoke(
        cli.cli, [
            "-vvv",
            "-d",
            "collect",
            "--cmd", target,
            "trace",
            "--engine", "pin",
            "--mode", "instructions",
        ],
    )  # fmt: skip
    pprint(result.output)

    assert result.exit_code == 0
    assert (
        "Skipping table with unknown separator: " "#Invalid table header 123"
    ) in result.output  # debug message
    return


def test_pin_binary_scan_fail(pcs_full, monkeypatch):
    runner = CliRunner()
    target = os.path.join(os.path.split(__file__)[0], "sources", "collect_trace", "tst")

    def _mocked_get_top_DIE(self):
        raise Exception("Dummy exception")

    monkeypatch.setattr(pin.PinEngine, "check_dependencies", lambda _: None)
    monkeypatch.setattr(CompileUnit, "get_top_DIE", _mocked_get_top_DIE)

    result = runner.invoke(
        cli.cli, [
            "-vvv",
            "-d",
            "collect",
            "--cmd", target,
            "trace",
            "--engine", "pin",
            "--collect-arguments",
        ],
    )  # fmt: skip
    pprint(result.output)

    assert result.exit_code == 1
    assert (
        "Couldn't read the DWARF debug info, please ensure that the binary is compiled "
        "with -g option (when using gcc)."
    ) in result.output
