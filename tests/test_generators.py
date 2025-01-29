"""Basic tests of generators"""

from __future__ import annotations

# Standard Imports
import os
from subprocess import CalledProcessError
import sys

# Third-Party Imports
import pytest

# Perun Imports
from perun import workload
from perun.logic import config, runner
from perun.utils import decorators
from perun.utils.common import common_kit
from perun.utils.structs.common_structs import Unit, Executable, CollectStatus, Job
from perun.workload.external_generator import ExternalGenerator
from perun.workload.generator import WorkloadGenerator
from perun.workload.integer_generator import IntegerGenerator
from perun.workload.singleton_generator import SingletonGenerator
from perun.workload.string_generator import StringGenerator
from perun.workload.textfile_generator import TextfileGenerator


def test_integer_generator():
    """Tests generation of integers from given range"""
    collector = Unit("time", {"warmup": 1, "repeat": 1})
    # On macOS, GNU factor executable is called 'gfactor'
    executable_name = "factor" if sys.platform != "darwin" else "gfactor"
    executable = Executable(executable_name)
    integer_job = Job(collector, [], executable)
    integer_generator = IntegerGenerator(integer_job, 10, 100, 10)

    for c_status, profile in integer_generator.generate(runner.run_collector):
        assert c_status == CollectStatus.OK
        assert profile
        assert len(profile["resources"]) > 0

    # Try that the pure generator raises error
    pure_generator = WorkloadGenerator(integer_job)
    with pytest.raises(SystemExit):
        _ = list(pure_generator.generate(runner.run_collector))


def test_integer_generator_for_each():
    """Tests the profile_for_each_workload option"""
    # When profile_for_each_workload is not set, we yield profiles for each workload
    collector = Unit("time", {"warmup": 1, "repeat": 1})
    # On macOS, GNU factor executable is called 'gfactor'
    executable_name = "factor" if sys.platform != "darwin" else "gfactor"
    executable = Executable(executable_name)
    integer_job = Job(collector, [], executable)
    integer_generator = IntegerGenerator(integer_job, 10, 100, 10, profile_for_each_workload=True)

    collection_pairs = list(integer_generator.generate(runner.run_collector))
    assert len(collection_pairs) == 10

    # When profile_for_each_workload is set, then we merge the resources
    integer_generator = IntegerGenerator(integer_job, 10, 100, 10, profile_for_each_workload=False)
    collection_pairs = list(integer_generator.generate(runner.run_collector))
    assert len(collection_pairs) == 1


def test_loading_generators_from_config(monkeypatch, pcs_with_root):
    """Tests loading generator specification from config"""
    # Initialize the testing configurations
    collector = Unit("time", {"warmup": 1, "repeat": 1})
    # On macOS, GNU factor executable is called 'gfactor'
    executable_name = "factor" if sys.platform != "darwin" else "gfactor"
    executable = Executable(executable_name)
    integer_job = Job(collector, [], executable)
    temp_local = config.Config(
        "local",
        "",
        {
            "generators": {
                "workload": [
                    {
                        "id": "gen1",
                        "type": "integer",
                        "min_range": 10,
                        "max_range": 20,
                        "step": 1,
                    }
                ]
            }
        },
    )
    temp_global = config.Config(
        "global",
        "",
        {
            "generators": {
                "workload": [
                    {
                        "id": "gen2",
                        "type": "integer",
                        "min_range": 100,
                        "max_range": 200,
                        "step": 10,
                    },
                    {"id": "gen_incorrect", "min_range": 100},
                    {"id": "gen_almost_correct", "type": "bogus"},
                ]
            }
        },
    )
    monkeypatch.setattr("perun.logic.config.local", lambda _: temp_local)
    monkeypatch.setattr("perun.logic.config.shared", lambda: temp_global)
    # Manually reset the singleton
    decorators.manual_registered_singletons["load_generator_specifications"].instance = None

    spec_map = workload.load_generator_specifications()
    assert len(spec_map.keys()) == 2
    assert "gen1" in spec_map.keys()
    assert "gen2" in spec_map.keys()
    assert "gen_incorrect" not in spec_map.keys()
    assert "gen_almost_correct" not in spec_map.keys()

    # Now test that the generators really work :P
    constructor, params = spec_map["gen1"].constructor, spec_map["gen1"].params
    for c_status, profile in constructor(integer_job, **params).generate(runner.run_collector):
        assert c_status == CollectStatus.OK
        assert profile
        assert len(profile["resources"])
    # Restore the singleton
    decorators.manual_registered_singletons["load_generator_specifications"].instance = None


