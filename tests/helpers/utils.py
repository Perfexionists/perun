import os
import shutil

import perun.logic.store as store
import perun.utils.streams as streams
import perun.logic.index as index

__author__ = 'Tomas Fiedor'


def profile_filter(generator, rule, return_type='prof'):
    """Finds concrete profile by the rule in profile generator.

    Arguments:
        generator(generator): stream of profiles as tuple: (name, dict)
        rule(str): string to search in the name

    Returns:
        Profile: first profile with name containing the rule
    """
    # Loop the generator and test the rule
    for profile in generator:
        if rule in profile[0]:
            if return_type == 'prof':
                return profile[1]
            elif return_type == 'name':
                return profile[0]
            else:
                return profile


def index_filter(file):
    """Index filtering function

    :param str file: name of the file
    :return: true if the file is not index
    """
    return file != '.index'


def populate_repo_with_untracked_profiles(pcs_path, untracked_profiles):
    """
    Populates the jobs directory in the repo by untracked profiles

    Arguments:
        pcs_path(str): path to PCS
        untracked_profiles(list): list of untracked profiles to be added to repo
    """
    jobs_dir = os.path.join(pcs_path, 'jobs')
    for valid_profile in untracked_profiles:
        shutil.copy2(valid_profile, jobs_dir)


def prepare_profile(dest_dir, profile, origin):
    """
    Arguments:
        dest_dir(str): destination of the prepared profile
        profile(str): name of the profile that is going to be stored in pending jobs
        origin(str): origin minor version for the given profile
    """
    # Copy to jobs and prepare origin for the current version
    shutil.copy2(profile, dest_dir)

    # Prepare origin for the current version
    copied_filename = os.path.join(dest_dir, os.path.split(profile)[-1])
    copied_profile = store.load_profile_from_file(copied_filename, is_raw_profile=True)
    copied_profile['origin'] = origin
    streams.store_json(copied_profile.serialize(), copied_filename)
    shutil.copystat(profile, copied_filename)
    return copied_filename


def exists_profile_in_index_such_that(index_handle, pred):
    """Helper assert to check, if there exists any profile in index such that pred holds.

    Arguments:
        index_handle(file): handle for the index
        pred(lambda): predicate over the index entry
    """
    for entry in index.walk_index(index_handle):
        if pred(entry):
            return True
    return False


def open_index(pcs_path, minor_version):
    """Helper function for opening handle of the index

    This encapsulates obtaining the full path to the given index

    Arguments:
        pcs_path(str): path to the pcs
        minor_version(str): sha minor version representation
    """
    assert store.is_sha1(minor_version)
    object_dir_path = os.path.join(pcs_path, 'objects')

    _, minor_version_index = store.split_object_name(object_dir_path, minor_version)
    return open(minor_version_index, 'rb+')


def count_contents_on_path(path):
    """Helper function for counting the contents of the path

    Arguments:
        path(str): path to the director which we will list

    Returns:
        (int, int): (file number, dir number) on path
    """
    file_number = 0
    dir_number = 0
    for _, dirs, files in os.walk(path):
        for __ in files:
            file_number += 1
        for __ in dirs:
            dir_number += 1
    return file_number, dir_number


def compare_results(expected, actual, eps=0.0001):
    """Compare two float values with eps tolerance.

    Arguments:
        expected(float): the expected result value
        actual(float): the actual result value
        eps(float): the tolerance value
    Returns:
        None
    """
    assert abs(abs(expected) - abs(actual)) < eps


def generate_models_by_uid(profile, value, uid_sequence, key='model'):
    """Provides computed models results for each uid in the specified uid sequence.

    Arguments:
        profile(Profile): the whole profile with 'models' results
        value(str): the specification of value of given key for matching models
        uid_sequence(list of str): list of uid values to search for
        key(str): the key for matching models
    Returns:
        generator: stream of lists with models dictionaries according to uid sequence
    """
    models = profile['profile']['models']
    for uid in uid_sequence:
        yield [m for m in models if m['uid'] == uid and m[key] == value]