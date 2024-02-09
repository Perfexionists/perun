"""This module contains functions for manipulating statistics files (the so called 'stats')

Stats are basically various data or statistics that need to be stored and manipulated by other
modules, collectors, post-processors etc. The 'stats' file can be indirectly linked to a specific
profile by using the profile 'source' or 'checksum' as a template for the name of the stats file.
Or the stats file might be completely unrelated to profiles by using some custom name.

Stats files are located in the .perun/stats directory under a specific minor version since the
statistics are mostly related to some results or profiles acquired in a specific VCS version. For
storing some temporary data that are unrelated to VCS version, use the 'temp' module.

The format of the stats files is as follows:

{
    'some_ID':
    {
        stats data stored by the user
    },

    'another_ID':
    {
        some other stored data
    },

    'yet_another_ID':
    {
        ...
    }
}

where the IDs uniquely represent stored statistics within the stats file and the ID is used to
identify the data that should be manipulated by the functions.

The contents of the stats file are stored in a compressed form to reduce the memory requirements.

"""
from __future__ import annotations

# Standard Imports
from typing import Optional, Iterable, BinaryIO, Callable, Any
import json
import os
import re
import shutil
import zlib

# Third-Party Imports

# Perun Imports
from perun.logic import index, pcs, store
from perun.profile import helpers
from perun.utils import exceptions, log as perun_log
from perun.utils.common import common_kit
from perun.utils.exceptions import SuppressedExceptions
from perun.vcs import vcs_kit

# Match the timestamp format of the profile names
PROFILE_TIMESTAMP_REGEX = re.compile(r"(-?\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2})")

# Default number of displayed records for listing stats objects
DEFAULT_STATS_LIST_TOP = 20


def build_stats_filename_as_profile_source(
    profile: str, ignore_timestamp: bool, minor_version: Optional[str] = None
) -> str:
    """Generate stats filename based on the 'source' property of the supplied profile,
    i.e. the stats filename will refer to the name of the profile before it was tracked.

    :param str profile: the profile identification, can be given as tag, sha value,
                        sha-path (path to tracked profile in obj) or source-name
    :param bool ignore_timestamp: if set to True, removes the 'date' component in the source name
    :param str minor_version: representation of the minor version or None for HEAD

    :return str: the generated stats filename (not path!)
    """
    profile_index_entry = helpers.find_profile_entry(profile, minor_version)
    stats_name = profile_index_entry.path
    if ignore_timestamp:
        # Remove the timestamp entry in the profile name
        stats_name = PROFILE_TIMESTAMP_REGEX.sub("", stats_name)
    if stats_name.endswith(".perf"):
        # Remove the '.perf' suffix
        stats_name = stats_name[:-5]
    return stats_name


def build_stats_filename_as_profile_sha(profile: str, minor_version: Optional[str] = None) -> str:
    """Generate stats filename based on the 'SHA' property of the supplied profile,
    i.e. the stats filename will refer to the name of the profile after its tracking.

    :param str profile: the profile identification, can be given as tag, sha value,
                        sha-path (path to tracked profile in obj) or source-name
    :param str minor_version: representation of the minor version or None for HEAD

    :return str: the generated stats filename (not path!)
    """
    return helpers.find_profile_entry(profile, minor_version).checksum


def get_stats_file_path(
    stats_filename: str,
    minor_version: Optional[str] = None,
    check_existence: bool = False,
    create_dir: bool = False,
) -> str:
    """Create full path for the given minor version and the stats file name.

    Note: the existence of the file is checked only if the corresponding parameter is set to True.
    If set to True and the file does not exist, StatsFileNotFoundException is raised.

    Note: the corresponding minor version directory is created only if 'create_dir' is set to True.
    However, if the minor version is not valid, an exception is thrown.

    :param str stats_filename: the name of the stats file to generate the path for
    :param str minor_version: the minor version representation or None for HEAD
    :param bool check_existence: the existence of the generated path is checked if set to True
    :param bool create_dir: the minor version directory will be created if it does not exist yet

    :return str: the full path to the file under the given minor version
    """
    stats_file = os.path.join(
        find_minor_stats_directory(minor_version)[1],
        os.path.basename(stats_filename.rstrip(os.sep)),
    )
    # Create the minor version directory if requested
    if create_dir:
        _touch_minor_stats_directory(minor_version)
    # Check if the file exists
    if check_existence and not os.path.exists(stats_file):
        raise exceptions.StatsFileNotFoundException(stats_file)
    return stats_file