def test_singleton():
    """Tests singleton generator"""
    collector = Unit("time", {})
    # On macOS, GNU factor executable is called 'gfactor'
    executable_name = "factor" if sys.platform != "darwin" else "gfactor"
    executable = Executable(executable_name)
    integer_job = Job(collector, [], executable)
    singleton_generator = SingletonGenerator(integer_job, "10")

    job_count = 0
    for c_status, profile in singleton_generator.generate(runner.run_collector):
        assert c_status == CollectStatus.OK
        assert profile
        assert len(profile["resources"]) > 0
        job_count += 1
    assert job_count == 1


def test_string_generator():
    """Tests string generator"""
    collector = Unit("time", {"warmup": 1, "repeat": 1})
    executable = Executable("echo")
    string_job = Job(collector, [], executable)
    string_generator = StringGenerator(string_job, 10, 20, 1)

    for c_status, profile in string_generator.generate(runner.run_collector):
        assert c_status == CollectStatus.OK
        assert profile
        assert len(profile["resources"]) > 0


def test_file_generator():
    """Tests file generator"""
    collector = Unit("time", {"warmup": 1, "repeat": 1})
    executable = Executable("wc -l")
    file_job = Job(collector, [], executable)
    file_generator = TextfileGenerator(file_job, 2, 5)

    for c_status, profile in file_generator.generate(runner.run_collector):
        assert c_status == CollectStatus.OK
        assert profile
        assert len(profile["resources"]) > 0


def _generate_temp_files(temp_dir, num):
    """Helper function for generating some temporary files
    :param temp_dir:
    :param num:
    :return:
    """
    common_kit.touch_dir(temp_dir)
    for _ in range(num):
        temp_file = os.path.join(temp_dir, f"tmp{num}_{num * 10}")
        with open(temp_file, "w") as tmp_handle:
            tmp_handle.write(("." * num * 10 + "\n") * num)


@pytest.mark.usefixtures("cleandir")
def test_external_generator(monkeypatch, capsys):
    """Tests external file generator"""

    collector = Unit("time", {"warmup": 1, "repeat": 1})
    executable = Executable("wc -l")
    file_job = Job(collector, [], executable)
    target_dir = os.path.join(os.getcwd(), "test")
    external_generator = ExternalGenerator(file_job, "generate", target_dir, "tmp{rows}_{cols}")

    # replace the running of generator
    def correct_generation(*_, **__):
        _generate_temp_files(target_dir, 3)

    monkeypatch.setattr(
        "perun.utils.external.commands.run_safely_external_command", correct_generation
    )

    for c_status, profile in external_generator.generate(runner.run_collector):
        assert c_status == CollectStatus.OK
        assert profile
        assert len(profile["resources"]) > 0

    # Test when values are incorrectly paired in format
    target_dir = os.path.join(os.getcwd(), "test3")
    common_kit.touch_dir(target_dir)
    external_generator = ExternalGenerator(
        file_job, "generate", target_dir, "tmp{rows}_{cols}_{chars}"
    )
    for c_status, profile in external_generator.generate(runner.run_collector):
        assert c_status == CollectStatus.OK
        assert profile
        assert len(profile["resources"]) > 0
    out, _ = capsys.readouterr()
    assert "Could not match format" in out

    def incorrect_generation(*_, **__):
        raise CalledProcessError(-1, "failed")

    target_dir = os.path.join(os.getcwd(), "test2")
    common_kit.touch_dir(target_dir)
    external_generator = ExternalGenerator(file_job, "generate", target_dir, "tmp{rows}_{cols}")
    monkeypatch.setattr(
        "perun.utils.external.commands.run_safely_external_command", incorrect_generation
    )
    profiles = list(external_generator.generate(runner.run_collector))
    assert len(profiles) == 1
    assert len(list(profiles[0][1].all_resources())) == 0
