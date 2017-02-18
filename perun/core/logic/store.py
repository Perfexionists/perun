"""Store module contains set of functions for working with directories and repositories.

Store is a collection of helper functions that can be used to pack content, compute checksums,
or load and store into the directories or filenames.
"""

import binascii
import hashlib
import os
import struct
import zlib

import perun.utils.decorators as decorators
import perun.utils.log as perun_log

from perun.utils.helpers import IndexEntry, INDEX_VERSION, INDEX_MAGIC_PREFIX

__author__ = 'Tomas Fiedor'


def touch_file(touched_filename, times=None):
    """
    Corresponding implementation of touch inside python.
    Courtesy of:
    http://stackoverflow.com/questions/1158076/implement-touch-using-python

    Arguments:
        touched_filename(str): filename that will be touched
        times(time): access times of the file
    """
    with open(touched_filename, 'a'):
        os.utime(touched_filename, times)


def touch_dir(touched_dir):
    """
    Touches directory, i.e. if it exists it does nothing and
    if the directory does not exist, then it creates it.

    Arguments:
        touched_dir(str): path that will be touched
    """
    if not os.path.exists(touched_dir):
        os.mkdir(touched_dir)


def path_to_subpath(path):
    """Breaks path to all the subpaths, i.e. all of the prefixes of the given path.

    >>> path_to_subpath('/dir/subdir/subsubdir')
    ['/dir', '/dir/subdir', '/dir/subdir/subsubdir']

    Arguments:
        path(str): path separated by os.sep separator

    Returns:
        list: list of subpaths
    """
    assert os.path.isdir(path)
    components = path.split(os.sep)
    return [os.sep + components[0]] + \
           [os.sep.join(components[:till]) for till in range(2, len(components) + 1)]


def compute_checksum(content):
    """Compute the checksum of the content using the SHA-1 algorithm

    Arguments:
        content(bytes): content we are computing checksum for

    Returns:
        str: 40-character SHA-1 checksum of the content
    """
    return hashlib.sha1(content).hexdigest()


def pack_content(content):
    """Pack the given content with packing algorithm.

    Uses the zlib compression algorithm, to deflate the content.

    Arguments:
        content(bytes): content we are packing

    Returns:
        str: packed content
    """
    return zlib.compress(content)


def split_object_name(base_dir, object_name):
    """
    Arguments:
        base_dir(str): base directory for the object_name
        object_name(str): sha-1 string representing the object (possibly with extension)

    Returns:
        (str, str): full path for directory and full path for file
    """
    object_dir, object_file = object_name[:2], object_name[2:]
    object_dir_full_path = os.path.join(base_dir, object_dir)
    object_file_full_path = os.path.join(object_dir_full_path, object_file)

    return object_dir_full_path, object_file_full_path


def add_loose_object_to_dir(base_dir, object_name, object_content):
    """
    Arguments:
        base_dir(path): path to the base directory
        object_name(str): sha-1 string representing the object (possibly with extension)
        object_content(bytes): contents of the packed object
    """
    # Break the sha1 representation to base dir (first byte) and rest of the file
    object_dir_full_path, object_file_full_path = split_object_name(base_dir, object_name)

    # Create the dir
    touch_dir(object_dir_full_path)

    # Write the content of the object
    if os.path.exists(object_file_full_path):
        perun_log.warn("{} is already added for tracking".format(object_file_full_path))

    with open(object_file_full_path, 'wb') as object_handle:
        object_handle.write(object_content)


def remove_loose_object_from_dir(base_dir, object_name):
    """
    Arguments:
        base_dir(path): path to the base directory
        object_name(str): sha-1 string representing the object base_dir (possibly with extension)
    """
    # Break the sha1 representation to base dir (first byte) and rest of the file
    object_dir_full_path, object_file_full_path = split_object_name(base_dir, object_name)

    # Remove file form the tracking
    if os.path.exists(object_file_full_path):
        os.remove(object_file_full_path)
    else:
        perun_log.warn("{} does not exist within .perun".format(object_file_full_path))

    # Remove directory from trakcing
    if not os.listdir(object_dir_full_path):
        os.rmdir(object_dir_full_path)


def read_int_from_handle(file_handle):
    """Helper function for reading one integer from handle

    Arguments:
        file_handle(file): read file

    Returns:
        int: one integer
    """
    return struct.unpack('i', file_handle.read(4))[0]


def read_char_from_handle(file_handle):
    """Helper function for reading one char from handle

    Arguments:
        file_handle(file): read file

    Returns:
        char: one read char
    """
    return struct.unpack('c', file_handle.read(1))[0].decode('utf-8')