@vcs_kit.lookup_minor_version
def find_minor_stats_directory(minor_version: str) -> tuple[bool, str]:
    """Finds the stats directory for the given minor version and checks its existence.

    :param str minor_version: the minor version representation or None for HEAD

    :return tuple: (bool representing the existence of directory, the directory path)
    """
    _, minor_dir = store.split_object_name(pcs.get_stats_directory(), minor_version)
    return os.path.exists(minor_dir), minor_dir


def add_stats(
    stats_filename: str,
    stats_ids: list[str],
    stats_contents: list[dict[str, Any]],
    minor_version: Optional[str] = None,
) -> str:
    """Save some stats represented by an ID into the provided stats filename under a specific
    minor version. Creates the stats file if it does not exist yet.

    :param str stats_filename: the name of the stats file where the data will be stored
    :param list of str stats_ids: strings that serve as unique identification of the stored stats
    :param list of dict stats_contents: the stats data to save
    :param str minor_version: the minor version representation or None for HEAD

    :return str: the path to the stats file containing the stored data
    """

    stats_file = get_stats_file_path(stats_filename, minor_version, create_dir=True)
    # append: create the file if necessary, be able to read the whole file and write to the file
    _modify_stats_file(stats_file, stats_ids, stats_contents, _add_to_dict)

    return stats_file


def update_stats(
    stats_filename: str,
    stats_ids: list[str],
    extensions: list[dict[str, Any]],
    minor_version: Optional[str] = None,
) -> None:
    """Updates the stats represented by an ID in the given stats filename under a specific
    minor version. The stats dictionary will be extended by the supplied extensions.

    :param str stats_filename: the name of the stats file where to update the stats
    :param list of str stats_ids: strings that serve as unique identification of the stored stats
    :param list of dict extensions: the dicts with the new / updated values
    :param str minor_version: the minor version representation or None for HEAD
    """
    stats_file = get_stats_file_path(stats_filename, minor_version, create_dir=True)
    _modify_stats_file(stats_file, stats_ids, extensions, _update_or_add_to_dict)


def get_stats_of(
    stats_filename: str,
    stats_ids: Optional[list[str]] = None,
    minor_version: Optional[str] = None,
) -> dict[str, dict[str, Any]]:
    """Gets the stats content represented by an ID (or the whole content if stats_id is None)
    from the stats filename under a specific minor version.
    Raises StatsFileNotFoundException if the given file does not exist.

    :param str stats_filename: the name of the stats file where to search for the stats
    :param list of str stats_ids: strings that serve as unique identification of the stored stats
    :param str minor_version: the minor version representation or None for HEAD

    :return dict: the stats content of the ID (or the whole file) or empty dict in case the
                  ID was not found in the stats file
    """
    stats_file = get_stats_file_path(stats_filename, minor_version, True)

    # Load the whole stats content and filter the ID if present
    with open(stats_file, "rb") as stats_handle:
        stats_content = _load_stats_from(stats_handle)
        if stats_ids is None:
            return stats_content
        # Extract the requested stats from the contents
        return {sid: val for sid, val in stats_content.items() if sid in stats_ids}


def delete_stats(
    stats_filename: str, stats_ids: list[str], minor_version: Optional[str] = None
) -> None:
    """Deletes the stats represented by an ID in the stats filename under a specific
    minor version. Raises StatsFileNotFoundException if the given file does not exist.

    :param str stats_filename: the name of the stats file where to delete the stats
    :param list of str stats_ids: strings that serve as unique identification of the stored stats
    :param str minor_version: the minor version representation or None for HEAD
    """
    stats_file = get_stats_file_path(stats_filename, minor_version, True)
    # We need to construct some dummy 'contents' variable
    _modify_stats_file(
        stats_file,
        stats_ids,
        [{} for _ in range(len(stats_ids))],
        lambda d, sid, _: d.pop(sid, []),
    )


