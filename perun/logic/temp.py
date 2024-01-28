"""This module contains functions for manipulating temporary files and directories located
in the .perun/tmp/ directory.

The .perun/tmp/ directory can be used to store various temporary files used during data collection,
postprocessing, visualization, logging, command output capturing, etc.
It is also possible to create directories and subdirectories to better separate files from different
sources.

The file name or content format is not restricted by any means. The user may or may not use the
interface provided by this module to store and retrieve temporary data, however, using at least
some minimal subset of functions can bring certain benefits in working with the tmp/ directory.

Some examples of the minimal interface operations:
--------------------------------------------------
 - temp_path: transforms supplied path (applies mostly for relative paths) into the context of the
              tmp/ directory and ensures that the resulting path is actually in the tmp/.
 - touch_temp_dir / touch_temp_file: Touches the required files or directory hierarchy.
 - delete_temp_dir / delete_temp_file: Safe deletion of the temporary files or directory hierarchy
                                       that respects protected status of files.
 - set_protected_status: Protects the temporary files against deletion when using this interface -
                         this will, however, not protect it against manual deletion by the user
                         directly in the file system. Can be also used to remove the protection.

The rest of the interface allows to also write to and read from the temporary files, clear the
contents of the file, list all temporary files etc.

Paths:
--------------------------------------------------
The interface functions that take a path argument accept either absolute or relative paths. The
relative paths are transformed to absolute ones, where the root/working directory is considered to
be the .perun/tmp/ directory. All resulting paths are checked so that no temporary file or
directory would be created outside the .perun/tmp/ directory.

The transformation works as follows:
- absolute path located in the .perun/tmp/ directory: no change
- relative path: transformed to absolute path where .perun/tmp/ is considered as the
                 root/working directory for the relative path
- absolute or relative path out of the .perun/tmp/: an exception is thrown


Protected files:
--------------------------------------------------
The protection status of files is simply a corresponding flag stored in the index file. When
deleting files using this interface, the protection flag is checked and if the 'force' mode
is not used, the file will not be deleted and exception will be raised. This allows to ensure
that some important files are not easily and accidentally removed, while also providing a
mechanism to delete them if the need for complete cleanup arises.

Deletion:
---------------------------------------------------
When using this interface, the files are not automatically cleaned up when they are no longer used.
Thus, the user should take care to delete them appropriately to save some memory.
"""
from __future__ import annotations

# Standard Imports
from typing import Optional, Any, cast, BinaryIO
import json
import os
import zlib

# Third-Party Imports

# Perun Imports
from perun.logic import index, pcs, store
from perun.utils import exceptions, log as perun_log
from perun.utils.common import common_kit

# Valid protection levels of temporary files
UNPROTECTED, PROTECTED = "unprotected", "protected"

# Options for temporary files filtering based on the protection level
PROTECTION_LEVEL = ["all", UNPROTECTED, PROTECTED]

# Valid attributes that can be used for sorting
SORT_ATTR = ["name", "protection", "size"]

# Additional sorting parameters
SORT_ATTR_MAP = {
    "name": {"pos": 0, "reverse": False},
    "protection": {"pos": 1, "reverse": False},
    "size": {"pos": 2, "reverse": True},
}


class TempFile:
    """Context manager class for managing a single temporary file in a limited scope. The CM
    ensures that the temporary file is properly created (if it does not already exist) as well as
    deleted after the CM scope is left.

    :ivar str filename: the name of the temporary file
    :ivar str abspath: the absolute path to the temporary file
    """

    __slots__ = ["filename", "abspath"]

    def __init__(self, filename: str) -> None:
        """
        :param str filename: the name of the temporary file
        """
        self.filename = filename
        self.abspath = temp_path(filename)

    def __enter__(self) -> "TempFile":
        """Context manager entry sentinel, creates the temporary file

        :return object: the context manager class instance
        """
        touch_temp_file(self.filename)
        return self

    def __exit__(self, exc_type: type, exc_val: Exception, exc_tb: BaseException) -> None:
        """Context manager exit sentinel, deletes the managed temporary file.

        :param type exc_type: the type of the exception
        :param exception exc_val: the value of the exception
        :param traceback exc_tb: the traceback of the exception
        """
        delete_temp_file(self.filename, force=True)


