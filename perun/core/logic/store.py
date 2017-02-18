"""Store module contains set of functions for working with directories and repositories.

Store is a collection of helper functions that can be used to pack content, compute checksums,
or load and store into the directories or filenames.
"""

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


@decorators.assume_version(INDEX_VERSION, 1)
def walk_index(index_handle):
    """
    Arguments:
        index_handle(file): handle to file containing index

    Returns:
        IndexEntry: Index entry named tuple
    """
    # Move to the begging of the handle
    index_handle.seek(0)
    magic_bytes = index_handle.read(4)
    assert magic_bytes == 'dirc'
    index_version = index_handle.read(4)
    assert index_version == 1
    number_of_objects = index_handle.read(4)
    loaded_objects = 0

    def read_entry():
        """
        Returns:
            IndexEntry: one read index entry
        """
        file_time = index_handle.read(4)
        file_sha = index_handle.read(20)
        file_path, byte = "", index_handle.read(1)
        while byte != '\0':
            file_path += byte
            byte = index_handle.read(1)
        return IndexEntry(file_time, file_sha, file_path, index_handle.tell())

    for entry in iter(read_entry):
        loaded_objects += 1
        if loaded_objects > number_of_objects:
            perun_log.error("fatal: malformed index file")
        yield entry

    if loaded_objects != number_of_objects:
        perun_log.error("fatal: malformed index file")


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
def register_in_index(base_dir, minor_version, registered_file, registered_file_checksum):
    """
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
