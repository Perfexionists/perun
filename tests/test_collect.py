"""Basic tests for running the currently supported collectors"""

# Standard Imports
import os
from subprocess import SubprocessError, CalledProcessError
import sys
import subprocess
import signal

# Third-Party Imports
from click.testing import CliRunner
import pytest

# Perun Imports
from perun.cli_groups import collect_cli
from perun.collect.complexity import makefiles, symbols, run as complexity, configurator
from perun.logic import pcs, runner as run
from perun.profile.factory import Profile
from perun.testing import asserts, utils as test_utils
from perun.utils import log
from perun.utils.common import common_kit
from perun.utils.external import commands
from perun.utils.structs.common_structs import Unit, Executable, CollectStatus, RunnerReport, Job
from perun.workload.integer_generator import IntegerGenerator


def _mocked_external_command(_, **__):
    return 1


def _mocked_always_correct(*_, **__):
    return 0


def _mocked_flag_support(_):
    return True


def _mocked_libs_existence_fails(_):
    return False


def _mocked_libs_existence_exception(_):
    raise NameError


def _mocked_record_processing(_, __, ___, ____):
    return 1


def _mocked_symbols_extraction(_):
    return ["_Z13SLList_insertP6SLListi", "main", "_fini", "_init", "_Z13SLList_removeP6SLListi",
            "_ZN9SLListclsD1Ev", "_ZN9SLListclsD2Ev", "_ZN9SLListclsC1Ev", "_ZN9SLListclsC2Ev",
            "_ZN9SLListcls6InsertEi", "__libc_csu_fini", "_Z14SLList_destroyP6SLList", "_start",
            "_ZN9SLListcls10SLLelemclsC1Ei", "_Z13SLList_searchP6SLListi", "__libc_csu_init",
            "_Z11SLList_initP6SLList", "_ZN9SLListcls10SLLelemclsC2Ei", "_ZN9SLListcls6SearchEi",
            "deregister_tm_clones", "register_tm_clones", "__do_global_dtors_aux", "frame_dummy",
            "_dl_relocate_static_pie", "_Z14SLList_destroyP6SLList", "_ZN9SLListclsD1Ev", "main",
            "_ZN9SLListclsD2Ev", "_fini", "_ZN9SLListcls6SearchEi", "_start",
            "_Z11SLList_initP6SLList", "_ZN9SLListcls10SLLelemclsC1Ei", "_init",
            "_ZN9SLListcls6InsertEi", "_ZN9SLListcls10SLLelemclsC2Ei", "_Z13SLList_insertP6SLListi",
            "_ZN9SLListclsC2Ev", "_Z13SLList_searchP6SLListi", "__libc_csu_init", "__libc_csu_fini",
            "_ZN9SLListclsC1Ev", "_Z13SLList_removeP6SLListi",
            "_ZNSt8__detail12_Insert_baseIiSt4pairIKiSt6vectorI5ColorSaIS4_EEESaIS7_ENS_10_"
            "Select1stESt8equal_toIiESt4hashIiENS_18_Mod_range_hashingENS_20_Default_ranged_hash"
            "ENS_20_Prime_rehash_policyENS_17_Hashtable_traitsILb0ELb0ELb1EEEEC1Ev"]  # fmt: skip