@decorators.assume_version(INDEX_VERSION, 1)
def walk_index(index_handle):
    """Iterator through index entries

    Reads the beginning of the file, verifying the version and type of the index. Then it iterates
    through all of the index entries and returns them as a IndexEntry structure for further
    processing.

    Arguments:
        index_handle(file): handle to file containing index

    Returns:
        IndexEntry: Index entry named tuple
    """
    # Get end of file position
    index_handle.seek(0, 2)
    last_position = index_handle.tell()

    # Move to the begging of the handle
    index_handle.seek(0)
    magic_bytes = index_handle.read(4)
    assert magic_bytes == INDEX_MAGIC_PREFIX

    index_version = read_int_from_handle(index_handle)
    assert index_version == INDEX_VERSION

    number_of_objects = read_int_from_handle(index_handle)
    loaded_objects = 0

    def read_entry():
        """
        Returns:
            IndexEntry: one read index entry
        """
        # Rather nasty hack, but nothing better comes to my mind currently
        if index_handle.tell() + 24 >= last_position:
            return ''

        file_offset = index_handle.tell()
        file_time = index_handle.read(4)
        file_sha = binascii.hexlify(index_handle.read(20)).decode('utf-8')
        file_path, byte = "", read_char_from_handle(index_handle)
        while byte != '\0':
            file_path += byte
            byte = read_char_from_handle(index_handle)
        return IndexEntry(file_time, file_sha, file_path, file_offset)

    for entry in iter(read_entry, ''):
        print(entry)
        loaded_objects += 1
        if loaded_objects > number_of_objects:
            perun_log.error("fatal: malformed index file")
        yield entry

    if loaded_objects != number_of_objects:
        perun_log.error("fatal: malformed index file")


@decorators.assume_version(INDEX_VERSION, 1)
def print_index(index_file):
    """Helper function for printing the contents of the index

    Arguments:
        index_file(str): path to the index file
    """
    with open(index_file, 'rb') as index_handle:
        index_prefix = index_handle.read(4)
        index_version = read_int_from_handle(index_handle)
        number_of_entries = read_int_from_handle(index_handle)

        print("{}, index version {} with {} entries\n".format(
            index_prefix, index_version, number_of_entries
        ))

        for entry in walk_index(index_handle):
            print(" @{3} {2} -> {1} ({0})".format(
                entry.time,
                entry.checksum,
                entry.path,
                entry.offset
            ))


@decorators.assume_version(INDEX_VERSION, 1)
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
    Arguments:
        index_path(str): path to the index
    """
    if not os.path.exists(index_path):
        touch_file(index_path)

        # create the index
        with open(index_path, 'wb') as index_handle:
            index_handle.write(INDEX_MAGIC_PREFIX)
            index_handle.write(struct.pack('i', INDEX_VERSION))
            index_handle.write(struct.pack('i', 0))


@decorators.assume_version(INDEX_VERSION, 1)
def modify_number_of_entries_in_index(index_handle, modify):
    """Helper function of inplace modification of number of entries in index

    Arguments:
        index_handle(file): handle of the opened index
        modify(function): function that will modify the value of number of entries
    """
    index_handle.seek(8)
    number_of_entries = read_int_from_handle(index_handle)
    index_handle.seek(8)
    index_handle.write(struct.pack('i', modify(number_of_entries)))


@decorators.assume_version(INDEX_VERSION, 1)
def write_entry_to_index(index_file, file_entry):
    """Writes the file_entry to its appropriate position within the index.

    Given the file entry, writes the entry within the file, moving everything by the given offset
    and then incrementing the number of entries within the index.

    Arguments:
        index_file(str): path to the index file
        file_entry(IndexEntry): index entry that will be written to the file
    """
    with open(index_file, 'rb+') as index_handle:
        modify_number_of_entries_in_index(index_handle, lambda x: x + 1)
        index_handle.seek(file_entry.offset)

        # Read previous entries to buffer and return back to the position
        buffer = index_handle.read()
        index_handle.seek(file_entry.offset)

        # Write the index_file entry to index
        index_handle.write(struct.pack('i', file_entry.time))
        index_handle.write(bytearray.fromhex(file_entry.checksum))
        index_handle.write(bytes(file_entry.path, 'utf-8'))
        index_handle.write(struct.pack('B', 0))

        # Write the stuff stored in buffer
        index_handle.write(buffer)


@decorators.assume_version(INDEX_VERSION, 1)
def register_in_index(base_dir, minor_version, registered_file, registered_file_checksum):
    """Registers file in the index corresponding to the minor_version

    If the index for the minor_version does not exist, then it is touched and initialized
    with empty prefix. Then the entry is added to the file.

    Arguments:
        base_dir(str): base directory of the minor version
        minor_version(str): sha-1 representation of the minor version of vcs (like e.g. commit)
        registered_file(path): filename that is registered
        registered_file_checksum(str): sha-1 representation fo the registered file
    """
    perun_log.msg_to_stdout("Registering file '{}'({}) into minor version {} index".format(
        registered_file, registered_file_checksum, minor_version
    ), 2)

    # Create the directory and index (if it does not exist)
    minor_dir, minor_index_file = split_object_name(base_dir, minor_version)
    touch_dir(minor_dir)
    touch_index(minor_index_file)

    print_index(minor_index_file)
    entry = IndexEntry(0, registered_file_checksum, registered_file, 12)
    write_entry_to_index(minor_index_file, entry)
    print("After writing")
    print_index(minor_index_file)


@decorators.assume_version(INDEX_VERSION, 1)
def remove_from_index(base_dir, minor_version, removed_file):
    """
    Arguments:
        base_dir(str): base directory of the minor version
        minor_version(str): sha-1 representation of the minor version of vcs (like e..g commit)
        removed_file(path): filename, that is removed from the tracking
    """
    perun_log.msg_to_stdout("Removing entry {} from the minor version {} index".format(
        removed_file, minor_version
    ))
    # TODO: Something something
