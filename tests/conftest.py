"""Shared fixtures for the testing of functionality of Perun commands."""

from __future__ import annotations

# Standard Imports
from typing import Iterable, Callable, Optional
import glob
import os
import shutil
import subprocess
import tempfile

# Third-Party Imports
import git
import pytest

# Perun Imports
from perun import cli
from perun.logic import commands, pcs, store
from perun.utils import decorators, log, metrics, streams
from perun.utils.common import common_kit
import perun.testing.utils as test_utils
import perun.view_diff.report.run as report


@pytest.fixture(scope="session", autouse=True)
def initialize_cli_modules():
    """
    Initializes the click commands (those that are dynamically initialized) only once per session
    """
    cli.init_unit_commands(False)


@pytest.fixture(scope="session")
def memory_collect_job():
    """
    Returns:
        tuple: ('bin', '', [''], 'memory', [])
    """
    # First compile the stuff, so we know it will work
    script_dir = os.path.split(__file__)[0]
    target_dir = os.path.join(script_dir, "sources", "collect_memory")
    target_src_path = os.path.join(target_dir, "memory_collect_test.c")

    # Compile the testing stuff with debugging information set
    subprocess.check_output(
        ["gcc", "--std=c99", "-g", target_src_path, "-o", "mct"], cwd=target_dir
    )
    target_bin_path = os.path.join(target_dir, "mct")
    assert "mct" in list(os.listdir(target_dir))

    yield [target_bin_path], [""], ["memory"], []

    # Remove the testing stuff
    os.remove(os.path.join(target_dir, "mct"))


@pytest.fixture(scope="session")
def memory_collect_no_debug_job():
    """
    Returns:
        tuple: ('bin', '', [''], 'memory', [])
    """
    # First compile the stuff, so we know it will work
    script_dir = os.path.split(__file__)[0]
    target_dir = os.path.join(script_dir, "sources", "collect_memory")
    target_src_path = os.path.join(target_dir, "memory_collect_test.c")

    # Compile the testing stuff with debugging information set
    subprocess.check_output(
        ["gcc", "--std=c99", target_src_path, "-o", "mct-no-dbg"], cwd=target_dir
    )
    target_bin_path = os.path.join(target_dir, "mct-no-dbg")
    assert "mct-no-dbg" in list(os.listdir(target_dir))

    yield [target_bin_path], [""], ["memory"], []

    # Remove the testing stuff
    os.remove(os.path.join(target_dir, "mct-no-dbg"))


@pytest.fixture(scope="session")
def complexity_collect_job():
    """
    :returns: 'bin', [''], 'memory', [], {}
    """
    # Load the configuration from the job file
    script_dir = os.path.split(__file__)[0]
    source_dir = os.path.join(script_dir, "sources", "collect_complexity")
    target_dir = os.path.join(source_dir, "target")
    job_config_file = os.path.join(source_dir, "job.yml")
    job_config = streams.safely_load_yaml_from_file(job_config_file)

    # Change the target dir to this location
    assert "target_dir" in job_config.keys()
    job_config["target_dir"] = target_dir

    yield [target_dir], [""], ["complexity"], [], {"collector_params": {"complexity": job_config}}

    # Remove target testing directory
    shutil.rmtree(target_dir)


@pytest.fixture(scope="session")
def trace_collect_job():
    """
    :returns: 'bin', '', [''], 'trace', [], {}
    """
    # Load the configuration from the job file
    script_dir = os.path.split(__file__)[0]
    source_dir = os.path.join(script_dir, "sources", "collect_trace")
    target_dir = source_dir
    job_config_file = os.path.join(source_dir, "job.yml")
    job_config = streams.safely_load_yaml_from_file(job_config_file)

    yield [target_dir + "/tst"], [""], ["trace"], [], {"collector_params": {"trace": job_config}}

    # Remove trace collect scripts generated at testing
    [os.remove(filename) for filename in glob.glob(source_dir + "/*.stp")]


@decorators.singleton_with_args
def all_profiles_in(directory, sort=False):
    """Helper function that generates stream of (sorted) profile paths in specified directory

    Arguments:
        directory(str): the name (not path!) of the profile directory
        sort(bool): flag used to lexicographically sort profiles found in the directory

    Returns:
        generator: stream of profile paths located in the given directory
    """
    # Build the directory path and list of all profiles in it
    pool_path = os.path.join(os.path.split(__file__)[0], "profiles", directory)
    profiles = [os.path.join(pool_path, prof_file) for prof_file in os.listdir(pool_path)]
    # Sort if required
    if sort:
        profiles.sort()

    for profile in profiles:
        yield profile