# TODO: Skipping the tests is a temporary solution. Ideally, we would like to have some mechanism
#  in place that keeps track of various requirements (platform, system, python, ...) for individual
#  commands and notifies the user when a certain command cannot be executed.
@pytest.mark.skipif(sys.platform == "darwin", reason="Incompatible compilation for macOS")
def test_collect_complexity(monkeypatch, pcs_with_root, complexity_collect_job):
    """Test collecting the profile using complexity collector"""
    before_object_count = test_utils.count_contents_on_path(pcs_with_root.get_path())[0]

    cmd, work, collectors, posts, config = complexity_collect_job
    head = pcs.vcs().get_minor_version_info(pcs.vcs().get_minor_head())
    result = run.run_single_job(cmd, work, collectors, posts, [head], **config)
    assert result == CollectStatus.OK

    # Assert that nothing was removed
    after_object_count = test_utils.count_contents_on_path(pcs_with_root.get_path())[0]
    assert before_object_count + 2 == after_object_count
    profiles = list(
        filter(
            test_utils.index_filter,
            os.listdir(os.path.join(pcs_with_root.get_path(), "jobs")),
        )
    )

    new_profile = profiles[0]
    assert len(profiles) == 1
    assert new_profile.endswith(".perf")

    # Fixme: Add check that the profile was correctly generated

    script_dir = os.path.join(os.path.split(__file__)[0], "sources", "collect_complexity", "target")
    job_params = complexity_collect_job[4]["collector_params"]["complexity"]

    files = [f"-f{os.path.abspath(os.path.join(script_dir, file))}" for file in job_params["files"]]
    rules = [f"-r{rule}" for rule in job_params["rules"]]
    samplings = sum(
        [[f"-s {sample['func']}", sample["sample"]] for sample in job_params["sampling"]], []
    )
    runner = CliRunner()
    result = runner.invoke(
        collect_cli.collect,
        [
            f"-c{job_params['target_dir']}",
            "-w input",
            "complexity",
            f"-t{job_params['target_dir']}",
        ]
        + files
        + rules
        + samplings,
    )
    asserts.predicate_from_cli(result, result.exit_code == 0)

    # test some scoped and templatized prototypes taken from a more difficult project
    monkeypatch.setattr(symbols, "extract_symbols", _mocked_symbols_extraction)
    more_rules = [
        "Gif::Ctable::Ctable(Gif::Ctable&&)",
        (
            "std::tuple<int&&>&& std::forward<std::tuple<int&&>"
            " >(std::remove_reference<std::tuple<int&&> >::type&)"
        ),
    ]
    rules.extend([f"-r{rule}" for rule in more_rules])
    result = runner.invoke(
        collect_cli.collect,
        [f"-c{job_params['target_dir']}", "complexity", f"-t{job_params['target_dir']}"]
        + files
        + rules
        + samplings,
    )
    asserts.predicate_from_cli(result, result.exit_code == 0)
    asserts.predicate_from_cli(result, "Stored generated profile" in result.output)