def list_stats_for_minor(minor_version: Optional[str] = None) -> list[tuple[str, Any]]:
    """Returns all the stats files stored under the given minor version.

    :param str minor_version: the minor version representation or None for HEAD

    :return list: all the stats file names in the minor version as tuples (file name, file size)
    """
    minor_exists, target_dir = find_minor_stats_directory(minor_version)
    if minor_exists:
        # We assume that all the files in the minor version stats directory are actually stats
        _, _, files = next(os.walk(target_dir))
        return [(file, os.stat(os.path.join(target_dir, file)).st_size) for file in files]
    return []


def list_stat_versions(from_minor: Optional[str] = None, top: int = 0) -> list[tuple[str, str]]:
    """Returns 'top' minor versions (starting at 'from_minor') that have directories and index
     records in the '.perun/stats'. The minor versions are sorted by date from the most recent.

    :param str from_minor: starting minor version or None for HEAD
    :param int top: the number of versions to return, 0 for unlimited

    :return list: the list of lists [version checksum, version date] sorted by date
    """
    indexed_versions = _load_stats_index()
    # Get the actual length if everything is to be displayed
    top = abs(len(indexed_versions) if top == 0 else top)
    return _slice_versions(indexed_versions, from_minor, top)


def delete_stats_file(
    stats_filename: str,
    minor_version: Optional[str] = None,
    keep_directory: bool = False,
) -> None:
    """Deletes the stats file in the stats directory of the given minor version.
    Raises StatsFileNotFoundException if the given file does not exist.

    :param str stats_filename: the name of the stats file to delete
    :param str minor_version: the minor version representation or None for HEAD
    :param bool keep_directory: do not remove the possibly empty (after the file deletion) minor
                                version directory if set to True
    """
    stats_file = get_stats_file_path(stats_filename, minor_version, True)
    os.remove(stats_file)
    if not keep_directory:
        # Delete the minor version directory if it is empty
        minor_version = minor_version or pcs.vcs().get_minor_head()
        delete_version_dirs([minor_version], True)


def get_latest(
    stats_filename: str,
    stats_ids: Optional[list[str]] = None,
    exclude_self: bool = False,
) -> dict[str, dict[str, Any]]:
    """Fetch the content of the latest stats file named 'stats_filename' according to the
    git versions.

    :param str stats_filename: the name of the stats file
    :param list stats_ids: fetch only the specified parts of the stats file
    :param bool exclude_self: ignore the stats file in the current git version

    :return dict: selected content (IDs) of the stats file, if found
    """
    versions = list_stat_versions()
    if exclude_self and versions[0][0] == pcs.vcs().get_minor_head():
        versions = versions[1:]
    # Traverse all the version directories and try to find it
    for version, _ in versions:
        with SuppressedExceptions(exceptions.StatsFileNotFoundException):
            return get_stats_of(stats_filename, stats_ids, version)
    return {}


def delete_stats_file_across_versions(stats_filename: str, keep_directory: bool = False) -> None:
    """Deletes the stats file across all the minor version directories in stats.

    :param str stats_filename: the name of the stats file to delete
    :param bool keep_directory: do not remove the possibly empty (after the file deletion) minor
                                version directory if set to True
    """
    matches = []
    # Traverse all the version directories and attempt to delete the file
    for version, _ in list_stat_versions():
        # If the file was not found in this version, simply continue
        with SuppressedExceptions(exceptions.StatsFileNotFoundException):
            delete_stats_file(stats_filename, version, True)
            matches.append(version)

    # Make sure we delete only empty version directories where we actually deleted the file
    if not keep_directory:
        delete_version_dirs(matches, True)