@pytest.fixture(scope="session")
def valid_profile_pool():
    """
    Returns:
        list: dictionary with profiles that are not assigned and can be distributed
    """
    yield list(filter(lambda p: "err" not in p, all_profiles_in("to_add_profiles", True)))


@pytest.fixture(scope="session")
def error_profile_pool():
    """
    Returns:
        list: list with profiles that contains some kind of error
    """
    yield list(filter(lambda p: "err" in p, all_profiles_in("to_add_profiles", True)))


@pytest.fixture(scope="session")
def stored_profile_pool():
    """
    Returns:
        list: list of stored profiles in the pcs_full
    """
    profiles = list(all_profiles_in("full_profiles", True))
    assert len(profiles) == 3
    return profiles


@pytest.fixture(scope="function")
def memory_profiles():
    """
    Returns:
        generator: generator of fully loaded memory profiles as dictionaries
    """
    yield [test_utils.load_profile("to_add_profiles", "new-prof-2-memory-basic.perf")]


def load_all_profiles_in(
    directory: str, prof_filter: Optional[Callable[[str], bool]] = None
) -> Iterable[tuple[str, "Profile"]]:
    """Generates stream of loaded (i.e. dictionaries) profiles in the specified directory.

    :param directory: the name (not path!) of the profile directory
    :param prof_filter: filtering string for filenames
    :return: stream of loaded profiles as tuple (profile_name, dictionary)
    """
    for profile in all_profiles_in(directory):
        if prof_filter is None or prof_filter(profile):
            yield profile, store.load_profile_from_file(profile, True, unsafe_load=True)


@pytest.fixture(scope="function")
def postprocess_profiles():
    """
    Returns:
        generator: generator of fully loaded postprocess profiles as tuple
                   (profile_name, dictionary)
    """
    yield load_all_profiles_in("postprocess_profiles")


@pytest.fixture(scope="function")
def postprocess_profiles_advanced():
    """
    Returns:
        generator: generator of fully loaded postprocess profiles as tuple
                   (profile_name, dictionary)
    """
    yield load_all_profiles_in("postprocess_profiles", lambda x: "rg_ma_kr" in x)


@pytest.fixture(scope="function")
def postprocess_profiles_regression_analysis():
    """
    Returns:
        generator: generator of fully loaded postprocess profiles as tuple
                   (profile_name, dictionary)
    """
    yield load_all_profiles_in("postprocess_profiles", lambda x: "computation" in x)


@pytest.fixture(scope="function")
def full_profiles():
    """
    Returns:
        generator: generator of fully loaded full profiles as tuple
                   (profile_name, dictionary)
    """
    yield load_all_profiles_in("full_profiles")


@pytest.fixture(scope="function")
def pcs_with_degradations():
    """
    * root [file1] p1
    |\
    | * second commit [file2] p2
    * | paralel commit [file3]
    |/
    * merge commit [] p3
    """
    pool_path = os.path.join(os.path.split(__file__)[0], "profiles", "degradation_profiles")
    profiles = [
        os.path.join(pool_path, "linear_base.perf"),
        os.path.join(pool_path, "linear_base_degradated.perf"),
        os.path.join(pool_path, "quad_base.perf"),
    ]
    # Change working dir into the temporary directory
    pcs_path = tempfile.mkdtemp()
    os.chdir(pcs_path)
    commands.init_perun_at(pcs_path, False, {"vcs": {"url": "../", "type": "git"}})

    # Initialize git
    pcs.vcs().init({})

    # Populate repo with commits
    repo = git.Repo(pcs_path)

    # Obtain the default branch name of the repo
    git_default_branch_name = pcs.vcs().get_default_major_version()

    # Create first commit
    file1 = os.path.join(pcs_path, "file1")
    common_kit.touch_file(file1)
    repo.index.add([file1])
    root = repo.index.commit("root")

    # Create second commit
    repo.git.checkout("-b", "develop")
    file2 = os.path.join(pcs_path, "file2")
    common_kit.touch_file(file2)
    repo.index.add([file2])
    middle_head = repo.index.commit("second commit")

    # Create third commit
    repo.git.checkout(git_default_branch_name)
    file3 = os.path.join(pcs_path, "file3")
    common_kit.touch_file(file3)
    repo.index.add([file3])
    repo.index.commit("parallel commit")
    repo.git.merge("--no-ff", "develop")
    current_head = str(repo.head.commit)

    # Populate PCS with profiles
    jobs_dir = pcs.get_job_directory()
    root_profile = test_utils.prepare_profile(jobs_dir, profiles[0], str(root))
    commands.add([root_profile], str(root))
    middle_profile = test_utils.prepare_profile(jobs_dir, profiles[1], str(middle_head))
    commands.add([middle_profile], str(middle_head))
    head_profile = test_utils.prepare_profile(jobs_dir, profiles[2], str(current_head))
    commands.add([head_profile], str(current_head))

    yield pcs

    # clean up the directory
    shutil.rmtree(pcs_path)


