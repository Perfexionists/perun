"""Basic tests for running the currently supported collectors"""

import os

import perun.core.logic.runner as runner

__author__ = 'Tomas Fiedor'


def test_collect_complexity(helpers, pcs_full, complexity_collect_job):
    """Test collecting the profile using complexity collector"""
    before_object_count = helpers.count_contents_on_path(pcs_full.path)[0]

    cmd, args, work, collectors, posts, config = complexity_collect_job
    runner.run_single_job(cmd, args, work, collectors, posts, **config)

    # Assert that nothing was removed
    after_object_count = helpers.count_contents_on_path(pcs_full.path)[0]
    assert before_object_count + 1 == after_object_count
    profiles = os.listdir(os.path.join(pcs_full.path, 'jobs'))

    new_profile = profiles[0]
    assert len(profiles) == 1
    assert new_profile.endswith(".perf")

    # Fixme: Add check that the profile was correctly generated


def test_collect_memory(helpers, pcs_full, memory_collect_job):
    """Test collecting the profile using the memory collector"""
    # Fixme: Add check that the profile was correctly generated
    before_object_count = helpers.count_contents_on_path(pcs_full.path)[0]

    runner.run_single_job(*memory_collect_job)

    # Assert that nothing was removed
    after_object_count = helpers.count_contents_on_path(pcs_full.path)[0]
    assert before_object_count + 1 == after_object_count

    profiles = os.listdir(os.path.join(pcs_full.path, 'jobs'))
    new_profile = profiles[0]
    assert len(profiles) == 1
    assert new_profile.endswith(".perf")

    # Fixme: Add check that the profile was correctly generated


def test_collect_time(helpers, pcs_full, capsys):
    """Test collecting the profile using the time collector"""
    # Count the state before running the single job
    before_object_count = helpers.count_contents_on_path(pcs_full.path)[0]

    runner.run_single_job(["echo"], "", ["hello"], ["time"], [])

    # Assert outputs
    out, err = capsys.readouterr()
    assert err == ''
    assert 'Successfully collected data from echo' in out

    # Assert that just one profile was created
    after_object_count = helpers.count_contents_on_path(pcs_full.path)[0]
    assert before_object_count + 1 == after_object_count

    profiles = os.listdir(os.path.join(pcs_full.path, 'jobs'))
    new_profile = profiles[0]
    assert len(profiles) == 1
    assert new_profile.startswith("echo-time-hello")
    assert new_profile.endswith(".perf")

    # Fixme: Add check that the profile was correctly generated