@pytest.mark.skipif(sys.platform == "darwin", reason="Incompatible compilation for macOS")
def test_collect_complexity_errors(monkeypatch, pcs_with_root, complexity_collect_job):
    """Test various scenarios where something goes wrong during the collection process."""

    # Yeah, I mocked the fuck out of this context, since these are not really important stuff
    def mocked_safe_external(*_, **__):
        return b"", b""

    old_run = commands.run_external_command
    old_cfg = configurator.create_runtime_config
    old_safe_run = commands.run_safely_external_command
    monkeypatch.setattr(commands, "run_external_command", _mocked_always_correct)
    monkeypatch.setattr(configurator, "create_runtime_config", _mocked_always_correct)
    monkeypatch.setattr(commands, "run_safely_external_command", mocked_safe_external)

    # Get the job.yml parameters
    script_dir = os.path.join(os.path.split(__file__)[0], "sources", "collect_complexity", "target")
    job_params = complexity_collect_job[4]["collector_params"]["complexity"]

    files = [f"-f{os.path.abspath(os.path.join(script_dir, file))}" for file in job_params["files"]]
    rules = [f"-r{rule}" for rule in job_params["rules"]]
    samplings = sum(
        [[f"-s {sample['func']}", sample["sample"]] for sample in job_params["sampling"]], []
    )

    # prepare the runner
    runner = CliRunner()

    # Try missing parameters --target-dir and --files
    result = runner.invoke(collect_cli.collect, ["complexity"])
    asserts.predicate_from_cli(result, result.exit_code == 1)
    asserts.predicate_from_cli(result, "--target-dir parameter must be supplied" in result.output)

    result = runner.invoke(collect_cli.collect, ["complexity", f"-t{job_params['target_dir']}"])
    asserts.predicate_from_cli(result, result.exit_code == 1)
    asserts.predicate_from_cli(result, "--files parameter must be supplied" in result.output)

    # Try supplying invalid directory path, which is a file instead
    invalid_target = os.path.join(os.path.dirname(script_dir), "job.yml")
    result = runner.invoke(collect_cli.collect, ["complexity", f"-t{invalid_target}"])
    asserts.predicate_from_cli(result, result.exit_code == 1)
    asserts.predicate_from_cli(result, "already exists" in result.output)

    # Simulate the failure of 'cmake'/'make' utility
    def mocked_make(cmd, *_, **__):
        if cmd == ["make"]:
            return 1
        else:
            return 0

    monkeypatch.setattr(commands, "run_external_command", _mocked_external_command)
    command = (
        [f"-c{job_params['target_dir']}", "complexity", f"-t{job_params['target_dir']}"]
        + files
        + rules
        + samplings
    )
    result = runner.invoke(collect_cli.collect, command)
    asserts.predicate_from_cli(
        result, "Command 'cmake' returned non-zero exit status 1" in result.output
    )
    monkeypatch.setattr(commands, "run_external_command", mocked_make)
    result = runner.invoke(collect_cli.collect, command)
    asserts.predicate_from_cli(
        result, "Command 'make' returned non-zero exit status 1" in result.output
    )
    monkeypatch.setattr(commands, "run_external_command", _mocked_always_correct)

    # Simulate that some required library is missing
    old_libs_existence = makefiles._libraries_exist
    monkeypatch.setattr(makefiles, "_libraries_exist", _mocked_libs_existence_fails)
    result = runner.invoke(collect_cli.collect, command)
    asserts.predicate_from_cli(result, "libraries are missing" in result.output)

    # Simulate that the libraries directory path cannot be found
    monkeypatch.setattr(makefiles, "_libraries_exist", _mocked_libs_existence_exception)
    result = runner.invoke(collect_cli.collect, command)
    asserts.predicate_from_cli(result, "Unable to locate" in result.output)
    monkeypatch.setattr(makefiles, "_libraries_exist", old_libs_existence)

    # Simulate the failure of output processing
    # We mock some data to trace.log
    common_kit.touch_dir(os.path.join(job_params["target_dir"], "bin"))
    with open(os.path.join(job_params["target_dir"], "bin", "trace.log"), "w") as mock_handle:
        mock_handle.write("a b c d\na b c d")
    old_record_processing = complexity._process_file_record
    monkeypatch.setattr(complexity, "_process_file_record", _mocked_record_processing)
    result = runner.invoke(collect_cli.collect, command)
    asserts.predicate_from_cli(result, "Call stack error" in result.output)
    monkeypatch.setattr(complexity, "_process_file_record", old_record_processing)

    # Simulate the failure of output processing
    old_find_braces = symbols._find_all_braces

    def mock_find_all_braces(s, b, e):
        return [1] if b == "(" and e == ")" else old_find_braces(s, b, e)

    monkeypatch.setattr(symbols, "_find_all_braces", mock_find_all_braces)
    result = runner.invoke(collect_cli.collect, command)
    asserts.predicate_from_cli(result, "wrong prototype of function" in result.output)
    monkeypatch.setattr(symbols, "_find_all_braces", old_find_braces)

    # Simulate missing dependencies
    monkeypatch.setattr("shutil.which", lambda *_: False)
    result = runner.invoke(collect_cli.collect, command)
    asserts.predicate_from_cli(result, "Could not find 'make'" in result.output)
    asserts.predicate_from_cli(result, "Could not find 'cmake'" in result.output)

    def mock_raised_exception(*_, **__):
        raise CalledProcessError(-1, "failed")

    monkeypatch.setattr(commands, "run_safely_external_command", mock_raised_exception)
    status, msg, _ = complexity.collect(Executable("pikachu"))
    assert status == CollectStatus.ERROR
    assert msg == "Err: command could not be run.: Command 'failed' died with <Signals.SIGHUP: 1>."

    monkeypatch.setattr(commands, "run_external_command", old_run)
    monkeypatch.setattr(commands, "run_safely_external_command", old_safe_run)
    monkeypatch.setattr(configurator, "create_runtime_config", old_cfg)


