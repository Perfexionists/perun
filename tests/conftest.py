"""Shared fixtures for the testing of functionality of Perun commands."""

import glob
import os
import shutil
import subprocess
import tempfile

import git

import perun.utils.helpers as helpers
import perun.utils.log as log
import perun.logic.pcs as pcs
import perun.logic.store as store
import perun.cli as cli
import pytest

import perun.logic.commands as commands
import perun.utils.decorators as decorators
import perun.utils.streams as streams
import perun.vcs as vcs

import tests.testing.utils as test_utils

__author__ = 'Tomas Fiedor'


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
    target_dir = os.path.join(script_dir, 'sources', 'collect_memory')
    target_src_path = os.path.join(target_dir, 'memory_collect_test.c')

    # Compile the testing stuff with debugging information set
    subprocess.check_output(
        ['gcc', '--std=c99', '-g', target_src_path, '-o', 'mct'], cwd=target_dir
    )
    target_bin_path = os.path.join(target_dir, 'mct')
    assert 'mct' in list(os.listdir(target_dir))

    yield [target_bin_path], '', [''], ['memory'], []

    # Remove the testing stuff
    os.remove(os.path.join(target_dir, 'mct'))


@pytest.fixture(scope="session")
def memory_collect_no_debug_job():
    """
    Returns:
        tuple: ('bin', '', [''], 'memory', [])
    """
    # First compile the stuff, so we know it will work
    script_dir = os.path.split(__file__)[0]
    target_dir = os.path.join(script_dir, 'sources', 'collect_memory')
    target_src_path = os.path.join(target_dir, 'memory_collect_test.c')

    # Compile the testing stuff with debugging information set
    subprocess.check_output(
        ['gcc', '--std=c99', target_src_path, '-o', 'mct-no-dbg'], cwd=target_dir
    )
    target_bin_path = os.path.join(target_dir, 'mct-no-dbg')
    assert 'mct-no-dbg' in list(os.listdir(target_dir))

    yield [target_bin_path], '', [''], ['memory'], []

    # Remove the testing stuff
    os.remove(os.path.join(target_dir, 'mct-no-dbg'))


@pytest.fixture(scope="session")
def complexity_collect_job():
    """


    Returns:
        tuple: 'bin', '', [''], 'memory', [], {}
    """
    # Load the configuration from the job file
    script_dir = os.path.split(__file__)[0]
    source_dir = os.path.join(script_dir, 'sources', 'collect_complexity')
    target_dir = os.path.join(source_dir, 'target')
    job_config_file = os.path.join(source_dir, 'job.yml')
    job_config = streams.safely_load_yaml_from_file(job_config_file)

    # Change the target dir to this location
    assert 'target_dir' in job_config.keys()
    job_config['target_dir'] = target_dir

    yield [target_dir], '', [''], ['complexity'], [], {'collector_params': {
        'complexity': job_config
    }}

    # Remove target testing directory
    shutil.rmtree(target_dir)


@pytest.fixture(scope="session")
def trace_collect_job():
    """


    Returns:
        tuple: 'bin', '', [''], 'trace', [], {}
    """
    # Load the configuration from the job file
    script_dir = os.path.split(__file__)[0]
    source_dir = os.path.join(script_dir, 'sources', 'collect_trace')
    target_dir = source_dir
    job_config_file = os.path.join(source_dir, 'job.yml')
    job_config = streams.safely_load_yaml_from_file(job_config_file)

    yield [target_dir + '/tst'], '', [''], ['trace'], [], {'collector_params': {
        'trace': job_config
    }}

    # Remove trace collect scripts generated at testing
    [os.remove(filename) for filename in glob.glob(source_dir + "/*.stp")]


def all_profiles_in(directory, sort=False):
    """Helper function that generates stream of (sorted) profile paths in specified directory

    Arguments:
        directory(str): the name (not path!) of the profile directory
        sort(bool): flag used to lexicographically sort profiles found in the directory

    Returns:
        generator: stream of profile paths located in the given directory
    """
    # Build the directory path and list of all profiles in it
    pool_path = os.path.join(os.path.split(__file__)[0], 'profiles', directory)
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
    yield list(filter(lambda p: 'err' not in p, all_profiles_in("to_add_profiles", True)))


@pytest.fixture(scope="session")
def error_profile_pool():
    """
    Returns:
        list: list with profiles that contains some kind of error
    """
    yield list(filter(lambda p: 'err' in p, all_profiles_in("to_add_profiles", True)))


@pytest.fixture(scope="session")
def stored_profile_pool():
    """
    Returns:
        list: list of stored profiles in the pcs_full
    """
    profiles = list(all_profiles_in("full_profiles", True))
    assert len(profiles) == 3
    return profiles


def get_loaded_profiles(profile_type):
    """
    Arguments:
        profile_type(str): type of the profile we are looking for

    Returns:
        generator: stream of profiles of the given type
    """
    for valid_profile in filter(lambda p: 'err' not in p, all_profiles_in("to_add_profiles", True)):
        loaded_profile = store.load_profile_from_file(valid_profile, is_raw_profile=True)
        if loaded_profile['header']['type'] == profile_type:
            yield loaded_profile


@pytest.fixture(scope="function")
def memory_profiles():
    """
    Returns:
        generator: generator of fully loaded memory profiles as dictionaries
    """
    yield get_loaded_profiles('memory')


