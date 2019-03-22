import os
import json
import re
import zlib

import perun.logic.store as store
import perun.logic.pcs as pcs
import perun.utils.exceptions as exceptions
import perun.vcs as vcs
import perun.logic.commands as commands


# Match the timestamp format of the profile names
PROFILE_TIMESTAMP_REGEX = re.compile(r"(-?\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2})")


def get_stats_filename_as_source(profile, ignore_timestamp, minor_version=None):
    """Generate stats filename based on the 'source' property of the supplied profile,
    i.e. the stats filename will refer to the name of the profile before it was tracked.

    :param str profile: the profile identification, can be given as tag, sha value,
                        sha-path (path to tracked profile in obj) or source-path
    :param bool ignore_timestamp: if set to True, removes the 'date' component in the source name
    :param str minor_version: representation of the minor version or None for HEAD

    :return str: the generated stats filename (not path!)
    """
    profile_index_entry = _find_profile_entry(profile, minor_version)
    if ignore_timestamp:
        # Remove the timestamp entry in the profile name
        return PROFILE_TIMESTAMP_REGEX.sub("", profile_index_entry.path)
    return profile_index_entry.path


def get_stats_filename_as_sha(profile, minor_version=None):
    """Generate stats filename based on the 'SHA' property of the supplied profile,
    i.e. the stats filename will refer to the name of the profile after its tracking.

    :param str profile: the profile identification, can be given as tag, sha value,
                        sha-path (path to tracked profile in obj) or source-path
    :param str minor_version: representation of the minor version or None for HEAD

    :return str: the generated stats filename (not path!)
    """
    return _find_profile_entry(profile, minor_version).checksum


def get_stats_file_path(stats_filename, minor_version=None, check_existence=False):
    """Create full path for the given minor version and the stats file name.

    Note: the existence of the file is checked only if the corresponding parameter is set to True.
    If set to True and the file does not exist, StatsFileNotFoundException is raised.

    :param str stats_filename: the name of the stats file to generate the path for
    :param str minor_version: the minor version representation or None for HEAD
    :param bool check_existence: the existence of the generated path is checked if set to True

    :return str: the full path to the file under the given minor version
    """
    stats_dir = _touch_minor_stats_directory(minor_version)
    stats_file = os.path.join(stats_dir, os.path.basename(stats_filename.rstrip(os.sep)))
    # Check if the file exists
    if check_existence and os.path.exists(stats_file):
        raise exceptions.StatsFileNotFoundException(stats_file)
    return stats_file


def add_stats(stats_id, stats_content, stats_filename, minor_version=None):
    """ Save some stats represented by an ID into the provided stats filename under a specific
    minor version.

    :param str stats_id: a string that serves as a unique identification of the stored stats
    :param dict stats_content: the stats data to save
    :param str stats_filename: the name of the stats file where the data will be stored
    :param str minor_version: the minor version representation or None for HEAD

    :return str: the path to the stats file containing the stored data
    """

    def add_to_dict(dictionary):
        """ A helper function that stores the stats content in the given dict under the ID

        :param dict dictionary: the dictionary where the content will be stored
        """
        dictionary[stats_id] = stats_content

    stats_file = get_stats_file_path(stats_filename, minor_version)
    _modify_stats_file(stats_file, "wb+", add_to_dict)

    return stats_file


def update_stats(stats_id, extension, stats_filename, minor_version=None):
    """ Updates the stats represented by an ID in the given stats filename under a specific
    minor version. The stats dictionary will be extended by the supplied extension.

    :param str stats_id: a string that serves as a unique identification of the stored stats
    :param dict extension: the dict with the new / updated values
    :param str stats_filename: the name of the stats file where to update the stats
    :param str minor_version: the minor version representation or None for HEAD
    """
    stats_file = get_stats_file_path(stats_filename, minor_version)
    _modify_stats_file(stats_file, "wb+", lambda r: r[stats_id].update(extension))


def delete_stats(stats_id, stats_filename, minor_version=None):
    """ Deletes the stats represented by an ID in the stats filename under a specific
    minor version. Raises StatsFileNotFoundException if the given file does not exist.

    :param str stats_id: a string that serves as a unique identification of the stored stats
    :param str stats_filename: the name of the stats file where to delete the stats
    :param str minor_version: the minor version representation or None for HEAD
    """
    stats_file = get_stats_file_path(stats_filename, minor_version, True)
    _modify_stats_file(stats_file, "wb", lambda r: r.pop(stats_id, []))


def delete_stats_file(stats_filename, minor_version=None):
    """ Deletes the whole stats file with all its content.
    Raises StatsFileNotFoundException if the given file does not exist.

    :param str stats_filename: the name of the stats file to delete
    :param str minor_version: the minor version representation or None for HEAD
    """
    stats_file = get_stats_file_path(stats_filename, minor_version, True)
    os.remove(stats_file)


def get_stats_of(stats_filename, stats_id=None, minor_version=None):
    """ Gets the stats content represented by an ID (or the whole content if stats_id is None)
    from the stats filename under a specific minor version.
    Raises StatsFileNotFoundException if the given file does not exist.

    :param str stats_filename: the name of the stats file where to search for the stats
    :param str stats_id: a string that serves as a unique identification of the stored stats
    :param str minor_version: the minor version representation or None for HEAD

    :return dict: the stats content of the ID (or the whole file) or empty dict in case the
                  ID was not found in the stats file
    """
    # TODO: extract the file finding / existence checking into a function
    stats_file = get_stats_file_path(stats_filename, minor_version, True)

    # Load the whole stats content and filter the ID if present
    with open(stats_file, "rb") as stats_handle:
        if stats_id is None:
            return _load_stats_from(stats_handle)
        return _load_stats_from(stats_handle).get(stats_id, {})