def temp_path(path: str) -> str:
    """Transforms the provided path to the tmp/ directory context, i.e.:
        - absolute path located in the .perun/tmp/ directory: no change
        - relative path: transformed to absolute path where .perun/tmp/ is considered as the
                         root/working directory for the relative path
        - absolute or relative path out of the .perun/tmp/: an exception is raised

    :param str path: the path that should be transformed

    :return str: the transformed path
    """
    tmp_location = pcs.get_tmp_directory()

    # The 'path' may be absolute with tmp/ location as prefix, which os.path.join handles well
    # However it might also be a custom path '/ab/ef/' which causes join to create '/ab/ef/'
    path = os.path.abspath(os.path.join(tmp_location, path))
    # The resulting path might end up out of tmp/ for both absolute or relative paths
    if not path.startswith(tmp_location):
        raise exceptions.InvalidTempPathException(
            f"The resulting path '{path}' is not located in the perun tmp/ directory."
        )
    return path


def touch_temp_dir(dir_path: str) -> None:
    """Touches the given directory path.

    For details regarding the path format, see the module docstring.

    :param str dir_path: the directory path
    """
    # Append the path to the tmp/ directory
    dir_path = temp_path(dir_path)
    # Create the new directory(ies)
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)


def touch_temp_file(file_path: str, protect: bool = False) -> None:
    """Touches the given temporary file and sets the protection level.

    For details regarding the path format, see the module docstring.

    :param str file_path: the temporary file path
    :param bool protect: if True, the temporary file will be indexed as protected
    """
    # Append the file path to the tmp/ directory
    file_path = temp_path(file_path.rstrip(os.sep))
    # Make sure that the directory hierarchy for the file exists
    touch_temp_dir(os.path.dirname(file_path))

    common_kit.touch_file(file_path)
    # Register the file as protected if needed
    if protect:
        _add_to_index(file_path, protected=protect)


def exists_temp_dir(dir_path: str) -> bool:
    """Checks if the temporary directory given by 'dir_path' exists.

    For details regarding the path format, see the module docstring.

    :param str dir_path: the temporary directory

    :return bool: True if the directory exists
    """
    dir_path = temp_path(dir_path)
    return os.path.exists(dir_path) and os.path.isdir(dir_path)


def exists_temp_file(file_path: str) -> bool:
    """Checks if the temporary file given by 'file_path' exists.

    For details regarding the path format, see the module docstring.

    :param str file_path: the temporary file

    :return bool: True if the file exists
    """
    file_path = temp_path(file_path)
    return os.path.exists(file_path) and os.path.isfile(file_path)


def create_new_temp(
    file_path: str,
    content: Any,
    json_format: bool = False,
    protect: bool = False,
    compress: bool = False,
) -> None:
    """Creates new temporary file if it does not exist yet and writes the 'content' into the file.
    An exception is raised if the file already exists.

    For details regarding the path format, see the module docstring.

    :param str file_path: the path to the file to create
    :param content: the content of the new temporary file
    :param bool json_format: if True, the content will be formatted as json
    :param bool protect: if True, the file will have the protected status
    :param bool compress: if True, the content will be compressed
    """
    # Do not allow file overwrite
    file_path = temp_path(file_path)
    if os.path.exists(file_path):
        raise exceptions.InvalidTempPathException(
            f"The temporary file '{file_path}' already exists."
        )
    # Make sure that the directory hierarchy for the file exists
    touch_temp_dir(os.path.dirname(file_path))
    _write_to_temp(file_path, content, json_format, protect, compress)


def store_temp(
    file_path: str,
    content: Any,
    json_format: bool = False,
    protect: bool = False,
    compress: bool = False,
) -> None:
    """Writes the 'content' to the temporary file given by the 'file_path'. The temporary file is
    created if it does not exist and overwritten if it does.

    For details regarding the path format, see the module docstring.

    :param str file_path: the path to the temporary file
    :param content: the new content of the temporary file
    :param bool json_format: if True, the content will be formatted as json
    :param bool protect: if True, the file will have the protected status
    :param bool compress: if True, the content will be compressed
    """
    file_path = temp_path(file_path)
    # Make sure that the directory hierarchy for the file exists
    touch_temp_dir(os.path.dirname(file_path))
    _write_to_temp(file_path, content, json_format, protect, compress)