@pytest.mark.skipif(sys.platform == "darwin", reason="Incompatible compilation for macOS")
def test_collect_memory(capsys, pcs_with_root, memory_collect_job, memory_collect_no_debug_job):
    """Test collecting the profile using the memory collector"""
    # Fixme: Add check that the profile was correctly generated
    before_object_count = test_utils.count_contents_on_path(pcs_with_root.get_path())[0]
    head = pcs.vcs().get_minor_version_info(pcs.vcs().get_minor_head())
    memory_collect_job += ([head],)

    run.run_single_job(*memory_collect_job)

    # Assert that nothing was removed
    after_object_count = test_utils.count_contents_on_path(pcs_with_root.get_path())[0]
    assert before_object_count + 2 == after_object_count

    profiles = list(
        filter(
            test_utils.index_filter,
            os.listdir(os.path.join(pcs_with_root.get_path(), "jobs")),
        )
    )
    new_profile = profiles[0]
    assert len(profiles) == 1
    assert new_profile.endswith(".perf")

    cmd, _, colls, posts, _ = memory_collect_job
    run.run_single_job(
        cmd,
        ["hello"],
        colls,
        posts,
        [head],
        **{"no_func": "fun", "sampling": 0.1},
    )

    profiles = list(
        filter(
            test_utils.index_filter,
            os.listdir(os.path.join(pcs_with_root.get_path(), "jobs")),
        )
    )
    new_smaller_profile = [p for p in profiles if p != new_profile][0]
    assert len(profiles) == 2
    assert new_smaller_profile.endswith(".perf")

    # Assert that nothing was removed
    after_second_object_count = test_utils.count_contents_on_path(pcs_with_root.get_path())[0]
    assert after_object_count + 1 == after_second_object_count

    log.VERBOSITY = log.VERBOSE_DEBUG
    memory_collect_no_debug_job += ([head],)
    run.run_single_job(*memory_collect_no_debug_job)
    last_object_count = test_utils.count_contents_on_path(pcs_with_root.get_path())[0]
    _, err = capsys.readouterr()
    assert after_second_object_count == last_object_count
    assert "debug info" in err
    assert 'File "' in err
    log.VERBOSITY = log.VERBOSE_RELEASE

    target_bin = memory_collect_job[0][0]
    collector_unit = Unit("memory", {"all": False, "no_func": "main"})
    executable = Executable(str(target_bin))
    assert executable.to_escaped_string() != ""
    job = Job("memory", [], executable)
    _, prof = run.run_collector(collector_unit, job)
    prof = Profile(prof)

    assert len(list(prof.all_resources())) == 2

    collector_unit = Unit("memory", {"all": False, "no_source": "memory_collect_test.c"})
    job = Job("memory", [], executable)
    _, prof = run.run_collector(collector_unit, job)
    prof = Profile(prof)

    assert len(list(prof.all_resources())) == 0

    # Try running memory from CLI
    runner = CliRunner()
    result = runner.invoke(collect_cli.collect, [f"-c{job.executable.cmd}", "memory"])
    assert result.exit_code == 0


@pytest.mark.skipif(sys.platform == "darwin", reason="Incompatible compilation for macOS")
def test_collect_memory_incorrect(monkeypatch, capsys, pcs_with_root, memory_collect_job):
    """Test collecting the profile using the memory collector"""
    # Fixme: Add check that the profile was correctly generated
    head = pcs.vcs().get_minor_version_info(pcs.vcs().get_minor_head())
    memory_collect_job += ([head],)

    # Patch os.path.isfile so for libmalloc.so it returns, that it is missing forcing recompilation
    original_is_file = os.path.isfile

    def patched_is_file(path):
        if "malloc.so" in path:
            return False
        else:
            return original_is_file(path)

    monkeypatch.setattr("os.path.isfile", patched_is_file)

    original_call = subprocess.call
    return_code_for_make = 0

    def patched_call(cmd, *_, **__):
        if cmd == ["make"]:
            return return_code_for_make
        else:
            return original_call(cmd, *_, **__)

    monkeypatch.setattr("subprocess.call", patched_call)

    # Try issue, when the libmalloc library is not there
    run.run_single_job(*memory_collect_job)
    out, _ = capsys.readouterr()
    assert "Dynamic library libmalloc - not found" in common_kit.escape_ansi(out)

    # Try compiling again, but now with an error during the compilation
    return_code_for_make = 1
    run.run_single_job(*memory_collect_job)
    _, err = capsys.readouterr()
    assert "Build of the library failed" in err

    return_code_for_make = 0

    # Try error while parsing logs
    def patched_parse(*args):
        raise IndexError

    monkeypatch.setattr("perun.collect.memory.parsing.parse_log", patched_parse)
    run.run_single_job(*memory_collect_job)
    _, err = capsys.readouterr()
    assert "Could not parse the log file due to" in err

    def patched_run(_):
        return 42, "dummy"

    monkeypatch.setattr("perun.collect.memory.syscalls.run", patched_run)
    run.run_single_job(*memory_collect_job)
    _, err = capsys.readouterr()
    assert "Execution of binary failed with error code: 42" in err


def test_collect_memory_with_generator(pcs_with_root, memory_collect_job):
    """Tries to collect the memory with integer generators"""
    executable = Executable(memory_collect_job[0][0])
    collector = Unit("memory", {})
    integer_job = Job(collector, [], executable)
    integer_generator = IntegerGenerator(integer_job, 1, 3, 1)
    memory_profiles = list(integer_generator.generate(run.run_collector))
    assert len(memory_profiles) == 1


