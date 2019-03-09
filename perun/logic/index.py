"""Collection of methods for manipulation with Index.

This contains both helper constants, enums, and function, and most of all all definitions
of various version of index entries.
"""

import os
import binascii
import struct

import perun.utils.timestamps as timestamps
import perun.utils.log as perun_log
import perun.utils.helpers as helpers
import perun.logic.store as store

from perun.utils.exceptions import EntryNotFoundException, MalformedIndexFileException

from enum import Enum

__author__ = 'Tomas Fiedor'

# List of current versions of format and magic constants
INDEX_ENTRIES_START_OFFSET = 12
INDEX_NUMBER_OF_ENTRIES_OFFSET = 8
INDEX_MAGIC_PREFIX = b'pidx'
# Index Version 1.0 Slow Lorris
INDEX_VERSION = 1

IndexVersion = Enum(
    'IndexVersion',
    'SlowLorris FastSloth'
)

class BasicIndexEntry(object):
    """Class representation of one index entry

    This corresponds to the basic version of the index called the Slow Lorris.
    The issue with this entry is that it is very minimalistic, and requires loading profiles
    for status and log.

    :ivar time: modification timestamp of the entry profile
    :ivar checksum: checksum of the object, i.e. the path to its real content
    :ivar path: the original path to the profile
    :ivar offset: offset of the entry within the index
    """
    version = IndexVersion.SlowLorris

    def __init__(self, time, checksum, path, offset, *_):
        """
        :param time: modification timestamp of the entry profile
        :param checksum: checksum of the object, i.e. the path to its real content
        :param path: the original path to the profile
        :param offset: offset of the entry within the index
        """
        self.time = time
        self.checksum = checksum
        self.path = path
        self.offset = offset

    def __eq__(self, other):
        """Compares two IndexEntries simply by checking the equality of its internal dictionaries

        :param other: other object to be compared
        :return: whether this object is the same as other
        """
        return self.__dict__ == other.__dict__

    @classmethod
    def read_from(cls, index_handle, index_version):
        """Reads the entry from the index handle

        This is basic version, which stores only the information of timestamp, sha and path of the
        file.

        TODO: add check for index version

        :param File index_handle: opened index handle
        :param IndexVersion index_version: version of the opened index
        :return: one read BasicIndexEntry
        """
        if BasicIndexEntry.version.value < index_version.value:
            perun_log.error("internal error: called read_from() for BasicIndexEntry")
        file_offset = index_handle.tell()
        file_time = timestamps.timestamp_to_str(timestamps.read_timestamp_from_file(index_handle))
        file_sha = binascii.hexlify(index_handle.read(20)).decode('utf-8')
        file_path, byte = "", store.read_char_from_handle(index_handle)
        while byte != '\0':
            file_path += byte
            byte = store.read_char_from_handle(index_handle)
        return BasicIndexEntry(file_time, file_sha, file_path, file_offset)

    def write_to(self, index_handle):
        """Writes entry at current location in the index_handle

        :param file index_handle: file handle of the index
        """
        timestamps.write_timestamp(index_handle, timestamps.str_to_timestamp(self.time))
        index_handle.write(bytearray.fromhex(self.checksum))
        index_handle.write(bytes(self.path, 'utf-8'))
        index_handle.write(struct.pack('B', 0))

    def __str__(self):
        """Converts the entry to one string representation

        :return:  string representation of the entry
        """
        return " @{3} {2} -> {1} ({0})".format(
            self.time,
            self.checksum,
            self.path,
            self.offset
        )


def walk_index(index_handle):
    """Iterator through index entries

    Reads the beginning of the file, verifying the version and type of the index. Then it iterates
    through all of the index entries and returns them as a BasicIndexEntry structure for further
    processing.

    :param file index_handle: handle to file containing index
    :returns BasicIndexEntry: Index entry named tuple
    """
    # Get end of file position
    index_handle.seek(0, 2)
    last_position = index_handle.tell()

    # Move to the begging of the handle
    index_handle.seek(0)
    magic_bytes = index_handle.read(4)
    if magic_bytes != INDEX_MAGIC_PREFIX:
        raise MalformedIndexFileException("read blob is not an index file")

    index_version = store.read_int_from_handle(index_handle)
    if index_version != INDEX_VERSION:
        raise MalformedIndexFileException("read index file is in format of different index version"
                                          " (read index file = {}".format(index_version) +
                                          ", supported = {})".format(INDEX_VERSION))

    number_of_objects = store.read_int_from_handle(index_handle)
    loaded_objects = 0

    while index_handle.tell() + 24 < last_position and loaded_objects < number_of_objects:
        entry = BasicIndexEntry.read_from(index_handle, IndexVersion(index_version))
        loaded_objects += 1
        yield entry

    if loaded_objects != number_of_objects:
        perun_log.error("fatal: "
                        "malformed index file: too many or too few objects registered in index")


