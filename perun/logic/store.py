"""Store module contains set of functions for working with directories and repositories.

Store is a collection of helper functions that can be used to pack content, compute checksums,
or load and store into the directories or filenames.
"""

from __future__ import annotations

# Standard Imports
from typing import BinaryIO, Optional
import hashlib
import json
import os
import re
import string
import struct
import zlib

# Third-Party Imports

# Perun Imports
from perun import profile as profile
from perun.utils import log
from perun.utils.common import common_kit
from perun.utils.exceptions import IncorrectProfileFormatException
from perun.utils.structs.common_structs import PerformanceChange, DegradationInfo

INDEX_TAG_REGEX = re.compile(r"^(\d+)@i$")
INDEX_TAG_RANGE_REGEX = re.compile(r"^(\d+)@i-(\d+)@i$")
PENDING_TAG_REGEX = re.compile(r"^(\d+)@p$")
PENDING_TAG_RANGE_REGEX = re.compile(r"^(\d+)@p-(\d+)@p$")


def compute_checksum(content: bytes) -> str:
    """Compute the checksum of the content using the SHA-1 algorithm

    :param content: content we are computing checksum for
    :return: 40-character SHA-1 checksum of the content
    """
    return hashlib.sha1(content).hexdigest()


def is_sha1(checksum: str) -> bool:
    """
    :param checksum: hexa string
    :return: true if the checksum is sha1 checksum
    """
    return len(checksum) == 40 and all(c in string.hexdigits for c in checksum)


def version_path_to_sha(sha_path: str) -> Optional[str]:
    """Transforms the path of the minor version file / directory (represented by the SHA value) to
    the actual SHA value as a string.

    :param sha_path: path to the minor version directory
    :return: the SHA value of the minor version or None if it's not a valid SHA value
    """
    rest, lower_level = os.path.split(sha_path.rstrip(os.sep))
    _, upper_level = os.path.split(rest.rstrip(os.sep))
    sha = upper_level + lower_level
    return sha if is_sha1(sha) else None


def pack_content(content: bytes) -> bytes:
    """Pack the given content with packing algorithm.

    Uses the zlib compression algorithm, to deflate the content.

    :param content: content we are packing to bytes
    :return: packed content
    """
    return zlib.compress(content)


def read_and_deflate_chunk(file_handle: BinaryIO) -> str:
    """
    :param file_handle: opened file handle
    :return: deflated chunk or whole file
    """
    packed_content = file_handle.read()

    decompressor = zlib.decompressobj()
    return decompressor.decompress(packed_content).decode("utf-8")


def split_object_name(base_dir: str, object_name: str, object_ext: str = "") -> tuple[str, str]:
    """
    :param base_dir: base directory for the object_name
    :param object_name: sha-1 string representing the object (possibly with extension)
    :param object_ext: additional extension of the created file
    :return: full path for directory and full path for file
    """
    object_dir, object_file = object_name[:2], object_name[2:]
    object_dir_full_path = os.path.join(base_dir, object_dir)
    object_file_full_path = os.path.join(object_dir_full_path, object_file)

    return object_dir_full_path, object_file_full_path + object_ext


def add_loose_object_to_dir(base_dir: str, object_name: str, object_content: bytes) -> None:
    """
    :param base_dir: path to the base directory
    :param object_name: sha-1 string representing the object (possibly with extension)
    :param object_content: contents of the packed object
    """
    # Break the sha1 representation to base dir (first byte) and rest of the file
    object_dir_full_path, object_file_full_path = split_object_name(base_dir, object_name)

    # Create the dir
    common_kit.touch_dir(object_dir_full_path)

    # Write the content of the object
    # Note: That in some universe, there may become some collision, but in reality it should not
    if not os.path.exists(object_file_full_path):
        with open(object_file_full_path, "wb") as object_handle:
            object_handle.write(object_content)


def read_int_from_handle(file_handle: BinaryIO) -> int:
    """Helper function for reading one integer from handle

    :param file_handle: read file
    :return: one integer
    """
    return struct.unpack("i", file_handle.read(4))[0]