def delete_version_dirs(
    minor_versions: list[str], only_empty: bool, keep_directories: bool = False
) -> None:
    """Deletes the given minor version directories in the stats directory.

    Based on the only_empty parameter, it may delete only those which are empty or all of them.

    :param list minor_versions: a list of minor versions whose directories should be deleted
    :param bool only_empty: if set then only those directories in 'minor_versions' which are empty will be deleted
    :param bool keep_directories: do not delete the minor version directories but only their
                                  content if set to True, does nothing if 'only_empty' is also True
    """
    # Deleting only empty directories and keeping the folders at the same time doesn't make sense
    if only_empty and keep_directories:
        return

    removed_versions = []
    for version in minor_versions:
        try:
            version_dir = store.split_object_name(pcs.get_stats_directory(), version)[1]
            if keep_directories:
                # Remove only the directories and files in the version directory
                _, dirs, files = next(os.walk(version_dir))
                _delete_stats_objects(
                    [os.path.join(version_dir, directory) for directory in dirs],
                    [os.path.join(version_dir, file) for file in files],
                )
            else:
                # Delete the whole directory
                if not only_empty:
                    shutil.rmtree(version_dir)
                # Attempt to delete the possibly empty directory
                elif only_empty and not _delete_empty_dir(version_dir):
                    continue
                # Also delete the lower level version directory (the first SHA byte) if empty
                _delete_empty_dir(os.path.split(version_dir)[0])
                removed_versions.append(version)
        except OSError as exc:
            # Failed to delete some object, log and skip
            perun_log.msg_to_file(f"Stats object deletion info: {exc}", 0)

    # Update the index to reflect the removed version directories
    _remove_versions_from_index(removed_versions)


def reset_stats(keep_directories: bool = False) -> None:
    """Clears the whole stats directory and attempts to reset it into the initial state.

    :param bool keep_directories: the empty version directories are kept in the stats directory
    """
    if keep_directories:
        # Synchronize the index to make sure that we delete every minor version
        synchronize_index()
        delete_version_dirs([version for version, _ in list_stat_versions()], False, True)
        clean_stats(keep_empty=True)
    else:
        # No need to keep the version directories, simply recreate the stats directory
        stats_dir = pcs.get_stats_directory()
        shutil.rmtree(stats_dir)
        common_kit.touch_dir(stats_dir)


def clean_stats(keep_custom: bool = False, keep_empty: bool = False) -> None:
    """Cleans the stats directory, that is:
    - synchronizes the internal state of the stats directory, i.e. the index file
    - attempts to delete all distinguishable custom files and directories (some manually created or
      custom objects may not be identified if they have the correct format, e.g. version directory
      that was created manually but has a valid version counterpart in the VCS, manually created
      files in the version directory etc.)
    - deletes all empty version directories in the stats directory

    :param bool keep_custom: the custom objects are kept in the stats directory if set to True
    :param bool keep_empty: the empty version directories are not deleted if set to True
    """
    # First synchronize the index file
    synchronize_index()
    if not keep_custom:
        # Get the custom files and directories in the stats directory
        _, custom = _get_versions_in_stats_directory()
        custom_files, custom_dirs = common_kit.partition_list(custom, os.path.isfile)
        # Use the reversed order to minimize the number of exceptions due to already deleted files
        _delete_stats_objects(reversed(custom_dirs), reversed(custom_files))
    if not keep_empty:
        delete_version_dirs([version for version, _ in list_stat_versions()], True)


def synchronize_index() -> None:
    """Synchronizes the index file with the actual content of the stats' directory. Should be
    needed only after some manual tampering with the directories and files in the stats directory.
    """
    indexed_versions = _load_stats_index()
    stats_versions, _ = _get_versions_in_stats_directory()
    # Delete from index all minor version records that do not have a directory in stats anymore
    indexed_versions = [version for version in indexed_versions if tuple(version) in stats_versions]
    # Add record to index for all versions in stats that do not already have one
    # Make sure the values are sorted by date and are unique by inserting all the records
    _add_versions_to_index(stats_versions + indexed_versions, [])


