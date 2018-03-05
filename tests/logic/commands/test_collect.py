"""Basic tests for running the currently supported collectors"""

import os

import perun.logic.runner as runner

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


def test_collect_memory(capsys, helpers, pcs_full, memory_collect_job, memory_collect_no_debug_job):
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

    cmd, args, _, colls, posts = memory_collect_job
    runner.run_single_job(cmd, args, ["hello"], colls, posts, **{'no_func': 'fun', 'sampling': 0.1})

    profiles = os.listdir(os.path.join(pcs_full.path, 'jobs'))
    new_smaller_profile = [p for p in profiles if p != new_profile][0]
    assert len(profiles) == 2
    assert new_smaller_profile.endswith(".perf")

    # Assert that nothing was removed
    after_second_object_count = helpers.count_contents_on_path(pcs_full.path)[0]
    assert after_object_count + 1 == after_second_object_count

    # Fixme: Add check that the profile was correctly generated

    runner.run_single_job(*memory_collect_no_debug_job)
    last_object_count = helpers.count_contents_on_path(pcs_full.path)[0]
    _, err = capsys.readouterr()
    assert after_second_object_count == last_object_count
    assert 'debug info' in err


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
    assert new_profile.endswith(".perf")

    # Fixme: Add check that the profile was correctly generated