def print_index(index_file):
    """Helper function for printing the contents of the index

    :param str index_file: path to the index file
    """
    with open(index_file, 'rb') as index_handle:
        print_index_from_handle(index_handle)


def print_index_from_handle(index_handle):
    """Helper funciton for printing the contents of index inside the handle.

    :param file index_handle: opened file handle
    """
    index_prefix = index_handle.read(4)
    index_version = store.read_int_from_handle(index_handle)
    number_of_entries = store.read_int_from_handle(index_handle)

    print("{}, index version {} with {} entries\n".format(
        index_prefix, index_version, number_of_entries
    ))

    for entry in walk_index(index_handle):
        print(str(entry))


def touch_index(index_path):
    """Initializes and creates the index if it does not exists

    The Version 1 index is of following form:
      -  4B magic prefix 'pidx' (perun index) for quick identification of the file
      -  4B version number (currently 1)
      -  4B number of index entries

    Followed by the entries of profiles of form:
      -  4B time of the file creation
      - 20B SHA-1 representation of the object
      -  ?B Variable length path
      -  ?B zero byte padding

    :param str index_path: path to the index
    """
    if not os.path.exists(index_path):
        store.touch_file(index_path)

        # create the index
        with open(index_path, 'wb') as index_handle:
            index_handle.write(INDEX_MAGIC_PREFIX)
            index_handle.write(struct.pack('i', INDEX_VERSION))
            index_handle.write(struct.pack('i', 0))


def modify_number_of_entries_in_index(index_handle, modify):
    """Helper function of inplace modification of number of entries in index

    :param file index_handle: handle of the opened index
    :param function modify: function that will modify the value of number of entries
    """
    index_handle.seek(INDEX_NUMBER_OF_ENTRIES_OFFSET)
    number_of_entries = store.read_int_from_handle(index_handle)
    index_handle.seek(INDEX_NUMBER_OF_ENTRIES_OFFSET)
    index_handle.write(struct.pack('i', modify(number_of_entries)))


def write_entry_to_index(index_file, file_entry):
    """Writes the file_entry to its appropriate position within the index.

    Given the file entry, writes the entry within the file, moving everything by the given offset
    and then incrementing the number of entries within the index.

    :param str index_file: path to the index file
    :param BasicIndexEntry file_entry: index entry that will be written to the file
    """
    with open(index_file, 'rb+') as index_handle:
        # Lookup the position of the registered file within the index
        if file_entry.offset == -1:
            try:
                predicate = (
                    lambda entry: entry.path > file_entry.path or (
                        entry.path == file_entry.path and entry.time >= file_entry.time
                    )
                )
                looked_up_entry = lookup_entry_within_index(index_handle, predicate)

                # If there is an exact match, we do not add the entry to the index
                if looked_up_entry.path == file_entry.path and \
                                looked_up_entry.time == file_entry.time:
                    perun_log.msg_to_stdout("{0.path} ({0.time}) already registered in {1}".format(
                        file_entry, index_file
                    ), 0)
                    return
                offset_in_file = looked_up_entry.offset
            except EntryNotFoundException:
                # Move to end of the file and set the offset to the end of the file
                index_handle.seek(0, 2)
                offset_in_file = index_handle.tell()
        else:
            offset_in_file = file_entry.offset

        # Modify the number of entries in index and return to position
        modify_number_of_entries_in_index(index_handle, lambda x: x + 1)
        index_handle.seek(offset_in_file)

        # Read previous entries to buffer and return back to the position
        buffer = index_handle.read()
        index_handle.seek(offset_in_file)

        # Write the index_file entry to index
        file_entry.write_to(index_handle)

        # Write the stuff stored in buffer
        index_handle.write(buffer)


def lookup_entry_within_index(index_handle, predicate):
    """Looks up the first entry within index that satisfies the predicate

    :param file index_handle: file handle of the index
    :param function predicate: predicate that tests given entry in index BasicIndexEntry -> bool
    :returns BasicIndexEntry: index entry satisfying the given predicate
    """
    for entry in walk_index(index_handle):
        if predicate(entry):
            return entry

    raise EntryNotFoundException(predicate.__name__)


def lookup_all_entries_within_index(index_handle, predicate):
    """
    :param file index_handle: file handle of the index
    :param function predicate: predicate that tests given entry in index BasicIndexEntry -> bool

    :returns [BasicIndexEntry]: list of index entries satisfying given predicate
    """
    return [entry for entry in walk_index(index_handle) if predicate(entry)]