def _delete_stats_objects(dirs: Iterable[str], files: Iterable[str]) -> None:
    """Deletes stats directories and files, should be used only for deleting the content of
    directories or standalone files, not minor version directories.

    :param iterable dirs: the list of directories (paths) to delete
    :param iterable files: the list of files (paths) to delete
    """
    # Deleting directories first could cause some 'files' to be removed and raising more exceptions
    for idx, group in enumerate([files, dirs]):
        delete_func = shutil.rmtree if idx == 1 else os.remove
        for item in group:
            try:
                # Note: We, ignore this, as MyPy seems to have problem inferring and coping with delete_func type
                delete_func(item)  # type: ignore
            except OSError as exc:
                # Possibly already deleted files or restricted permission etc., log and skip
                perun_log.msg_to_file(f"Stats object deletion error: {exc}", 0)


def _delete_empty_dir(directory_path: str) -> bool:
    """Deletes the directory given by the path if it is empty. If not, then nothing is done.

    :param str directory_path: path to the directory that should be deleted

    :return bool: True if the directory was deleted, False otherwise
    """
    if not os.listdir(directory_path):
        os.rmdir(directory_path)
        return True
    return False


def _add_to_dict(dictionary: dict[str, Any], sid: str, content: dict[str, Any]) -> None:
    """A helper function that stores the stats content in the given dict under the ID

    :param dict dictionary: the dictionary where the content will be stored
    :param str sid: a string that serves as a unique identification of the stored stats
    :param dict content: the stats data to save
    """
    dictionary[sid] = content


def _update_or_add_to_dict(dictionary: dict[str, Any], sid: str, extension: dict[str, Any]) -> None:
    """A helper function that updates the stats content in the given dict under the ID or creates
    the new ID with the 'extension' content if it does not exist

    :param dict dictionary: the dictionary where the content will be stored
    :param str sid: a string that serves as a unique identification of the stored stats
    :param dict extension: the stats data to save
    """
    if sid in dictionary:
        dictionary[sid].update(extension)
    else:
        _add_to_dict(dictionary, sid, extension)


@vcs_kit.lookup_minor_version
def _touch_minor_stats_directory(minor_version: str) -> str:
    """Touches the stats directories - upper (first byte of the minor version SHA) and lower (the
    rest of the SHA bytes) levels.

    :param str minor_version: the minor version representation or None for HEAD

    :return str: the full path of the minor version directory for stats
    """
    # Obtain path to the directory for the given minor version
    _, lower_level_dir = store.split_object_name(pcs.get_stats_directory(), minor_version)
    # Make an entry in the index if the minor version directory does not exist yet
    if not os.path.exists(lower_level_dir):
        _add_versions_to_index([_get_version_info(store.version_path_to_sha(lower_level_dir))])

    # Create the directory for storing statistics in the given minor version
    common_kit.touch_dir(lower_level_dir)
    return lower_level_dir


def _load_stats_from(stats_handle: BinaryIO) -> dict[str, Any]:
    """Loads and unzips the contents of the opened stats file.

    :param file stats_handle: the handle of the stats file

    :return dict: the stats file contents
    """
    try:
        # Make sure we're at the beginning
        stats_handle.seek(0)
        return json.loads(store.read_and_deflate_chunk(stats_handle))
    except (ValueError, zlib.error):
        # Contents either empty or corrupted, init the content to empty dict
        return {}


def _save_stats_to(stats_handle: BinaryIO, stats_records: dict[str, Any]) -> None:
    """Saves and zips the stats contents (records) to the file.

    :param file stats_handle: the handle of the stats file
    :param dict stats_records: the contents to save
    """
    # We need to rewrite the file contents, so move to the beginning and erase everything
    stats_handle.seek(0)
    stats_handle.truncate(0)
    compressed = store.pack_content(json.dumps(stats_records, indent=2).encode("utf-8"))
    stats_handle.write(compressed)