def read_temp(file_path: str) -> Any:
    """Reads the content of the temporary file 'file_path'. An exception is raised if the file does
    not exist. None is returned if the file could not have been read, is corrupted, has
    inconsistent or invalid index properties.

    For details regarding the path format, see the module docstring.

    :param str file_path: the path to the temporary file to read

    :return str or None: the file content or None if an error occurred
    """
    # Check the existence of the file and obtain its properties
    file_path = temp_path(file_path)
    _is_tmp_file(file_path)
    json_format, _, compressed = _get_index_entry(file_path)
    try:
        with open(file_path, "rb" if compressed else "r") as tmp_handle:
            # Take care of possible compression
            if compressed:
                content = store.read_and_deflate_chunk(cast(BinaryIO, tmp_handle))
            else:
                content = tmp_handle.read()
            # Parse the json-formatted files
            if json_format:
                content = json.loads(content)
        return content
    # Handle possible errors
    except (OSError, ValueError, zlib.error) as exc:
        perun_log.msg_to_file(f"Error reading temporary file: {exc}", 0)
        return {}


def reset_temp(file_path: str) -> None:
    """Clears the content and resets properties of the temporary file 'file_path'

    For details regarding the path format, see the module docstring.

    :param str file_path: the path to the temporary file
    """
    file_path = temp_path(file_path)
    _is_tmp_file(file_path)
    with open(file_path, "w"):
        pass
    _add_to_index(file_path, False, False, False)


def list_all_temps(root: Optional[str] = None) -> list[str]:
    """Provides a list of all the temporary files in the 'root' folder and all its subfolders.

    For details regarding the path format, see the module docstring.

    If the 'root' is not provided or None, the whole tmp/ folder is considered as the root.

    :param str root: the path to the root folder

    :return list: paths to all the files in the 'root' folder hierarchy
    """
    # Get the correct root
    root = pcs.get_tmp_directory() if root is None else temp_path(root)
    _is_tmp_dir(root)
    # Omit the index file
    return [
        os.path.join(dirpath, file)
        for dirpath, _, files in os.walk(root)
        for file in files
        if file != ".index"
    ]


def list_all_temps_with_details(
    root: Optional[str] = None,
) -> list[tuple[str, str, int]]:
    """Provides a list of all the temporary files in the 'root' folder and all its subfolders
    with additional data such as protection level and file size.

    For details regarding the path format, see the module docstring.

    If the 'root' is not provided or None, the whole tmp/ folder is considered as the root.

    :param str root: the path to the root folder

    :return list: tuples (name, protection level, size)
    """
    # Get the files, protection level and sizes
    tmp_files = list_all_temps(root)
    unprotected, protected = _filter_protected_files(tmp_files)
    u_sizes, p_sizes = _get_temps_size(unprotected), _get_temps_size(protected)
    # Create 3 lists representing the names, protection levels and sizes
    tmp_files = unprotected + protected
    sizes = u_sizes + p_sizes
    protection_level = [UNPROTECTED] * len(unprotected) + [PROTECTED] * len(protected)

    # Create tuples out of the parameters
    result = []
    for idx, file in enumerate(tmp_files):
        result.append((file, protection_level[idx], sizes[idx]))
    return result


def get_temp_properties(file_path: str) -> tuple[bool, bool, bool]:
    """Returns the known properties of the temporary file such as:
        - json_formatted
        - protected
        - compressed

    If the file has no known or registered properties, the default value is False for all properties

    For details regarding the path format, see the module docstring.

    :param str file_path: the path to the temporary file

    :return tuple: (json_formatted, protected, compressed)
    """
    return _get_index_entry(temp_path(file_path))


def set_protected_status(file_path: str, protected: bool) -> None:
    """Sets a new protection status of a temporary file.

    For details regarding the path format, see the module docstring.

    :param str file_path: the path to the temporary file
    :param bool protected: True for protected file, False for unprotected file
    """
    file_path = temp_path(file_path)
    _is_tmp_file(file_path)
    _add_to_index(file_path, protected=protected)


def delete_temp_dir(root: str, ignore_protected: bool = False, force: bool = False) -> None:
    """Delete the whole temporary directory given by the 'root' and all its content.

    For details regarding the path format, see the module docstring.

    If 'ignore_protected' is False and the directory structure contains protected temporary files,
    the whole deletion process is aborted, no file is deleted and an exception is raised.
    If set to True, protected files will be kept and only unprotected files and empty folders
    will be deleted.

    If 'force' is True, all the files including the protected ones are deleted regardless of the
    'ignore_protected' value.

    :param str root: path to the temporary directory to delete
    :param bool ignore_protected: protected files in the directory will either abort the deletion
                                  process or they will be ignored and not deleted
    :param bool force: if True, the protected files will be also deleted
    """
    root = temp_path(root)
    # Check if the directory path is valid
    _is_tmp_dir(root)

    # Delete all the temporary files and empty directories
    delete_all_temps(root, ignore_protected, force)
    _delete_empty_directories(root)