def load_all_profiles_in(directory):
    """Generates stream of loaded (i.e. dictionaries) profiles in the specified directory.

    Arguments:
        directory(str): the name (not path!) of the profile directory

    Returns:
        generator: stream of loaded profiles as tuple (profile_name, dictionary)
    """
    for profile in list(all_profiles_in(directory)):
        yield (profile, store.load_profile_from_file(profile, True))


@pytest.fixture(scope="function")
def query_profiles():
    """
    Returns:
        generator: generator of fully loaded query profiles as tuple (profile_name, dictionary)
    """
    yield list(load_all_profiles_in("query_profiles"))


@pytest.fixture(scope="function")
def postprocess_profiles():
    """
    Returns:
        generator: generator of fully loaded postprocess profiles as tuple
                   (profile_name, dictionary)
    """
    yield load_all_profiles_in("postprocess_profiles")


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
    """
    pool_path = os.path.join(os.path.split(__file__)[0], 'profiles', 'degradation_profiles')
    profiles = [
        os.path.join(pool_path, 'linear_base.perf'),
        os.path.join(pool_path, 'linear_base_degradated.perf'),
        os.path.join(pool_path, 'quad_base.perf')
    ]
    # Change working dir into the temporary directory
    pcs_path = tempfile.mkdtemp()
    os.chdir(pcs_path)
    commands.init_perun_at(pcs_path, False, {'vcs': {'url': '../', 'type': 'git'}})

    # Initialize git
    vcs.init({})

    # Populate repo with commits
    repo = git.Repo(pcs_path)

    # Create first commit
    file1 = os.path.join(pcs_path, "file1")
    helpers.touch_file(file1)
    repo.index.add([file1])
    root = repo.index.commit("root")

    # Create second commit
    repo.git.checkout('-b', 'develop')
    file2 = os.path.join(pcs_path, "file2")
    helpers.touch_file(file2)
    repo.index.add([file2])
    middle_head = repo.index.commit("second commit")

    # Create third commit
    repo.git.checkout('master')
    file3 = os.path.join(pcs_path, "file3")
    helpers.touch_file(file3)
    repo.index.add([file3])
    repo.index.commit("parallel commit")
    repo.git.merge('--no-ff', 'develop')
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
def pcs_full(stored_profile_pool):
    # Change working dir into the temporary directory
    profiles = stored_profile_pool
    pcs_path = tempfile.mkdtemp()
    os.chdir(pcs_path)
    commands.init_perun_at(pcs_path, False, {'vcs': {'url': '../', 'type': 'git'}})

    # Initialize git
    vcs.init({})

    # Populate repo with commits
    repo = git.Repo(pcs_path)

    # Create first commit
    file1 = os.path.join(pcs_path, "file1")
    helpers.touch_file(file1)
    repo.index.add([file1])
    root = repo.index.commit("root")

    # Create second commit
    file2 = os.path.join(pcs_path, "file2")
    helpers.touch_file(file2)
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
def pcs_with_more_commits():
    """
    """
    # Change working dir into the temporary directory
    pcs_path = tempfile.mkdtemp()
    os.chdir(pcs_path)
    commands.init_perun_at(pcs_path, False, {'vcs': {'url': '../', 'type': 'git'}})

    # Initialize git
    vcs.init({})

    # Populate repo with commits
    repo = git.Repo(pcs_path)

    # Create first commit
    file1 = os.path.join(pcs_path, "file1")
    helpers.touch_file(file1)
    repo.index.add([file1])
    repo.index.commit("root")

    # Create second commit
    file2 = os.path.join(pcs_path, "file2")
    helpers.touch_file(file2)
    repo.index.add([file2])
    repo.index.commit("second commit")

    # Create third commit
    file3 = os.path.join(pcs_path, "file3")
    helpers.touch_file(file3)
    repo.index.add([file3])
    repo.index.commit("third commit")

    yield pcs

    # clean up the directory
    shutil.rmtree(pcs_path)


@pytest.fixture(scope="function")
def pcs_with_empty_git():
    """
    """
    # Change working dir into the temporary directory
    pcs_path = tempfile.mkdtemp()
    os.chdir(pcs_path)
    commands.init_perun_at(pcs_path, False, {'vcs': {'url': '../', 'type': 'git'}})

    # Initialize git
    vcs.init({})

    yield pcs

    # clean up the directory
    shutil.rmtree(pcs_path)


@pytest.fixture(scope="function")
def pcs_with_git_root_commit():
    """
    """
    # Change working dir into the temporary directory
    pcs_path = tempfile.mkdtemp()
    os.chdir(pcs_path)
    commands.init_perun_at(pcs_path, False, {'vcs': {'url': '../', 'type': 'git'}})

    # Initialize git
    vcs.init({})

    # Populate repo with commits
    repo = git.Repo(pcs_path)

    # Create first commit
    file1 = os.path.join(pcs_path, "file1")
    helpers.touch_file(file1)
    repo.index.add([file1])
    repo.index.commit("root")

    yield pcs

    # clean up the directory
    shutil.rmtree(pcs_path)


@pytest.fixture(scope="function")
def pcs_without_vcs():
    """
    """
    # Change working dir into the temporary directory
    pcs_path = tempfile.mkdtemp()
    os.chdir(pcs_path)
    commands.init_perun_at(pcs_path, False, {'vcs': {'url': '../', 'type': 'pvcs'}})

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
    yield