def _modify_stats_file(
    stats_filepath: str,
    stats_ids: list[str],
    stats_contents: list[dict[str, dict[str, Any]]],
    modify_function: Callable[[dict[str, Any], str, dict[str, Any]], None],
) -> None:
    """Modifies the contents of the given stats file by the provided modification function

    :param str stats_filepath: the path to the stats file
    :param list of str stats_ids: identifications of the stats block that are being modified
    :param list of dict stats_contents: the data to modify (add, update, ...)
    :param function modify_function: function that takes the stats contents as a parameter and modifies it accordingly
    """
    with open(stats_filepath, "a+b") as stats_handle:
        stats_records = _load_stats_from(stats_handle)
        for idx in range(min(len(stats_ids), len(stats_contents))):
            modify_function(stats_records, stats_ids[idx], stats_contents[idx])
        _save_stats_to(stats_handle, stats_records)


def _get_version_candidates(minor_checksum: str, minor_date: str) -> list[str]:
    """Obtains successor minor versions that have the same date as the given minor version.

    :param str minor_checksum: the minor version checksum
    :param str minor_date: the date of the minor version

    :return list: list of successor versions in form of checksums
    """
    candidates = []
    # Ignore some unexpected git corruption or the end of minor version history
    with SuppressedExceptions(exceptions.VersionControlSystemException, StopIteration):
        # Start iterating the minor versions at the supplied version
        from_iter = pcs.vcs().walk_minor_versions(minor_checksum)
        # However, the first generator result is the version itself, skip it
        next(from_iter)
        successor = pcs.vcs().get_minor_version_info(next(from_iter).checksum)
        while successor.date == minor_date:
            candidates.append(successor.checksum)
            successor = pcs.vcs().get_minor_version_info(next(from_iter).checksum)
    return candidates


def _get_version_info(minor_version: Optional[str]) -> tuple[str, str]:
    """Resolves the minor version and returns its checksum and date. An exception
    VersionControlSystemException is raised if the version is invalid.

    :param str minor_version: the minor version representation

    :return tuple (str, str): the minor version details (checksum, date)
    """
    pcs.vcs().check_minor_version_validity(minor_version)
    minor_version_info = pcs.vcs().get_minor_version_info(minor_version)
    return minor_version_info.checksum, minor_version_info.date


def _add_versions_to_index(
    minor_versions: list[tuple[str, str]],
    index_stats: Optional[list[tuple[str, str]]] = None,
) -> None:
    """Adds the minor versions records to the stats index file.

    :param list minor_versions: list of minor versions (checksum, date) to add
    :param list index_stats: the content of the index file - is loaded from the file if not provided
    """
    index_stats = _load_stats_index() if index_stats is None else index_stats
    for checksum, date in minor_versions:
        # Find the correct location for inserting the new minor record, avoid duplicates
        insert_pos = _find_nearest_version(index_stats, checksum, date)
        if insert_pos == len(index_stats) or index_stats[insert_pos] != (
            checksum,
            date,
        ):
            index_stats.insert(insert_pos, (checksum, date))
    index.save_custom_index(pcs.get_stats_index(), index_stats)


def _remove_versions_from_index(minor_versions: list[str]) -> None:
    """Removes minor versions from the index file.

    :param list minor_versions: list of minor versions (checksums) to delete
    """
    index_stats = [
        [checksum, date] for checksum, date in _load_stats_index() if checksum not in minor_versions
    ]
    index.save_custom_index(pcs.get_stats_index(), index_stats)


def _find_nearest_version(
    versions: list[tuple[str, str]], minor_checksum: str, minor_date: str
) -> int:
    """Searches the 'versions' list in order to find a minor version record that is closest to the
    provided minor version in terms of VCS order.

    Thus, either the exact record or the nearest successor of the exact minor version is found.

    :param list versions: a list of minor versions in form of tuple (checksum, date)
    :param str minor_checksum: the minor version checksum
    :param str minor_date: the date of the minor version

    :return int: the position of the nearest minor version in the 'versions' list
    """
    # Obtain the minor version and check the validity
    candidates = _get_version_candidates(minor_checksum, minor_date)
    # Traverse the versions list and try to find either the version record or its next successor
    for record_pos, (stat_checksum, stat_date) in enumerate(versions):
        # The records are sorted by date - if dates are equal, then git ordering is used
        if (
            minor_checksum == stat_checksum
            or stat_date < minor_date
            or (stat_date == minor_date and stat_checksum in candidates)
        ):
            return record_pos
    # No result found, the exact version is not there and it has no successor
    return len(versions)


