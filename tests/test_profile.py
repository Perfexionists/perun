"""Collection of tests for Perun's Profiles"""
from __future__ import annotations

# Standard Imports

# Third-Party Imports
import pytest
import git

# Perun Imports
from perun.logic import commands, config
from perun.profile.factory import Profile
import perun.profile.helpers as profiles
import perun.testing.utils as test_utils


def test_loading(pcs_single_prof, valid_profile_pool):
    """Test new feature of loading the profile straight out of profile info

    Expecting correct behaviour
    """
    test_utils.populate_repo_with_untracked_profiles(pcs_single_prof.get_path(), valid_profile_pool)
    untracked = commands.get_untracked_profiles()
    assert len(untracked) != 0

    first_untracked = untracked[0].load()
    assert isinstance(first_untracked, Profile)
    assert "header" in first_untracked.keys()

    git_repo = git.Repo(pcs_single_prof.get_vcs_path())
    head = str(git_repo.head.commit)

    minor_version_profiles = profiles.load_list_for_minor_version(head)
    assert len(minor_version_profiles) != 0
    first_indexed = minor_version_profiles[0].load()
    assert isinstance(first_indexed, Profile)
    assert "header" in first_indexed


def test_name_generation(capsys):
    """Test generation of profile names for various configurations

    Expecting correct outputs
    """
    rt_config = config.runtime()
    rt_config.set("format.output_profile_template", "%collector%-of-%cmd%-%workload%")
    profile_name = profiles.generate_profile_name(
        {
            "header": {
                "cmd": "./whatever/sub/fun/mybin -O2 -q",
                "workload": "input.txt",
            },
            "collector_info": {"name": "memory", "params": {}},
        }
    )
    assert profile_name == "memory-of-[mybin_-O2_-q]-[input.txt].perf"

    rt_config.set("format.output_profile_template", "%collector%-%postprocessors%-%origin%")
    profile_name = profiles.generate_profile_name(
        {
            "origin": "c4592b902b7c5773d20693021b76d83de63e4a3a",
            "header": {
                "cmd": "./whatever/sub/fun/mybin -O2 -q",
                "workload": "input.txt",
            },
            "postprocessors": [
                {"name": "clusterizer", "params": {}},
                {"name": "normalizer", "params": {}},
            ],
            "collector_info": {"name": "memory", "params": {}},
        }
    )
    assert (
        profile_name
        == "memory-after-clusterizer-and-normalizer-c4592b902b7c5773d20693021b76d83de63e4a3a.perf"
    )

    # Lookup of collectors params
    rt_config.set("format.output_profile_template", "%collector%-sampling-[%memory.sampling%]")
    profile_name = profiles.generate_profile_name(
        {
            "origin": "c4592b902b7c5773d20693021b76d83de63e4a3a",
            "header": {
                "cmd": "./whatever/sub/fun/mybin -O2 -q",
                "workload": "input.txt",
            },
            "postprocessors": [
                {"name": "clusterizer", "params": {}},
                {"name": "normalizer", "params": {}},
            ],
            "collector_info": {"name": "memory", "params": {"sampling": 0.01}},
        }
    )
    assert profile_name == "memory-sampling-[0.01].perf"

    # Lookup in incorrect formatting string
    rt_config.set("format.output_profile_template", "%")
    with pytest.raises(SystemExit):
        profiles.generate_profile_name(
            {
                "origin": "c4592b902b7c5773d20693021b76d83de63e4a3a",
                "header": {
                    "cmd": "./whatever/sub/fun/mybin -O2 -q",
                    "workload": "input.txt",
                },
                "postprocessors": [
                    {"name": "clusterizer", "params": {}},
                    {"name": "normalizer", "params": {}},
                ],
                "collector_info": {"name": "memory", "params": {"sampling": 0.01}},
            }
        )

    _, err = capsys.readouterr()
    assert "formatting string '%' could not be parsed" in err

    # Try missing param
    rt_config.set("format.output_profile_template", "sampling-[%memory.sampling%]")
    profile_name = profiles.generate_profile_name({"collector_info": {"name": "trace"}})
    assert profile_name == "sampling-[_].perf"
