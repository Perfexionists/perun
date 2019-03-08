"""Store module contains set of functions for working with directories and repositories.

Store is a collection of helper functions that can be used to pack content, compute checksums,
or load and store into the directories or filenames.
"""

import binascii
import re
import os
import string
import struct
import zlib

import perun.utils.timestamps as timestamps
import perun.utils.log as perun_log
import perun.utils.helpers as helpers

from perun.utils.helpers import LINE_PARSING_REGEX
from perun.utils.structs import PerformanceChange, DegradationInfo
from perun.utils.exceptions import EntryNotFoundException, NotPerunRepositoryException, \
    MalformedIndexFileException

import demandimport
with demandimport.enabled():
    import hashlib

__author__ = 'Tomas Fiedor'


INDEX_TAG_REGEX = re.compile(r"^(\d+)@i$")
INDEX_TAG_RANGE_REGEX = re.compile(r"^(\d+)@i-(\d+)@i$")
PENDING_TAG_REGEX = re.compile(r"^(\d+)@p$")
PENDING_TAG_RANGE_REGEX = re.compile(r"^(\d+)@p-(\d+)@p$")

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
    def __init__(self, time, checksum, path, offset):
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
        :param int index_version: version of the opened index
        :return: one read BasicIndexEntry
        """
        file_offset = index_handle.tell()
        file_time = timestamps.timestamp_to_str(timestamps.read_timestamp_from_file(index_handle))
        file_sha = binascii.hexlify(index_handle.read(20)).decode('utf-8')
        file_path, byte = "", read_char_from_handle(index_handle)
        while byte != '\0':
            file_path += byte
            byte = read_char_from_handle(index_handle)
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

def touch_file(touched_filename, times=None):
    """
    Corresponding implementation of touch inside python.
    Courtesy of:
    http://stackoverflow.com/questions/1158076/implement-touch-using-python

    :param str touched_filename: filename that will be touched
    :param time times: access times of the file
    """
    with open(touched_filename, 'a'):
        os.utime(touched_filename, times)


def touch_dir(touched_dir):
    """
    Touches directory, i.e. if it exists it does nothing and
    if the directory does not exist, then it creates it.

    :param str touched_dir: path that will be touched
    """
    if not os.path.exists(touched_dir):
        os.mkdir(touched_dir)


def touch_dir_range(touched_dir_start, touched_dir_end):
    """Iterates through the range of the subdirs between start and end touching each one of the dir

    E.g. for the following:
    touched_dir_start = '/a/b', touched_dir_end = '/a/b/c/d/e'
    following will be touched: /a/b, /a/b/c, ..., /a/b/c/d/e

    :param str touched_dir_start: base case of the touched dirs
    :param str touched_dir_end: end case of the touched dirs
    """
    for subdir in path_to_subpaths(touched_dir_end):
        if subdir.startswith(touched_dir_start):
            touch_dir(subdir)


def path_to_subpaths(path):
    """Breaks path to all the subpaths, i.e. all of the prefixes of the given path.

    >>> path_to_subpaths('/dir/subdir/subsubdir')
    ['/dir', '/dir/subdir', '/dir/subdir/subsubdir']

    :param str path: path separated by os.sep separator
    :returns list: list of subpaths
    """
    components = path.split(os.sep)
    return [os.sep + components[0]] + \
           [os.sep.join(components[:till]) for till in range(2, len(components) + 1)]


def locate_perun_dir_on(path):
    """Locates the nearest perun directory

    Locates the nearest perun directory starting from the @p path. It walks all of the
    subpaths sorted by their lenght and checks if .perun directory exists there.

    :param str path: starting point of the perun dir search
    :returns str: path to perun dir or "" if the path is not underneath some underlying perun
        control
    """
    # convert path to subpaths and reverse the list so deepest subpaths are traversed first
    lookup_paths = path_to_subpaths(path)[::-1]

    for tested_path in lookup_paths:
        if os.path.isdir(tested_path) and '.perun' in os.listdir(tested_path):
            return tested_path
    raise NotPerunRepositoryException(path)


def compute_checksum(content):
    """Compute the checksum of the content using the SHA-1 algorithm

    :param bytes content: content we are computing checksum for
    :returns str: 40-character SHA-1 checksum of the content
    """
    return hashlib.sha1(content).hexdigest()


def is_sha1(checksum):
    """
    :param str checksum: hexa string
    :returns bool: true if the checksum is sha1 checksum
    """
    return len(checksum) == 40 and all(c in string.hexdigits for c in checksum)


def pack_content(content):
    """Pack the given content with packing algorithm.

    Uses the zlib compression algorithm, to deflate the content.

    :param bytes content: content we are packing
    :returns str: packed content
    """
    return zlib.compress(content)


def peek_profile_type(profile_name):
    """Retrieves from the binary file the type of the profile from the header.

    Peeks inside the binary file of the profile_name and returns the type of the
    profile, without reading it whole.

    :param str profile_name: filename of the profile
    :returns str: type of the profile
    """
    with open(profile_name, 'rb') as profile_handle:
        profile_chunk = read_and_deflate_chunk(profile_handle, helpers.READ_CHUNK_SIZE)
        prefix, profile_type, *_ = profile_chunk.split(" ")

        # Return that the stored profile is malformed
        if prefix != 'profile' or profile_type not in helpers.SUPPORTED_PROFILE_TYPES:
            return helpers.PROFILE_MALFORMED
        else:
            return profile_type


def read_and_deflate_chunk(file_handle, chunk_size=-1):
    """
    :param file file_handle: opened file handle
    :param int chunk_size: size of read chunk or -1 if whole file should be read
    :returns str: deflated chunk or whole file
    """
    if chunk_size == -1:
        packed_content = file_handle.read()
    else:
        packed_content = file_handle.read(chunk_size)

    decompressor = zlib.decompressobj()
    return decompressor.decompress(packed_content).decode('utf-8')


def split_object_name(base_dir, object_name, object_ext=""):
    """
    :param str base_dir: base directory for the object_name
    :param str object_name: sha-1 string representing the object (possibly with extension)
    :param str object_ext: additional extension of the created file
    :returns (str, str): full path for directory and full path for file
    """
    object_dir, object_file = object_name[:2], object_name[2:]
    object_dir_full_path = os.path.join(base_dir, object_dir)
    object_file_full_path = os.path.join(object_dir_full_path, object_file)

    return object_dir_full_path, object_file_full_path + object_ext


def add_loose_object_to_dir(base_dir, object_name, object_content):
    """
    :param path base_dir: path to the base directory
    :param str object_name: sha-1 string representing the object (possibly with extension)
    :param bytes object_content: contents of the packed object
    """
    # Break the sha1 representation to base dir (first byte) and rest of the file
    object_dir_full_path, object_file_full_path = split_object_name(base_dir, object_name)

    # Create the dir
    touch_dir(object_dir_full_path)

    # Write the content of the object
    # Note: That in some universe, there may become some collision, but in reality it should not
    if not os.path.exists(object_file_full_path):
        with open(object_file_full_path, 'wb') as object_handle:
            object_handle.write(object_content)


def read_int_from_handle(file_handle):
    """Helper function for reading one integer from handle

    :param file file_handle: read file
    :returns int: one integer
    """
    return struct.unpack('i', file_handle.read(4))[0]


def read_char_from_handle(file_handle):
    """Helper function for reading one char from handle

    :param file file_handle: read file
    :returns char: one read char
    """
    return struct.unpack('c', file_handle.read(1))[0].decode('utf-8')


def read_number_of_entries_from_handle(index_handle):
    """Helper function for reading number of entries in the handle.

    :param file index_handle: filehandle with index
    """
    current_position = index_handle.tell()
    index_handle.seek(0)
    index_handle.read(4)
    read_int_from_handle(index_handle)
    number_of_entries = read_int_from_handle(index_handle)
    index_handle.seek(current_position)
    return number_of_entries


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
    if magic_bytes != helpers.INDEX_MAGIC_PREFIX:
        raise MalformedIndexFileException("read blob is not an index file")

    index_version = read_int_from_handle(index_handle)
    if index_version != helpers.INDEX_VERSION:
        raise MalformedIndexFileException("read index file is in format of different index version"
                                          " (read index file = {}".format(index_version) +
                                          ", supported = {})".format(helpers.INDEX_VERSION))

    number_of_objects = read_int_from_handle(index_handle)
    loaded_objects = 0

    while index_handle.tell() + 24 < last_position and loaded_objects < number_of_objects:
        entry = BasicIndexEntry.read_from(index_handle, index_version)
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
    index_version = read_int_from_handle(index_handle)
    number_of_entries = read_int_from_handle(index_handle)

    print("{}, index version {} with {} entries\n".format(
        index_prefix, index_version, number_of_entries
    ))

    for entry in walk_index(index_handle):
        print(str(entry))


def get_profile_list_for_minor(base_dir, minor_version):
    """Read the list of entries corresponding to the minor version from its index.

    :param str base_dir: base directory of the models
    :param str minor_version: representation of minor version
    :returns list: list of IndexEntries
    """
    _, minor_index_file = split_object_name(base_dir, minor_version)

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
    _, minor_index_file = split_object_name(base_dir, minor_version)

    if os.path.exists(minor_index_file):
        profile_numbers_per_type = {
            profile_type: 0 for profile_type in helpers.SUPPORTED_PROFILE_TYPES
        }

        # Fixme: Remove the peek_profile_type dependency if possible
        with open(minor_index_file, 'rb') as index_handle:
            # Read the overall
            index_handle.seek(helpers.INDEX_NUMBER_OF_ENTRIES_OFFSET)
            profile_numbers_per_type['all'] = read_int_from_handle(index_handle)

            # Check the types of the entry
            for entry in walk_index(index_handle):
                _, entry_file = split_object_name(base_dir, entry.checksum)
                entry_profile_type = peek_profile_type(entry_file)
                profile_numbers_per_type[entry_profile_type] += 1
            return profile_numbers_per_type
    else:
        return {'all': 0}


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
        touch_file(index_path)

        # create the index
        with open(index_path, 'wb') as index_handle:
            index_handle.write(helpers.INDEX_MAGIC_PREFIX)
            index_handle.write(struct.pack('i', helpers.INDEX_VERSION))
            index_handle.write(struct.pack('i', 0))


def modify_number_of_entries_in_index(index_handle, modify):
    """Helper function of inplace modification of number of entries in index

    :param file index_handle: handle of the opened index
    :param function modify: function that will modify the value of number of entries
    """
    index_handle.seek(helpers.INDEX_NUMBER_OF_ENTRIES_OFFSET)
    number_of_entries = read_int_from_handle(index_handle)
    index_handle.seek(helpers.INDEX_NUMBER_OF_ENTRIES_OFFSET)
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


def register_in_index(base_dir, minor_version, registered_file, registered_file_checksum):
    """Registers file in the index corresponding to the minor_version

    If the index for the minor_version does not exist, then it is touched and initialized
    with empty prefix. Then the entry is added to the file.

    :param str base_dir: base directory of the minor version
    :param str minor_version: sha-1 representation of the minor version of vcs (like e.g. commit)
    :param path registered_file: filename that is registered
    :param str registered_file_checksum: sha-1 representation fo the registered file
    """
    # Create the directory and index (if it does not exist)
    minor_dir, minor_index_file = split_object_name(base_dir, minor_version)
    touch_dir(minor_dir)
    touch_index(minor_index_file)

    modification_stamp = timestamps.timestamp_to_str(os.stat(registered_file).st_mtime)
    entry_name = os.path.split(registered_file)[-1]
    entry = BasicIndexEntry(modification_stamp, registered_file_checksum, entry_name, -1)
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
    _, minor_version_index = split_object_name(base_dir, minor_version)

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
                if is_sha1(removed_file):
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
        index_handle.seek(helpers.INDEX_NUMBER_OF_ENTRIES_OFFSET)
        index_handle.write(struct.pack('i', len(all_entries) - len(removed_entries)))

        # For each entry remove from the index, starting from the greatest offset
        for entry in all_entries:
            if entry in removed_entries:
                continue
            entry.write_to(index_handle)

        index_handle.truncate()


def save_degradation_list_for(base_dir, minor_version, degradation_list):
    """Saves the given degradation list to a minor version storage

    This converts the list of degradation records to a storage-able format. Moreover,
    this loads all of the already stored degradations. For each tuple of the change
    location and change type, this saves only one change record.

    :param str base_dir: base directory, where the degradations will be stored
    :param str minor_version: minor version for which we are storing the degradations
    :param degradation_list:
    :return:
    """
    already_saved_changes = load_degradation_list_for(base_dir, minor_version)

    list_of_registered_changes = dict()
    already_saved_changes.extend(degradation_list)
    for deg_info, cmdstr, source in already_saved_changes:
        info_string = " ".join([
            deg_info.to_storage_record(),
            source,
            cmdstr
        ])
        uid = (deg_info.location, deg_info.type, cmdstr)
        list_of_registered_changes[uid] = info_string

    # Sort the changes
    to_be_stored_changes = sorted(list(list_of_registered_changes.values()))

    # Store the changes in the file
    minor_dir, minor_storage_file = split_object_name(base_dir, minor_version, ".changes")
    touch_dir(minor_dir)
    touch_file(minor_storage_file)
    with open(minor_storage_file, 'w') as write_handle:
        write_handle.write("\n".join(to_be_stored_changes))


def parse_changelog_line(line):
    """Parses one changelog record into the triple of degradation info, command string and minor.

    :param str line: input line from one change log
    :return: triple (degradation info, command string, minor version)
    """
    tokens = LINE_PARSING_REGEX.match(line)
    deg_info = DegradationInfo(
        PerformanceChange[tokens.group('result')],
        tokens.group('type'),
        tokens.group('location'),
        tokens.group('from'),
        tokens.group('to'),
        tokens.group('drate'),
        tokens.group('ctype'),
        float(tokens.group('crate'))
    )
    return deg_info, tokens.group('cmdstr'), tokens.group('minor')


def load_degradation_list_for(base_dir, minor_version):
    """Loads a list of degradations stored for the minor version.

    This opens a file in the .perun/objects directory in the minor version subdirectory with the
    extension ".changes". The file is basically a log of degradation records separated by
    white spaces in ascii coding.

    :param str base_dir: directory to the storage of the objects
    :param str minor_version:
    :return: list of triples (DegradationInfo, command string, minor version source)
    """
    minor_dir, minor_storage_file = split_object_name(base_dir, minor_version, ".changes")
    touch_dir(minor_dir)
    touch_file(minor_storage_file)
    with open(minor_storage_file, 'r') as read_handle:
        lines = read_handle.readlines()

    degradation_list = []
    for line in lines:
        parsed_triple = parse_changelog_line(line.strip())
        degradation_list.append(parsed_triple)
    return degradation_list