def _slice_versions(
    versions: list[tuple[str, str]], from_version: Optional[str], top: int
) -> list[tuple[str, str]]:
    """Slice the given versions list based on the starting minor version and number of 'top'
    requested version records.

    :param list versions: the list of versions to slice
    :param str from_version: the minor version to start at
    :param int top: number of version records to take

    :return list: the versions list sliced accordingly to the parameters
    """
    try:
        # If not provided, the default start is at the HEAD
        if from_version is None:
            from_version = pcs.vcs().get_minor_head()
        from_checksum, from_date = _get_version_info(from_version)
        # The list may not contain the exact version, try to find the closest one
        slice_location = _find_nearest_version(versions, from_checksum, from_date)
        return versions[slice_location : slice_location + top]
    except exceptions.VersionControlSystemException:
        # Start from the beginning in case of some trouble with version lookup
        return versions[:top]


def _get_versions_in_stats_directory() -> tuple[list[tuple[str, str]], list[str]]:
    """Returns a list of minor versions that have a directory in the '.perun/stats' and a list
    of custom directories or files that were not created by the stats interface.

    :return tuple: list of minor versions (checksum, date), list of custom directories and files
    """

    def dirs_generator(
        directory: str,
        custom_list: list[str],
        filter_func: Optional[Callable[[str], Any]] = None,
    ) -> Iterable[str]:
        """Generator of directories contained within the 'directory'. Files or objects not passing
        the filter function are appended to the custom list.

        :param str directory: path of the base directory to scan for other directories
        :param list custom_list: list for custom objects that are not valid directories
        :param function filter_func: optional function that can filter the traversed directories

        :return generator: generator object that provides the valid directories
        """
        for item in os.listdir(directory):
            item = os.path.join(directory, item)
            # Filter out objects that are not directories or do not pass the filtering function
            if not os.path.isdir(item) or (filter_func is not None and not filter_func(item)):
                custom_list.append(item)
            # The rest should be valid directories
            else:
                yield item

    # List all the upper and lower directories
    versions = []
    custom: list[str] = []
    stats_dir, stats_idx = pcs.get_stats_directory(), pcs.get_stats_index()
    # The upper level of directories should represent the first SHA byte
    for upper in list(dirs_generator(stats_dir, custom, os.listdir)):
        # The lower level represents the rest of the SHA
        lower_list = list(dirs_generator(upper, custom))
        # If there are no lower level directories, then the upper directory is custom
        if not lower_list:
            custom.append(upper)
        # Check all the lower level objects
        temp_versions, temp_custom = [], []
        for lower in lower_list:
            try:
                # Construct the minor version from SHA and resolve it
                temp_versions.append(_get_version_info(store.version_path_to_sha(lower)))
                # Check the contents of the minor version stats, directories should not be allowed
                # Do not check the files as we do not really have a way to distinguish custom ones
                temp_custom.extend(list(dirs_generator(lower, [])))
            except exceptions.VersionControlSystemException:
                temp_custom.append(lower)
        # If all the objects in the upper directory are custom, delete the upper
        # Otherwise delete only the lower level objects
        if not temp_versions:
            custom.append(upper)
        else:
            versions.extend(temp_versions)
            custom.extend(temp_custom)

    # Remove the .index file from the custom list if it is present
    if stats_idx in custom:
        custom.remove(stats_idx)

    return versions, custom


def _load_stats_index() -> Any:
    """Wraps the loader of custom index files so that it would return the expected default value.

    TODO: There should be validation that stats is in right format

    :return list: list of records in the index file or empty list for empty index file
    """
    stats_index = index.load_custom_index(pcs.get_stats_index())
    return stats_index if stats_index else []