@pytest.fixture(scope="function")
def pcs_single_prof(stored_profile_pool):
    """
    * root [file1]
    |
    * second commit [file2] p1
    """
    # Change working dir into the temporary directory
    profiles = stored_profile_pool
    pcs_path = tempfile.mkdtemp()
    os.chdir(pcs_path)
    commands.init_perun_at(pcs_path, False, {"vcs": {"url": "../", "type": "git"}})

    # Initialize git
    pcs.vcs().init({})

    # Populate repo with commits
    repo = git.Repo(pcs_path)

    # Create first commit
    file1 = os.path.join(pcs_path, "file1")
    common_kit.touch_file(file1)
    repo.index.add([file1])

    # Create second commit
    file2 = os.path.join(pcs_path, "file2")
    common_kit.touch_file(file2)
    repo.index.add([file2])
    current_head = repo.index.commit("second commit")

    # Populate PCS with profiles
    jobs_dir = pcs.get_job_directory()
    chead_profile1 = test_utils.prepare_profile(jobs_dir, profiles[1], str(current_head))
    commands.add([chead_profile1], str(current_head))

    # Assert that we have five blobs: 2 for commits and 3 for profiles
    pcs_object_dir = os.path.join(pcs_path, ".perun", "objects")
    number_of_perun_objects = sum(
        len(os.listdir(os.path.join(pcs_object_dir, sub))) for sub in os.listdir(pcs_object_dir)
    )
    assert number_of_perun_objects == 2

    yield pcs

    # clean up the directory
    shutil.rmtree(pcs_path)


@pytest.fixture(scope="function")
def pcs_full(stored_profile_pool):
    """
    * root [file1] p1
    |
    * second commit [file2] p2 p3
    """
    # Change working dir into the temporary directory
    profiles = stored_profile_pool
    pcs_path = tempfile.mkdtemp()
    os.chdir(pcs_path)
    commands.init_perun_at(pcs_path, False, {"vcs": {"url": "../", "type": "git"}})

    # Initialize git
    pcs.vcs().init({})

    # Populate repo with commits
    repo = git.Repo(pcs_path)

    # Create first commit
    file1 = os.path.join(pcs_path, "file1")
    common_kit.touch_file(file1)
    repo.index.add([file1])
    root = repo.index.commit("root")

    # Create second commit
    file2 = os.path.join(pcs_path, "file2")
    common_kit.touch_file(file2)
    repo.index.add([file2])
    current_head = repo.index.commit("second commit")

    # Populate PCS with profiles
    jobs_dir = pcs.get_job_directory()
    root_profile = test_utils.prepare_profile(jobs_dir, profiles[0], str(root))
    commands.add([root_profile], str(root))
    chead_profile1 = test_utils.prepare_profile(jobs_dir, profiles[1], str(current_head))
    chead_profile2 = test_utils.prepare_profile(jobs_dir, profiles[2], str(current_head))
    commands.add([chead_profile1, chead_profile2], str(current_head))

    # Assert that we have five blobs: 2 for commits and 3 for profiles
    pcs_object_dir = os.path.join(pcs_path, ".perun", "objects")
    number_of_perun_objects = sum(
        len(os.listdir(os.path.join(pcs_object_dir, sub))) for sub in os.listdir(pcs_object_dir)
    )
    assert number_of_perun_objects == 5

    yield pcs

    # clean up the directory
    shutil.rmtree(pcs_path)