@pytest.mark.skipif(sys.platform == "darwin", reason="Incompatible clang-3.5 binary for macOS")
def test_collect_bounds(monkeypatch, pcs_with_root):
    """Test collecting the profile using the bounds collector"""
    current_dir = os.path.split(__file__)[0]
    test_dir = os.path.join(current_dir, "sources", "collect_bounds")
    sources = [os.path.join(test_dir, src) for src in os.listdir(test_dir) if src.endswith(".c")]
    single_sources = [os.path.join(test_dir, "partitioning.c")]
    job = Job(Unit("bounds", {"sources": sources}), [], Executable("echo hello"))

    status, prof = run.run_collector(job.collector, job)
    assert status == CollectStatus.OK
    assert len(prof["global"]["resources"]) == 19

    job = Job(Unit("bounds", {"sources": single_sources}), [], Executable("echo hello"))

    status, prof = run.run_collector(job.collector, job)
    assert status == CollectStatus.OK
    assert len(prof["global"]["resources"]) == 8

    original_function = commands.run_safely_external_command

    def before_returning_error(cmd, **kwargs):
        raise SubprocessError("something happened")

    monkeypatch.setattr(
        "perun.utils.external.commands.run_safely_external_command", before_returning_error
    )
    status, prof = run.run_collector(job.collector, job)
    assert status == CollectStatus.ERROR

    def collect_returning_error(cmd, **kwargs):
        if "loopus" in cmd:
            raise SubprocessError("something happened")
        else:
            original_function(cmd, **kwargs)

    monkeypatch.setattr(
        "perun.utils.external.commands.run_safely_external_command", collect_returning_error
    )

    status, prof = run.run_collector(job.collector, job)
    assert status == CollectStatus.ERROR


def test_collect_time(monkeypatch, pcs_with_root, capsys):
    """Test collecting the profile using the time collector"""
    # Count the state before running the single job
    before_object_count = test_utils.count_contents_on_path(pcs_with_root.get_path())[0]
    head = pcs.vcs().get_minor_version_info(pcs.vcs().get_minor_head())

    run.run_single_job(["echo"], ["hello"], ["time"], [], [head])

    # Assert outputs
    out, err = capsys.readouterr()
    assert err == ""
    assert "Collecting by time from `echo hello` - succeeded" in common_kit.escape_ansi(out)

    # Assert that just one profile was created
    # + 1 for index
    after_object_count = test_utils.count_contents_on_path(pcs_with_root.get_path())[0]
    assert before_object_count + 2 == after_object_count

    profiles = list(
        filter(
            test_utils.index_filter,
            os.listdir(os.path.join(pcs_with_root.get_path(), "jobs")),
        )
    )
    new_profile = profiles[0]
    assert len(profiles) == 1
    assert new_profile.endswith(".perf")

    # Test running time with error
    run.run_single_job(["echo"], ["hello"], ["time"], [], [head])

    def collect_raising_exception(**kwargs):
        raise Exception("Something happened lol!")

    monkeypatch.setattr("perun.collect.time.run.collect", collect_raising_exception)
    run.run_single_job(["echo"], ["hello"], ["time"], [], [head])
    _, err = capsys.readouterr()
    assert "Something happened lol!" in err


def test_integrity_tests(capsys):
    """Basic tests for checking integrity of runners"""
    mock_report = RunnerReport(complexity, "postprocessor", {"profile": {}})
    run.check_integrity_of_runner(complexity, "postprocessor", mock_report)
    out, err = capsys.readouterr()

    assert "complexity is missing postprocess() function" in out
    assert "" == err

    mock_report = RunnerReport(complexity, "collector", {})
    run.check_integrity_of_runner(complexity, "collector", mock_report)
    out, err = capsys.readouterr()
    assert "collector complexity does not return any profile"
    assert "" == err