def read_char_from_handle(file_handle: BinaryIO) -> str:
    """Helper function for reading one char from handle

    :param file_handle: read file
    :return: one read char
    """
    return struct.unpack("c", file_handle.read(1))[0].decode("utf-8")


def read_number_of_entries_from_handle(index_handle: BinaryIO) -> int:
    """Helper function for reading number of entries in the handle.

    :param index_handle: filehandle with index
    """
    current_position = index_handle.tell()
    index_handle.seek(0)
    index_handle.read(4)
    read_int_from_handle(index_handle)
    number_of_entries = read_int_from_handle(index_handle)
    index_handle.seek(current_position)
    return number_of_entries


def write_list_to_handle(
    file_handle: BinaryIO, list_content: list[str], separator: str = " "
) -> None:
    """Writes list to the opened handle

    :param file_handle: opened file handle of the index
    :param list_content: list to be written in the handle
    :param separator: separator of the list
    """
    string_list = separator.join(list_content)
    write_string_to_handle(file_handle, string_list)


def read_list_from_handle(file_handle: BinaryIO, separator: str = " ") -> list[str]:
    """Reads list from the opened file index handle

    :param file_handle: opened file handle of the index
    :param separator: separator of the list
    :return: read list
    """
    string_list = read_string_from_handle(file_handle)
    return string_list.split(separator)


def write_string_to_handle(file_handle: BinaryIO, content: str) -> None:
    """Writes string to the opened file index handle.

    First we write the number of bytes to the index, and then the actual bytes.

    :param file_handle: opened file handle of the index
    :param content: string content to be written
    """
    binary_content = bytes(content, "utf-8")
    content_len = len(binary_content)
    binary_len = struct.pack("<I", content_len)
    file_handle.write(binary_len)
    file_handle.write(binary_content)


def read_string_from_handle(file_handle: BinaryIO) -> str:
    """Reads string from the opened file handle.

    Reads first one integer that states the number of stored bytes, then the bytes.

    :param file_handle: opened file handle of the index
    :return: read data
    """
    content_len = read_int_from_handle(file_handle)
    binary_content = file_handle.read(content_len).decode("utf-8")
    return binary_content


def save_degradation_list_for(
    base_dir: str,
    minor_version: str,
    degradation_list: list[tuple[DegradationInfo, str, str]],
) -> None:
    """Saves the given degradation list to a minor version storage

    This converts the list of degradation records to a storage-able format. Moreover,
    this loads all the already stored degradations. For each tuple of the change
    location and change type, this saves only one change record.

    :param base_dir: base directory, where the degradations will be stored
    :param minor_version: minor version for which we are storing the degradations
    :param degradation_list:
    :return:
    """
    already_saved_changes = load_degradation_list_for(base_dir, minor_version)

    list_of_registered_changes = dict()
    already_saved_changes.extend(degradation_list)
    for deg_info, cmdstr, source in already_saved_changes:
        info_string = " ".join([deg_info.to_storage_record(), source, cmdstr])
        uid = (deg_info.location, deg_info.type, cmdstr)
        list_of_registered_changes[uid] = info_string

    # Sort the changes
    to_be_stored_changes = sorted(list(list_of_registered_changes.values()))

    # Store the changes in the file
    minor_dir, minor_storage_file = split_object_name(base_dir, minor_version, ".changes")
    common_kit.touch_dir(minor_dir)
    common_kit.touch_file(minor_storage_file)
    with open(minor_storage_file, "w") as write_handle:
        write_handle.write("\n".join(to_be_stored_changes))


