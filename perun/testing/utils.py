from __future__ import annotations

# Standard Imports
from typing import Iterable, Callable, BinaryIO, Any, TYPE_CHECKING
import os
import shutil

# Third-Party Imports

# Perun Imports
from perun.logic import index, store
from perun.utils import decorators, streams

if TYPE_CHECKING:
    from perun.logic.index import BasicIndexEntry
    from perun.profile.factory import Profile


def load_profilename(prof_directory: str, prof_filename: str) -> str:
    """Helper function for getting name of profile

    :param prof_directory: directory, where profile is
    :param prof_filename: name of the profile
    """
    pool_path = os.path.join(
        os.path.split(__file__)[0], "..", "..", "tests", "profiles", prof_directory
    )
    return os.path.join(pool_path, prof_filename)


@decorators.singleton_with_args
def load_profile(prof_directory: str, prof_filename: str) -> Profile:
    """Helper function for loading raw profile from test pool

    :param prof_directory: directory, where profile is
    :param prof_filename: name of the profile
    """
    # We fuck the check here
    return store.load_profile_from_file(
        load_profilename(prof_directory, prof_filename),
        is_raw_profile=True,
        unsafe_load=True,
    )


def index_filter(file: str) -> bool:
    """Index filtering function

    :param str file: name of the file
    :return: true if the file is not index
    """
    return file != ".index"


def populate_repo_with_untracked_profiles(pcs_path: str, untracked_profiles: list[str]) -> None:
    """
    Populates the jobs directory in the repo by untracked profiles

    :param str pcs_path: path to PCS
    :param list untracked_profiles: list of untracked profiles to be added to repo
    """
    jobs_dir = os.path.join(pcs_path, "jobs")
    for valid_profile in untracked_profiles:
        shutil.copy2(valid_profile, jobs_dir)


def prepare_profile(dest_dir: str, profile: str, origin: str) -> str:
    """
    :param str dest_dir: destination of the prepared profile
    :param str profile: name of the profile that is going to be stored in pending jobs
    :param str origin: origin minor version for the given profile
    """
    # Copy to jobs and prepare origin for the current version
    shutil.copy2(profile, dest_dir)

    # Prepare origin for the current version
    copied_filename = os.path.join(dest_dir, os.path.split(profile)[-1])
    # We skip the check if copied_filename exists, it will fuck the tests if it somehow does not
    copied_profile = store.load_profile_from_file(
        copied_filename, is_raw_profile=True, unsafe_load=True
    )
    copied_profile["origin"] = origin
    streams.store_json(copied_profile.serialize(), copied_filename)
    shutil.copystat(profile, copied_filename)
    return copied_filename


def exists_profile_in_index_such_that(
    index_handle: BinaryIO, pred: Callable[[BasicIndexEntry], bool]
) -> bool:
    """Helper assert to check, if there exists any profile in index such that pred holds.

    :param file index_handle: handle for the index
    :param lambda pred: predicate over the index entry
    """
    for entry in index.walk_index(index_handle):
        if pred(entry):
            return True
    return False


def open_index(pcs_path: str, minor_version: str) -> BinaryIO:
    """Helper function for opening handle of the index

    This encapsulates obtaining the full path to the given index

    :param str pcs_path: path to the pcs
    :param str minor_version: sha minor version representation
    """
    assert store.is_sha1(minor_version)
    object_dir_path = os.path.join(pcs_path, "objects")

    _, minor_version_index = store.split_object_name(object_dir_path, minor_version)
    return open(minor_version_index, "rb+")


def count_contents_on_path(path: str) -> tuple[int, int]:
    """Helper function for counting the contents of the path

    :param str path: path to the director which we will list
    :return: (int, int), (file number, dir number) on path
    """
    file_number = 0
    dir_number = 0
    for _, dirs, files in os.walk(path):
        for __ in files:
            file_number += 1
        for __ in dirs:
            dir_number += 1
    return file_number, dir_number


def compare_results(expected: float, actual: float, eps: float = 0.0001) -> None:
    """Compare two float values with eps tolerance.

    :param float expected: the expected result value
    :param float actual: the actual result value
    :param float eps: the tolerance value
    """
    assert abs(abs(expected) - abs(actual)) < eps


def generate_models_by_uid(
    profile: Profile, value: str, uid_sequence: list[str], key: str = "model"
) -> Iterable[list[dict[str, Any]]]:
    """Provides computed models results for each uid in the specified uid sequence.

    :param Profile profile: the whole profile with 'models' results
    :param str value: the specification of value of given key for matching models
    :param list uid_sequence: list of uid values to search for
    :param str key: the key for matching models
    :return: stream of lists with models dictionaries according to uid sequence
    """
    models = profile["profile"]["models"]
    for uid in uid_sequence:
        yield [m for m in models if m["uid"] == uid and m[key] == value]