@pytest.fixture(scope="function")
def pcs_full_no_prof():
    """
    * root [file1]
    |
    * second commit [file2]
    |
    * third commit [file3]
    """
    # Change working dir into the temporary directory
    pcs_path = tempfile.mkdtemp()
    os.chdir(pcs_path)
    commands.init_perun_at(pcs_path, False, {"vcs": {"url": "../", "type": "git"}})

    # Initialize git
    pcs.vcs().init({})

    # Populate repo with commits
    repo = git.Repo(pcs_path)

    # Create first commit
    file1 = os.path.join(pcs_path, "file1")
    common_kit.touch_file(file1)
    repo.index.add([file1])
    repo.index.commit("root")

    # Create second commit
    file2 = os.path.join(pcs_path, "file2")
    common_kit.touch_file(file2)
    repo.index.add([file2])
    repo.index.commit("second commit")

    # Create third commit
    file3 = os.path.join(pcs_path, "file3")
    common_kit.touch_file(file3)
    repo.index.add([file3])
    repo.index.commit("third commit")

    yield pcs

    # clean up the directory
    shutil.rmtree(pcs_path)


@pytest.fixture(scope="function")
def pcs_with_empty_git():
    """
    *
    """
    # Change working dir into the temporary directory
    pcs_path = tempfile.mkdtemp()
    os.chdir(pcs_path)
    commands.init_perun_at(pcs_path, False, {"vcs": {"url": "../", "type": "git"}})

    # Initialize git
    pcs.vcs().init({})

    yield pcs

    # clean up the directory
    shutil.rmtree(pcs_path)


@pytest.fixture(scope="function")
def pcs_with_root():
    """
    * root [file1]
    """
    # Change working dir into the temporary directory
    pcs_path = tempfile.mkdtemp()
    os.chdir(pcs_path)
    commands.init_perun_at(pcs_path, False, {"vcs": {"url": "../", "type": "git"}})

    # Initialize git
    pcs.vcs().init({})

    # Populate repo with commits
    repo = git.Repo(pcs_path)

    # Create first commit
    file1 = os.path.join(pcs_path, "file1")
    common_kit.touch_file(file1)
    repo.index.add([file1])
    repo.index.commit("root")

    yield pcs

    # clean up the directory
    shutil.rmtree(pcs_path)


@pytest.fixture(scope="function")
def pcs_with_svs():
    """
    *
    """
    # Change working dir into the temporary directory
    pcs_path = tempfile.mkdtemp()
    os.chdir(pcs_path)
    commands.init_perun_at(pcs_path, False, {"vcs": {"url": "../", "type": "svs"}})

    # Initialize git
    pcs.vcs().init({})

    yield pcs

    # clean up the directory
    shutil.rmtree(pcs_path)


@pytest.fixture(scope="function")
def pcs_without_vcs():
    """ """
    # Change working dir into the temporary directory
    pcs_path = tempfile.mkdtemp()
    os.chdir(pcs_path)
    commands.init_perun_at(pcs_path, False, {"vcs": {"url": "../", "type": "pvcs"}})

    yield pcs

    # clean up the directory
    shutil.rmtree(pcs_path)


@pytest.fixture(scope="function")
def cleandir():
    """Runs the test in the clean new dir, which is purged afterwards"""
    temp_path = tempfile.mkdtemp()
    os.chdir(temp_path)
    yield
    shutil.rmtree(temp_path)


@pytest.yield_fixture(autouse=True)
def setup():
    """Cleans the caches before each test"""
    # Cleans up the caching of all singleton instances
    for singleton in decorators.registered_singletons:
        singleton.instance = None
    for singleton_with_args in decorators.func_args_cache.values():
        singleton_with_args.clear()

    # Reset the verbosity to release
    log.VERBOSITY = 0
    log.LOGGING = False
    log.CURRENT_INDENT = 0
    log.SUPPRESS_PAGING = True
    log.REDIRECT_STDOUT_IN_PROGRESS = False

    # We disable the metrics by default, since they might slow down tests
    metrics.Metrics.enabled = False
    report.Stats.KnownStatsSet.clear()
    report.Stats.SortedStats = []
    yield
