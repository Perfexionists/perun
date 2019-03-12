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
    :param str minor_version: representation of the minor version

    :return str: the generated stats filename (not path!)
    """
    profile_index_entry = _find_profile_entry(profile, minor_version)
    if ignore_timestamp:
        return PROFILE_TIMESTAMP_REGEX.sub("", profile_index_entry.path)
    return profile_index_entry.path


def get_stats_filename_as_sha(profile, minor_version=None):
    """Generate stats filename based on the 'SHA' property of the supplied profile,
    i.e. the stats filename will refer to the name of the profile after its tracking.

    :param str profile: the profile identification, can be given as tag, sha value,
                        sha-path (path to tracked profile in obj) or source-path
    :param bool ignore_timestamp: if set to True, removes the 'date' component in the source name
    :param str minor_version: representation of the minor version

    :return str: the generated stats filename (not path!)
    """
    profile_index_entry = _find_profile_entry(profile, minor_version)
    return profile_index_entry.checksum


def get_stats_file_path(stats_filename, minor_version=None):
    target_dir = _touch_minor_stats_directory(minor_version)
    stats_filename = os.path.basename(stats_filename.rstrip(os.sep))
    return os.path.join(target_dir, stats_filename)


def add_stats(stats_id, stats_content, stats_filename, minor_version=None):

    def add_to_dict(dictionary):
        dictionary[stats_id] = stats_content

    target_file = get_stats_file_path(stats_filename, minor_version)
    _modify_stats_file(target_file, "wb+", add_to_dict)

    return target_file


def update_stats(stats_id, extension, stats_filename, minor_version=None):
    target_file = get_stats_file_path(stats_filename, minor_version)

    _modify_stats_file(target_file, "wb+", lambda r: r[stats_id].update(extension))


def delete_stats(stats_id, stats_filename, minor_version=None):
    target_file = get_stats_file_path(stats_filename, minor_version)

    if os.path.exists(target_file):
        raise exceptions.StatsFileNotFoundException(target_file)

    _modify_stats_file(target_file, "wb", lambda r: r.pop(stats_id, []))


def delete_stats_file(stats_filename, minor_version=None):
    target_file = get_stats_file_path(stats_filename, minor_version)
    if not os.path.exists(target_file):
        raise exceptions.StatsFileNotFoundException(target_file)
    os.remove(target_file)


def get_stats_of(stats_filename, stats_id=None, minor_version=None):
    target_file = get_stats_file_path(stats_filename, minor_version)

    if not os.path.exists(target_file):
        raise exceptions.StatsFileNotFoundException(target_file)

    with open(target_file, "rb") as stats_handle:
        if stats_id is None:
            return _load_stats_from(stats_handle)
        return _load_stats_from(stats_handle).get(stats_id, None)


def list_stats_for_minor(minor_version=None):
    minor_exists, target_dir = _find_minor_stats_directory(minor_version)
    if minor_exists:
        _, _, files = next(os.walk(target_dir))
        return files
    return []


@commands.lookup_minor_version
def _touch_minor_stats_directory(minor_version):
    # Obtain path to the directory for the given minor version
    upper_level_dir, lower_level_dir = store.split_object_name(pcs.get_stats_directory(),
                                                               minor_version)
    # Create both directories for storing statistics to the given minor version
    store.touch_dir(upper_level_dir)
    store.touch_dir(lower_level_dir)
    return lower_level_dir


@commands.lookup_minor_version
def _find_minor_stats_directory(minor_version):
    _, minor_dir = store.split_object_name(pcs.get_stats_directory(), minor_version)
    return os.path.exists(minor_dir), minor_dir


# TODO: make public in store?
def _find_minor_index(minor_version):
    # Find the index file
    _, index_file = store.split_object_name(pcs.get_object_directory(), minor_version)
    if not os.path.exists(index_file):
        raise exceptions.EntryNotFoundException(index_file)
    return index_file


# TODO: make public in store?
@commands.lookup_minor_version
def _find_profile_entry(profile, minor_version):
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
    try:
        return json.loads(store.read_and_deflate_chunk(stats_handle))
    except (ValueError, zlib.error):
        # Contents either empty or corrupted, init the content to empty dict
        return {}


def _save_stats_to(stats_handle, stats_records):
    compressed = store.pack_content(json.dumps(stats_records, indent=2).encode('utf-8'))
    stats_handle.write(compressed)


def _modify_stats_file(status_filepath, file_mode, modify_function):
    with open(status_filepath, file_mode) as stats_handle:
        stats_records = _load_stats_from(stats_handle)
        modify_function(stats_records)
        _save_stats_to(stats_handle, stats_records)


# TODO: make general publicly-accessible version? Like lookup_minor_version but not decorator
def _lookup_minor_version(minor_version):
    if minor_version is None:
        minor_version = vcs.get_minor_head()
    else:
        vcs.check_minor_version_validity(minor_version)
    return minor_version


# TODO: make public?
def _sha_path_to_sha(sha_path):
    rest, lower_level = os.path.split(sha_path.rstrip(os.sep))
    _, upper_level = os.path.split(rest.rstrip(os.sep))
    return upper_level + lower_level