def parse_changelog_line(line: str) -> tuple[DegradationInfo, str, str]:
    """Parses one changelog record into the triple of degradation info, command string and minor.

    :param line: input line from one change log
    :return: triple (degradation info, command string, minor version)
    """
    if tokens := common_kit.LINE_PARSING_REGEX.match(line):
        deg_info = DegradationInfo(
            res=PerformanceChange[tokens.group("result")],
            t=tokens.group("type"),
            loc=tokens.group("location"),
            fb=tokens.group("from"),
            tt=tokens.group("to"),
            rd=float(tokens.group("drate")),
            ct=tokens.group("ctype"),
            cr=float(tokens.group("crate")),
            rdr=float(tokens.group("rdrate")),
        )
        return deg_info, tokens.group("cmdstr"), tokens.group("minor")
    else:
        log.error(f"could not parse changelog line '{line}'")
        # Note: this is never executed and is only for typechecking


def load_degradation_list_for(
    base_dir: str, minor_version: str
) -> list[tuple[DegradationInfo, str, str]]:
    """Loads a list of degradations stored for the minor version.

    This opens a file in the .perun/objects directory in the minor version subdirectory with the
    extension ".changes". The file is basically a log of degradation records separated by
    white spaces in ascii coding.

    :param base_dir: directory to the storage of the objects
    :param minor_version:
    :return: list of triples (DegradationInfo, command string, minor version source)
    """
    minor_dir, minor_storage_file = split_object_name(base_dir, minor_version, ".changes")
    common_kit.touch_dir(minor_dir)
    common_kit.touch_file(minor_storage_file)
    with open(minor_storage_file, "r") as read_handle:
        lines = read_handle.readlines()

    degradation_list = []
    warned_about_error = False
    for line in lines:
        try:
            parsed_triple = parse_changelog_line(line.strip())
            degradation_list.append(parsed_triple)
        except ValueError:
            if not warned_about_error:
                log.warn(f"Malformed changelog line in {minor_storage_file}")
                warned_about_error = True
    return degradation_list


def load_profile_from_file(
    file_name: str, is_raw_profile: bool, unsafe_load: bool = False
) -> profile.Profile:
    """Loads profile w.r.t :ref:`profile-spec` from file.

    :param file_name: file path, where the profile is stored
    :param is_raw_profile: if set to true, then the profile was loaded
        from the file system and is thus in the JSON already and does not have
        to be decompressed and unpacked to JSON format.
    :param unsafe_load: if set to True, then we assume that the @p file_name exists and skip the check for existence
    :returns: JSON dictionary w.r.t. :ref:`profile-spec`
    :raises IncorrectProfileFormatException: raised, when **filename** contains
        data, which cannot be converted to valid :ref:`profile-spec`
    Fixme: Add cache! Really badly!
    """
    if not unsafe_load and not os.path.exists(file_name):
        raise IncorrectProfileFormatException(file_name, "file '{}' not found")

    with open(file_name, "rb") as file_handle:
        return load_profile_from_handle(file_name, file_handle, is_raw_profile)


def load_profile_from_handle(
    file_name: str, file_handle: BinaryIO, is_raw_profile: bool
) -> profile.Profile:
    """
    Fixme: Add check that the loaded profile is in valid format!!!
    TODO: This should be broken into two parts

    :param file_name: name of the file opened in the handle
    :param file_handle: opened file handle
    :param is_raw_profile: true if the profile is in json format already
    :return: JSON representation of the profile
    :raises IncorrectProfileFormatException: when the profile cannot be parsed by json.loads(body)
        or when the profile is not in correct supported format or when the profile is malformed
    """
    if is_raw_profile:
        body = file_handle.read().decode("utf-8")
    else:
        # Read deflated contents and split to header and body
        contents = read_and_deflate_chunk(file_handle)
        header, body = contents.split("\0")
        prefix, profile_type, profile_size = header.split(" ")

        # Check the header, if the body is not malformed
        if (
            prefix != "profile"
            or profile_type not in common_kit.SUPPORTED_PROFILE_TYPES
            or len(body) != int(profile_size)
        ):
            raise IncorrectProfileFormatException(file_name, "malformed profile '{}'")

    # Try to load the json, if there is issue with the profile
    try:
        with common_kit.disposable_resources(json.loads(body)) as json_profile:
            return profile.Profile(json_profile)
    except ValueError:
        raise IncorrectProfileFormatException(
            file_name, f"profile '{file_name}' is not in profile format"
        )