def register_in_index(base_dir, minor_version, registered_file, registered_file_checksum, profile):
    """Registers file in the index corresponding to the minor_version

    If the index for the minor_version does not exist, then it is touched and initialized
    with empty prefix. Then the entry is added to the file.

    :param str base_dir: base directory of the minor version
    :param str minor_version: sha-1 representation of the minor version of vcs (like e.g. commit)
    :param path registered_file: filename that is registered
    :param str registered_file_checksum: sha-1 representation fo the registered file
    :param dict profile: profile to be registered
    """
    # Create the directory and index (if it does not exist)
    minor_dir, minor_index_file = store.split_object_name(base_dir, minor_version)
    store.touch_dir(minor_dir)
    touch_index(minor_index_file)

    modification_stamp = timestamps.timestamp_to_str(os.stat(registered_file).st_mtime)
    entry_name = os.path.split(registered_file)[-1]
    entry = BasicIndexEntry(modification_stamp, registered_file_checksum, entry_name, -1, profile)
    write_entry_to_index(minor_index_file, entry)

    reg_rel_path = os.path.relpath(registered_file)
    perun_log.info("'{}' successfully registered in minor version index".format(reg_rel_path))


def remove_from_index(base_dir, minor_version, removed_file_generator, remove_all=False):
    """Removes stream of removed files from the index.

    Iterates through all of the removed files, and removes their partial/full occurence from the
    index. The index is walked just once.

    :param str base_dir: base directory of the minor version
    :param str minor_version: sha-1 representation of the minor version of vcs (like e..g commit)
    :param generator removed_file_generator: generator of filenames, that will be removed from the
        tracking
    :param bool remove_all: true if all of the entries should be removed
    """
    # Get directory and index
    _, minor_version_index = store.split_object_name(base_dir, minor_version)

    if not os.path.exists(minor_version_index):
        raise EntryNotFoundException(minor_version_index)

    # Lookup all entries for the given function
    with open(minor_version_index, 'rb+') as index_handle:
        # Gather all of the entries from the index
        all_entries = [entry for entry in walk_index(index_handle)]
        all_entries.sort(key=lambda unsorted_entry: unsorted_entry.offset)
        removed_entries = []

        for removed_file in removed_file_generator:
            def lookup_function(entry):
                """Helper lookup function according to the type of the removed file"""
                if store.is_sha1(removed_file):
                    return entry.checksum == removed_file
                else:
                    return entry.path == removed_file

            if remove_all:
                removed_entries.append(
                    lookup_all_entries_within_index(index_handle, lookup_function)
                )
            else:
                removed_entries.extend([lookup_entry_within_index(index_handle, lookup_function)])
            perun_log.info("deregistered: {}".format(removed_file))

        # Update number of entries
        index_handle.seek(INDEX_NUMBER_OF_ENTRIES_OFFSET)
        index_handle.write(struct.pack('i', len(all_entries) - len(removed_entries)))

        # For each entry remove from the index, starting from the greatest offset
        for entry in all_entries:
            if entry in removed_entries:
                continue
            entry.write_to(index_handle)

        index_handle.truncate()


def get_profile_list_for_minor(base_dir, minor_version):
    """Read the list of entries corresponding to the minor version from its index.

    :param str base_dir: base directory of the models
    :param str minor_version: representation of minor version
    :returns list: list of IndexEntries
    """
    _, minor_index_file = store.split_object_name(base_dir, minor_version)

    if os.path.exists(minor_index_file):
        with open(minor_index_file, 'rb') as index_handle:
            return [entry for entry in walk_index(index_handle)]
    else:
        return []


def get_profile_number_for_minor(base_dir, minor_version):
    """
    :param str base_dir: base directory of the profiles
    :param str minor_version: representation of minor version
    :returns dict: dictionary of number of profiles inside the index of the minor_version of types
    """
    _, minor_index_file = store.split_object_name(base_dir, minor_version)

    if os.path.exists(minor_index_file):
        profile_numbers_per_type = {
            profile_type: 0 for profile_type in helpers.SUPPORTED_PROFILE_TYPES
            }

        # Fixme: Remove the peek_profile_type dependency if possible
        with open(minor_index_file, 'rb') as index_handle:
            # Read the overall
            index_handle.seek(INDEX_NUMBER_OF_ENTRIES_OFFSET)
            profile_numbers_per_type['all'] = store.read_int_from_handle(index_handle)

            # Check the types of the entry
            for entry in walk_index(index_handle):
                _, entry_file = store.split_object_name(base_dir, entry.checksum)
                entry_profile_type = store.peek_profile_type(entry_file)
                profile_numbers_per_type[entry_profile_type] += 1
            return profile_numbers_per_type
    else:
        return {'all': 0}

