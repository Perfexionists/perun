import perun.utils.log as perun_log
import hashlib
import os
import zlib

from perun.utils.helpers import IndexEntry

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
    return [os.sep + components[0]] + [os.sep.join(components[:till]) for till in range(2, len(components) + 1)]


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
        pass
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


def register_in_index(base_dir, minor_version, registered_file, registered_file_checksum):
    """
    Arguments:
        base_dir(str): base directory of the minor version
        minor_version(str): sha-1 representation of the minor version of vcs (like e.g. commit)
        registered_file(path): filename that is registered
        registered_file_checksum(str): sha-1 representation fo the registered file
    """
    minor_dir, minor_index_file = split_object_name(base_dir, minor_version)
    touch_dir(minor_dir)


def remove_from_index(minor_version, removed_file):
    """
    Arguments:
        minor_version(str): sha-1 representation of the minor version of vcs (like e..g commit)
        removed_file(path): filename, that is removed from the tracking
    """
    # TODO: Something something
    pass