def list_stats_for_minor(minor_version=None):
    """ Returns all the stats files stored under the given minor version.

    :param str minor_version: the minor version representation or None for HEAD

    :return list: all the stats filenames in the minor version
    """
    minor_exists, target_dir = _find_minor_stats_directory(minor_version)
    if minor_exists:
        # We assume that all the files in the minor version stats directory are actually stats
        _, _, files = next(os.walk(target_dir))
        return files
    return []


@commands.lookup_minor_version
def _touch_minor_stats_directory(minor_version):
    """ Touches the stats directories - upper (first byte of the minor version SHA) and lower (the
    rest of the SHA bytes) levels.

    :param str minor_version: the minor version representation or None for HEAD

    :return str: the full path of the minor version directory for stats
    """
    # Obtain path to the directory for the given minor version
    upper_level_dir, lower_level_dir = store.split_object_name(pcs.get_stats_directory(),
                                                               minor_version)
    # Create both directories for storing statistics to the given minor version
    store.touch_dir(upper_level_dir)
    store.touch_dir(lower_level_dir)
    return lower_level_dir


@commands.lookup_minor_version
def _find_minor_stats_directory(minor_version):
    """ Finds the stats directory for the given minor version and checks its existence.

    :param str minor_version: the minor version representation or None for HEAD

    :return tuple: (bool representing the existence of directory, the directory path)
    """
    _, minor_dir = store.split_object_name(pcs.get_stats_directory(), minor_version)
    return os.path.exists(minor_dir), minor_dir


# TODO: make public in store?
def _find_minor_index(minor_version):
    """ Finds the corresponding index for the minor version or raises EntryNotFoundException if
    the index was not found.

    :param str minor_version: the minor version representation or None for HEAD

    :return str: path to the index file
    """
    # Find the index file
    _, index_file = store.split_object_name(pcs.get_object_directory(), minor_version)
    if not os.path.exists(index_file):
        raise exceptions.EntryNotFoundException(index_file)
    return index_file


# TODO: make public in store?
@commands.lookup_minor_version
def _find_profile_entry(profile, minor_version):
    """ Finds the profile entry within the index file of the minor version.

    :param str profile: the profile identification, can be given as tag, sha value,
                        sha-path (path to tracked profile in obj) or source-path
    :param str minor_version: the minor version representation or None for HEAD

    :return IndexEntry: the profile entry from the index file
    """
    minor_index = _find_minor_index(minor_version)

    # If profile is given as tag, obtain the sha-path of the file
    tag_match = store.INDEX_TAG_REGEX.match(profile)
    if tag_match:
        profile = commands.get_nth_profile_of(int(tag_match.group(1)), minor_version)
    # Transform the sha-path (obtained or given) to the sha value
    if not store.is_sha1(profile) and not profile.endswith('.perf'):
        profile = _sha_path_to_sha(profile)

    # Search the minor index for the requested profile
    with open(minor_index, 'rb') as index_handle:
        # The profile can be only sha value or source path now
        if store.is_sha1(profile):
            return store.lookup_entry_within_index(index_handle, lambda x: x.checksum == profile)
        else:
            return store.lookup_entry_within_index(index_handle, lambda x: x.path == profile)


def _load_stats_from(stats_handle):
    """ Loads and unzips the contents of the opened stats file.

    :param file stats_handle: the handle of the stats file

    :return dict: the stats file contents
    """
    try:
        return json.loads(store.read_and_deflate_chunk(stats_handle))
    except (ValueError, zlib.error):
        # Contents either empty or corrupted, init the content to empty dict
        return {}


def _save_stats_to(stats_handle, stats_records):
    """ Saves and zips the stats contents (records) to the file.

    :param file stats_handle: the handle of the stats file
    :param dict stats_records: the contents to save
    """
    compressed = store.pack_content(json.dumps(stats_records, indent=2).encode('utf-8'))
    stats_handle.write(compressed)


def _modify_stats_file(stats_filepath, file_mode, modify_function):
    """ Modifies the contents of the given stats file by the provided modification function

    :param str stats_filepath: the path to the stats file
    :param str file_mode: the file opening mode
    :param function modify_function: function that takes the stats contents as a parameter and
                                     modifies it accordingly
    """
    with open(stats_filepath, file_mode) as stats_handle:
        stats_records = _load_stats_from(stats_handle)
        modify_function(stats_records)
        _save_stats_to(stats_handle, stats_records)


# TODO: make general publicly-accessible version? Like lookup_minor_version but not a decorator
def _lookup_minor_version(minor_version):
    """Looks up the given minor version and checks its existence.

    :param str minor_version: the minor version representation or None for HEAD
    :return str: the minor version representation
    """
    if minor_version is None:
        minor_version = vcs.get_minor_head()
    else:
        vcs.check_minor_version_validity(minor_version)
    return minor_version


# TODO: make public?
def _sha_path_to_sha(sha_path):
    """ Transforms the path of the minor version directory (represented by the SHA value) to the
    actual SHA value as a string.

    :param str sha_path: path to the minor version directory
    :return str: the SHA value of the minor version
    """
    rest, lower_level = os.path.split(sha_path.rstrip(os.sep))
    _, upper_level = os.path.split(rest.rstrip(os.sep))
    return upper_level + lower_level