def delete_temp_file(file_path: str, ignore_protected: bool = False, force: bool = False) -> None:
    """Delete the temporary file identified by the 'file_path'.

    For details regarding the path format, see the module docstring.

    If 'ignore_protected' is False and the temporary file is protected, the whole deletion process
    is aborted, the file is not deleted and an exception is raised.
    If set to True, the protected file will be kept.

    If 'force' is True, the protected file is deleted regardless of the 'ignore_protected' value.

    :param str file_path: path to the temporary file to delete
    :param bool ignore_protected: protected file will either abort the deletion process or
                                  the file will be ignored and not deleted
    :param bool force: if True and the 'filepath' is protected, the file will be deleted anyway
    """
    file_path = temp_path(file_path.rstrip(os.sep))
    # Check if tmp file exists
    _is_tmp_file(file_path)
    # Don't delete protected temp files unless forced
    _delete_files([file_path], ignore_protected, force)


def delete_all_temps(
    root: Optional[str] = None, ignore_protected: bool = False, force: bool = False
) -> None:
    """Deletes all the temporary files in the 'root' folder and its subfolders.

    For details regarding the path format, see the module docstring.

    If 'ignore_protected' is False and the directory structure contains protected temporary files,
    the whole deletion process is aborted, no file is deleted and an exception is raised.
    If set to True, protected files will be kept and only unprotected files will be deleted.

    If 'force' is True, all the files including the protected ones are deleted regardless of the
    'ignore_protected' value.

    :param str root: the path to the root folder
    :param bool ignore_protected: protected files in the directories will either abort the deletion
                                  process or they will be ignored and not deleted
    :param bool force: if True, the protected files will be also deleted
    """
    tmp_files = list_all_temps(root)
    _delete_files(tmp_files, ignore_protected, force)


def synchronize_index() -> None:
    """Synchronizes the index file with the content of the tmp/ directory.

    Namely, removes index entries that are not needed or refer to no longer existing files
    """
    index_entries = index.load_custom_index(pcs.get_tmp_index())
    tmp_files = list_all_temps()
    for tmp_name, conf in list(index_entries.items()):
        # Remove records of files that are deleted or not necessary to track
        if tmp_name not in tmp_files or (
            not conf["json"] and not conf["protected"] and not conf["compressed"]
        ):
            del index_entries[tmp_name]
    # Save the updated index
    index.save_custom_index(pcs.get_tmp_index(), index_entries)


def _is_tmp_path(path: str) -> None:
    """Checks if the provided path exists and is within the .perun/tmp/ directory. If not, an
    exception is raised.

    :param str path: the path that should be checked
    """
    if not path.startswith(pcs.get_tmp_directory()) or not os.path.exists(path):
        raise exceptions.InvalidTempPathException(f"The 'tmp' path '{path}' does not exist.")


def _is_tmp_file(path: str) -> None:
    """Checks if the provided path is valid and existing temporary file. If not, an exception is
    raised.

    :param str path: the path to the temporary file to check
    """
    _is_tmp_path(path)
    if not os.path.isfile(path):
        raise exceptions.InvalidTempPathException(f"The 'tmp' path '{path}' is not a file.")


def _is_tmp_dir(path: str) -> None:
    """Checks if the provided path is valid and existing temporary directory. if not, an exception
    is raised.

    :param str path: the path to the temporary directory to check
    """
    _is_tmp_path(path)
    if not os.path.isdir(path):
        raise exceptions.InvalidTempPathException(f"The 'tmp' path '{path}' is not a directory.")


def _delete_files(tmp_files: list[str], ignore_protected: bool, force: bool) -> None:
    """Deletes the supplied temporary files.

    If 'ignore_protected' is False and the directory structure contains protected temporary files,
    the whole deletion process is aborted, no file is deleted and an exception is raised.
    If set to True, protected files will be kept and only unprotected files will be deleted.

    If 'force' is True, all the files including the protected ones are deleted regardless of the
    'ignore_protected' value.

    :param list tmp_files: a list of the temporary file paths to delete
    :param bool ignore_protected: protected files in the directories will either abort the deletion
                                  process or they will be ignored and not deleted
    :param bool force: if True, the protected files will be also deleted
    """
    # Check for protected files
    if not force:
        tmp_files, protected = _filter_protected_files(tmp_files)
        if protected and not ignore_protected:
            # Abort the operation if ignore_protected is not set
            raise exceptions.ProtectedTempException(
                "Aborted temporary files deletion due to a presence of protected files."
            )
    # Delete all the files and their potential records in the index
    for file in tmp_files:
        os.remove(file)
    _delete_index_entries(tmp_files)