def test_teardown(pcs_with_root, monkeypatch, capsys):
    """Basic tests for integrity of the teardown phase"""
    head = pcs.vcs().get_minor_version_info(pcs.vcs().get_minor_head())
    original_phase_f = run.run_phase_function

    # Assert that collection went OK and teardown returns error
    status = run.run_single_job(["echo"], ["hello"], ["time"], [], [head])
    assert status == CollectStatus.OK

    def teardown_returning_error(report, phase):
        if phase == "teardown":
            result = (CollectStatus.ERROR, "error in teardown", {})
            report.update_from(*result)
        else:
            original_phase_f(report, phase)

    monkeypatch.setattr("perun.logic.runner.run_phase_function", teardown_returning_error)
    status = run.run_single_job(["echo"], ["hello"], ["time"], [], [head])
    assert status == CollectStatus.ERROR
    _, err = capsys.readouterr()
    assert "error in teardown" in err

    # Assert that collection went Wrong, teardown went OK, and still returns the error
    def teardown_not_screwing_things(report, phase):
        if phase == "teardown":
            print("Teardown was executed")
            assert report.status == CollectStatus.ERROR
            result = (CollectStatus.OK, "", {})
            report.update_from(*result)
        elif phase == "before":
            result = (CollectStatus.ERROR, "error while before", {})
            report.update_from(*result)

    monkeypatch.setattr("perun.logic.runner.run_phase_function", teardown_not_screwing_things)
    status = run.run_single_job(["echo"], ["hello"], ["time"], [], [head])
    assert status == CollectStatus.ERROR
    out, err = capsys.readouterr()
    assert "Teardown was executed" in out
    assert "error while before" in err

    # Test signals
    def collect_firing_sigint(report, phase):
        if phase == "collect":
            os.kill(os.getpid(), signal.SIGINT)
        else:
            original_phase_f(report, phase)

    monkeypatch.setattr("perun.logic.runner.run_phase_function", collect_firing_sigint)
    status = run.run_single_job(["echo"], ["hello"], ["time"], [], [head])
    assert status == CollectStatus.ERROR
    out, err = capsys.readouterr()
    assert "while collecting by time: received signal" in err


@pytest.mark.skipif(sys.platform == "darwin", reason="Perf not available on macOS")
def test_collect_kperf(monkeypatch, pcs_with_root, capsys):
    """Test collecting the profile using the time collector"""
    # Count the state before running the single job
    before_object_count = test_utils.count_contents_on_path(pcs_with_root.get_path())[0]

    runner = CliRunner()
    result = runner.invoke(
        collect_cli.collect, ["-c", "ls", "-w", ".", "kperf", "-w", "1", "-r", "1"]
    )
    assert result.exit_code == 0
    after_object_count = test_utils.count_contents_on_path(pcs_with_root.get_path())[0]
    assert before_object_count + 2 == after_object_count

    # Test sudo (mocked)
    def mocked_safe_external(*_, **__):
        return b"", b""

    old_run = commands.run_external_command
    monkeypatch.setattr(commands, "run_safely_external_command", mocked_safe_external)
    result = runner.invoke(
        collect_cli.collect, ["-c", "ls", "-w", ".", "kperf", "-w", "1", "-r", "1", "--with-sudo"]
    )
    assert result.exit_code == 0

    def mocked_fail_external(cmd, *args, **kwargs):
        if "ls" in cmd:
            raise subprocess.CalledProcessError("perf", "something happened")
        else:
            return old_run(cmd, *args, **kwargs)

    old_run = commands.run_external_command
    monkeypatch.setattr(commands, "run_safely_external_command", mocked_fail_external)
    monkeypatch.setattr("perun.utils.external.commands.is_executable", lambda command: True)
    result = runner.invoke(
        collect_cli.collect, ["-c", "ls", "-w", ".", "kperf", "-w", "1", "-r", "1", "--with-sudo"]
    )
    assert result.exit_code == 0
    monkeypatch.setattr(commands, "run_safely_external_command", old_run)

    # Test error stuff
    def mocked_is_executable_sc(command):
        if "stackcoll" in command:
            return False
        else:
            return True

    monkeypatch.setattr("perun.utils.external.commands.is_executable", mocked_is_executable_sc)
    result = runner.invoke(
        collect_cli.collect, ["-c", "ls", "-w", ".", "kperf", "-w", "0", "-r", "1"]
    )
    assert result.exit_code != 0
    assert "not-executable" in result.output

    def mocked_is_executable_perf(command):
        if "perf" in command:
            return False
        else:
            return True

    monkeypatch.setattr("perun.utils.external.commands.is_executable", mocked_is_executable_perf)
    result = runner.invoke(
        collect_cli.collect, ["-c", "ls", "-w", ".", "kperf", "-w", "0", "-r", "1"]
    )
    assert result.exit_code != 0
    assert "not-executable" in result.output