def _filter_protected_files(tmp_files: list[str]) -> tuple[list[str], list[str]]:
    """Filters the protected files in the supplied temporary files.

    :param list tmp_files: a list of the temporary files

    :return tuple: (list of unprotected files, list of protected files)
    """
    index_entries = index.load_custom_index(pcs.get_tmp_index())
    unprotected, protected = [], []
    for file in tmp_files:
        # Check if file is indexed and protected
        if index_entries.get(file, {"protected": False})["protected"]:
            protected.append(file)
        else:
            unprotected.append(file)
    return unprotected, protected


def _delete_empty_directories(root: str) -> None:
    """Identifies and deletes all empty directories and subdirectories in the 'root' directory.

    The .perun/tmp/ directory, however, will not be deleted this way.

    :param str root: the path to the root directory
    """
    # Obtain all the subdirectories in the root in the reverse order, however make sure tmp/ stays
    tmp_root = pcs.get_tmp_directory()
    root = temp_path(root)
    all_dirs = [dirs for dirs, _, _ in os.walk(root, topdown=False) if dirs != tmp_root]
    # Check if the given directory is empty and delete it
    for directory in all_dirs:
        if not os.listdir(directory):
            os.rmdir(directory)


def _write_to_temp(
    file_path: str, content: Any, json_format: bool, protect: bool, compress: bool
) -> None:
    """Writes the 'content' into the temporary file and stores the properties into the index
    if needed.

    :param str file_path: the path to the temporary file
    :param content: the new content of the temporary file
    :param bool json_format: if True, the content will be formatted as json
    :param bool protect: if True, the file will have the protected status
    :param bool compress: if True, the content will be compressed
    """
    # Optionally encode the content to json and compress it
    file_mode = "w+"
    if json_format:
        content = json.dumps(content, indent=2)
    if compress:
        file_mode = "w+b"
        content = store.pack_content(content.encode("utf-8"))
    # Write the content to the tmp file
    with open(file_path, file_mode) as tmp_handle:
        tmp_handle.write(content)
    # Save the properties to the index file if needed
    _add_to_index(file_path, json_format, protect, compress)


def _get_temps_size(tmp_files: list[str]) -> list[int]:
    """Obtains the sizes (in bytes) of the temporary files.

    :param list tmp_files: a list of temporary files
    :return list: list with corresponding sizes (the pairs are defined by the same list index)
    """
    sizes = []
    for tmp_file in tmp_files:
        sizes.append(os.stat(tmp_file).st_size)
    return sizes


def _add_to_index(
    tmp_file: str,
    json_format: bool = False,
    protected: bool = False,
    compressed: bool = False,
) -> None:
    """Adds a new entry into the index. The entry tracks 'json_format, protected, compressed'
    properties for the given tmp_file. If all of those properties are False, no entry is created.

    :param str tmp_file: the path of the temporary file
    :param bool json_format: the property describing if json format was used
    :param bool protected: the protection level property
    :param bool compressed: the compression property
    """
    # Do not index entries that have no True parameters
    if not json_format and not protected and not compressed:
        # However remove possible outdated occurrences of the index entry
        _delete_index_entries([tmp_file])
        return
    # Otherwise save the parameters
    index_records = index.load_custom_index(pcs.get_tmp_index())
    file_config = index_records.setdefault(tmp_file, {})
    file_config["json"] = json_format
    file_config["protected"] = protected
    file_config["compressed"] = compressed
    index.save_custom_index(pcs.get_tmp_index(), index_records)


def _get_index_entry(tmp_file: str) -> tuple[bool, bool, bool]:
    """Gets an index entry (i.e. the tracked properties) for the given temporary file.

    If no corresponding entry for the file exists, then all the properties are assumed
    to be False.

    :param str tmp_file: the path of the temporary file
    :return tuple: (json_format, protected, compressed)
    """
    file_record = index.load_custom_index(pcs.get_tmp_index()).get(tmp_file)
    if file_record is None:
        # Non-existent entries are assumed to be all False
        return False, False, False
    return file_record["json"], file_record["protected"], file_record["compressed"]


def _delete_index_entries(tmp_files: list[str]) -> None:
    """Deletes the index entries (if they exist) of the supplied temporary files.

    :param list tmp_files: the list of the temporary files for which to delete the entries
    """
    index_records = index.load_custom_index(pcs.get_tmp_index())
    for tmp_file in tmp_files:
        if tmp_file in index_records:
            del index_records[tmp_file]
    index.save_custom_index(pcs.get_tmp_index(), index_records)
