"""Collection of methods for manipulation with Index.

This contains both helper constants, enums, and function, and most of all definitions
of various version of index entries.
"""

from __future__ import annotations

# Standard Imports
from enum import Enum
from typing import Callable, BinaryIO, Any, Iterable, Collection, TYPE_CHECKING
import binascii
import json
import os
import struct
import zlib

# Third-Party Imports

# Perun Imports
from perun.logic import pcs, store
from perun.utils import log as perun_log, timestamps
from perun.utils.common import common_kit
from perun.utils.exceptions import (
    EntryNotFoundException,
    MalformedIndexFileException,
    IndexNotFoundException,
)

if TYPE_CHECKING:
    from perun.profile.factory import Profile


# List of current versions of format and magic constants
INDEX_ENTRIES_START_OFFSET: int = 12
INDEX_NUMBER_OF_ENTRIES_OFFSET: int = 8
INDEX_MAGIC_PREFIX: bytes = b"pidx"
# Index Version 2.0 FastSloth
INDEX_VERSION: int = 2


class IndexVersion(Enum):
    SlowLorris = 1
    FastSloth = 2


class BasicIndexEntry:
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

    def __init__(self, time: str, checksum: str, path: str, offset: int, *_: Any) -> None:
        """
        :param time: modification timestamp of the entry profile
        :param checksum: checksum of the object, i.e. the path to its real content
        :param path: the original path to the profile
        :param offset: offset of the entry within the index
        """
        self.time: str = time
        self.checksum: str = checksum
        self.path: str = path
        self.offset: int = offset
        # For backward compatibility, we set everything to 'unknown', but not store it in the index
        self.type: str = "??"
        self.cmd: str = "??"
        self.workload: str = "??"
        self.label: str = "??"
        self.collector: str = "??"
        self.postprocessors: list[str] = []

    def __eq__(self, other: object) -> bool:
        """Compares two IndexEntries simply by checking the equality of its internal dictionaries

        :param other: other object to be compared
        :return: whether this object is the same as other
        """
        return self.__dict__ == other.__dict__

    @classmethod
    def read_from(cls, index_handle: BinaryIO, index_version: IndexVersion) -> "BasicIndexEntry":
        """Reads the entry from the index handle

        This is basic version, which stores only the information of timestamp, sha and path of the
        file.

        :param index_handle: opened index handle
        :param index_version: version of the opened index
        :return: one read BasicIndexEntry
        """
        if BasicIndexEntry.version.value < index_version.value:
            perun_log.error(
                f"internal error: called read_from() for BasicIndexEntry {index_version.value}"
            )
        file_offset = index_handle.tell()
        file_time = timestamps.timestamp_to_str(timestamps.read_timestamp_from_file(index_handle))
        file_sha = binascii.hexlify(index_handle.read(20)).decode("utf-8")
        file_path, byte = "", store.read_char_from_handle(index_handle)
        while byte != "\0":
            file_path += byte
            byte = store.read_char_from_handle(index_handle)
        return BasicIndexEntry(file_time, file_sha, file_path, file_offset)

    def write_to(self, index_handle: BinaryIO) -> None:
        """Writes entry at current location in the index_handle

        :param index_handle: file handle of the index
        """
        timestamps.write_timestamp(index_handle, timestamps.str_to_timestamp(self.time))
        index_handle.write(bytearray.fromhex(self.checksum))
        index_handle.write(bytes(self.path, "utf-8"))
        index_handle.write(struct.pack("B", 0))

    def __str__(self) -> str:
        """Converts the entry to one string representation

        :return:  string representation of the entry
        """
        return f" @{self.offset} {self.path} -> {self.checksum} ({self.time})"


class ExtendedIndexEntry(BasicIndexEntry):
    """Class representation of one extended index entry

    This corresponds to the extended version of the index called the Fast Sloth.
    It contains additional information about profile, so one do not have to load
    the profiles everytime it wants to print some basic information.

    :ivar time: modification timestamp of the entry profile
    :ivar checksum: checksum of the object, i.e. the path to its real content
    :ivar path: the original path to the profile
    :ivar offset: offset of the entry within the index
    :ivar cmd: command for which we collected data
    :ivar workload: workload of the command
    :ivar label: a custom profile label
    :ivar collector: collector used to collect data
    :ivar postprocessors: list of postprocessors used to postprocess data
    """

    version = IndexVersion.FastSloth

    def __init__(
        self,
        time: str,
        checksum: str,
        path: str,
        offset: int,
        profile: dict[str, Any] | Profile,
    ) -> None:
        """
        :param time: modification timestamp of the entry profile
        :param checksum: checksum of the object, i.e. the path to its real content
        :param path: the original path to the profile
        :param offset: offset of the entry within the index
        :param profile: basic information for profiles
        """
        super().__init__(time, checksum, path, offset)
        self.type: str = profile["header"]["type"]
        self.cmd: str = profile["header"]["cmd"]
        self.workload: str = profile["header"].get("workload", "")
        self.label: str = profile["header"].get("label", "")
        self.collector: str = profile["collector_info"]["name"]
        self.postprocessors: list[str] = [
            postprocessor["name"] for postprocessor in profile["postprocessors"]
        ]

    def __eq__(self, other: object) -> bool:
        """Compares two IndexEntries simply by checking the equality of its internal dictionaries

        :param other: other object to be compared
        :return: whether this object is the same as other
        """
        return self.__dict__ == other.__dict__

    @classmethod
    def read_from(cls, index_handle: BinaryIO, index_version: IndexVersion) -> "ExtendedIndexEntry":
        """Reads the entry from the index handle

        :param index_handle: opened index handle
        :param index_version: version of the opened index
        :return: one read ExtendedIndexEntry
        """
        if ExtendedIndexEntry.version.value > index_version.value:
            # Since we are reading from the older index, we will have to fix some stuff
            return ExtendedIndexEntry._read_from_older_index(index_handle, index_version)
        return ExtendedIndexEntry._read_from_same_index(index_handle, index_version)

    @classmethod
    def _read_from_older_index(
        cls, index_handle: BinaryIO, index_version: IndexVersion
    ) -> "ExtendedIndexEntry":
        """Reads the ExtendedIndexEntry from older version of index.

        This means, that not everything was stored in the index, and the profile itself has to be
        loaded to extract additional details.

        :param index_handle:
        :param index_version:
        :return:
        """
        basic_entry = super().read_from(index_handle, index_version)
        _, profile_name = store.split_object_name(pcs.get_object_directory(), basic_entry.checksum)
        profile = store.load_profile_from_file(profile_name, is_raw_profile=False)
        return ExtendedIndexEntry(
            basic_entry.time,
            basic_entry.checksum,
            basic_entry.path,
            basic_entry.offset,
            profile,
        )

    @classmethod
    def _read_from_same_index(
        cls, index_handle: BinaryIO, index_version: IndexVersion
    ) -> "ExtendedIndexEntry":
        """

        :param index_handle:
        :return:
        """
        basic_entry = BasicIndexEntry.read_from(index_handle, get_older_version(index_version))
        profile: dict[str, Any] = {
            "header": {
                "type": store.read_string_from_handle(index_handle),
                "cmd": store.read_string_from_handle(index_handle),
                "workload": store.read_string_from_handle(index_handle),
                "label": store.read_string_from_handle(index_handle),
            },
            "collector_info": {
                "name": store.read_string_from_handle(index_handle),
            },
            "postprocessors": [
                {"name": post} for post in store.read_list_from_handle(index_handle)
            ],
        }

        # Read the rest of the stored profile
        return ExtendedIndexEntry(
            basic_entry.time,
            basic_entry.checksum,
            basic_entry.path,
            basic_entry.offset,
            profile,
        )

    def write_to(self, index_handle: BinaryIO) -> None:
        """Writes entry at current location in the index_handle

        :param index_handle: file handle of the index
        """
        super().write_to(index_handle)
        store.write_string_to_handle(index_handle, self.type)
        store.write_string_to_handle(index_handle, self.cmd)
        store.write_string_to_handle(index_handle, self.workload)
        store.write_string_to_handle(index_handle, self.label)
        store.write_string_to_handle(index_handle, self.collector)
        store.write_list_to_handle(index_handle, self.postprocessors)

    def __str__(self) -> str:
        """Converts the entry to one string representation

        :return:  string representation of the entry
        """
        return (
            f" @{self.offset} {self.path} -> {self.checksum} ({self.time}) {self.type}; "
            f"{' '.join([self.cmd, self.workload])}; {self.label}; "
            f"{self.collector} {' '.join(self.postprocessors)}"
        )


def get_older_version(index_version: IndexVersion) -> IndexVersion:
    """Returns older version of the index

    :param index_version:
    :return: older version of the index
    """
    return IndexVersion(index_version.value - 1)


def walk_index(index_handle: BinaryIO) -> Iterable[BasicIndexEntry]:
    """Iterator through index entries

    Reads the beginning of the file, verifying the version and type of the index. Then it iterates
    through index entries and returns them as a BasicIndexEntry structure for further
    processing.

    :param index_handle: handle to file containing index
    :return: entry from the index
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
    if index_version > INDEX_VERSION:
        raise MalformedIndexFileException(
            "read index file is in format of different index version "
            f"(read index file = {index_version}, supported = {INDEX_VERSION})"
        )

    number_of_objects = store.read_int_from_handle(index_handle)
    loaded_objects = 0
    entry_constructor = INDEX_ENTRY_CONSTRUCTORS[INDEX_VERSION - 1]

    while index_handle.tell() + 24 < last_position and loaded_objects < number_of_objects:
        entry = entry_constructor.read_from(index_handle, IndexVersion(index_version))
        loaded_objects += 1
        yield entry

    if loaded_objects != number_of_objects:
        perun_log.error(
            "fatal: malformed index file: too many or too few objects registered in index"
        )


def print_index(index_file: str) -> None:
    """Helper function for printing the contents of the index

    :param index_file: path to the index file
    """
    with open(index_file, "rb") as index_handle:
        print_index_from_handle(index_handle)


def print_index_from_handle(index_handle: BinaryIO) -> None:
    """Helper function for printing the contents of index inside the handle.

    :param index_handle: opened file handle
    """
    index_prefix = index_handle.read(4)
    index_version = store.read_int_from_handle(index_handle)
    number_of_entries = store.read_int_from_handle(index_handle)

    perun_log.write(
        f"{index_prefix.decode('utf-8')}, index version {index_version} with "
        f"{number_of_entries} entries\n"
    )

    for entry in walk_index(index_handle):
        perun_log.write(str(entry))


def touch_index(index_path: str) -> None:
    """Initializes and creates the index if it does not exist

    The Version 1 index is of following form:
      -  4B magic prefix 'pidx' (perun index) for quick identification of the file
      -  4B version number (currently 1)
      -  4B number of index entries

    Followed by the entries of profiles of form:
      -  4B time of the file creation
      - 20B SHA-1 representation of the object
      -  ?B Variable length path
      -  ?B zero byte padding

    :param index_path: path to the index
    """
    if not os.path.exists(index_path):
        common_kit.touch_file(index_path)

        # create the index
        with open(index_path, "wb") as index_handle:
            initialize_index_in_handle(index_handle)


def initialize_index_in_handle(index_handle: BinaryIO) -> None:
    """Initialize the index prefix in the handle.

    First the magic bytes are written, then the version of the index and at last the
    number of the registered entries.

    :param index_handle:
    :return:
    """
    index_handle.write(INDEX_MAGIC_PREFIX)
    index_handle.write(struct.pack("i", INDEX_VERSION))
    index_handle.write(struct.pack("i", 0))


def update_index_version(index_handle: BinaryIO) -> None:
    """Updates the index handle to newer version

    :param index_handle: opened index handle
    """
    previous_position = index_handle.tell()
    index_handle.seek(4)
    index_handle.write(struct.pack("i", INDEX_VERSION))
    index_handle.seek(previous_position)


def modify_number_of_entries_in_index(index_handle: BinaryIO, modify: Callable[[int], int]) -> None:
    """Helper function of inplace modification of number of entries in index

    :param index_handle: handle of the opened index
    :param modify: function that will modify the value of number of entries
    """
    index_handle.seek(INDEX_NUMBER_OF_ENTRIES_OFFSET)
    number_of_entries = store.read_int_from_handle(index_handle)
    index_handle.seek(INDEX_NUMBER_OF_ENTRIES_OFFSET)
    index_handle.write(struct.pack("i", modify(number_of_entries)))


def write_entry_to_index(index_file: str, file_entry: BasicIndexEntry) -> None:
    """Writes the file_entry to its appropriate position within the index.

    The position is determined by lexicographic ordering over the entry paths.

    If the index already contains an entry with the same path as file_entry, then the original
    entry in the index is overwritten with the file_entry. Hence, the index works as an ordered
    set of entries with the key being the entry path.

    Offset specifications in the file_entry are ignored, as they may be unaligned or incorrect
    w.r.t. to the ordering of entries.

    :param index_file: path to the index file
    :param file_entry: index entry that will be written to the file
    """
    with open(index_file, "rb+") as index_handle:
        try:
            # Look for an index entry that occupies the space where this entry should be stored.
            looked_up_entry = lookup_entry_within_index(
                index_handle, lambda entry: entry.path >= file_entry.path, file_entry.path
            )
            # An identical entry already exists, skip any index update.
            if (
                looked_up_entry.path == file_entry.path
                and looked_up_entry.time == file_entry.time
                and looked_up_entry.label == file_entry.label
            ):
                perun_log.warn(
                    f"{file_entry.path} ({file_entry.time}) already registered in {index_file}",
                )
                return
            # A non-identical index entry with the same path has been found, overwrite.
            elif looked_up_entry.path == file_entry.path:
                placement_offset, preserve_offset = looked_up_entry.offset, index_handle.tell()
            # This is a completely new entry.
            else:
                placement_offset = preserve_offset = looked_up_entry.offset
        except EntryNotFoundException:
            # This entry should be placed as the last one within the index.
            index_handle.seek(0, 2)
            placement_offset = preserve_offset = index_handle.tell()

        # placement_offset: an index offset indicating where to store the entry.
        # preserve_offset: an index offset marking the position of the first index entry that
        #    should be stored directly after the newly inserted entry. This offset is used to fill
        #    a buffer with index entries that are to be shifted to make space for the new entry.
        # When placement and preserve offsets are identical, a new entry is to be written.
        # Otherwise, an existing entry is to be overwritten.
        if placement_offset == preserve_offset:
            modify_number_of_entries_in_index(index_handle, lambda x: x + 1)

        # Read the entries that are to be preserved into a buffer
        index_handle.seek(preserve_offset)
        buffer = index_handle.read()

        # (Over)write an entry in the index at the placement offset
        index_handle.seek(placement_offset)
        file_entry.write_to(index_handle)

        # Write back the entries stored in the buffer
        index_handle.write(buffer)

        # Finally update the index version, if it was the older one
        update_index_version(index_handle)


def write_list_of_entries(index_file: str, entry_list: list[BasicIndexEntry]) -> None:
    """Rewrites the index file to contain the list of entries only

    Clears the index and writes list of entries into the index

    :param index_file:
    :param entry_list:
    """
    # First delete the index
    with open(index_file, "wb+") as index_handle:
        index_handle.truncate(0)
        initialize_index_in_handle(index_handle)
        modify_number_of_entries_in_index(index_handle, lambda x: len(entry_list))
        index_handle.seek(INDEX_ENTRIES_START_OFFSET)
        for entry in entry_list:
            entry.write_to(index_handle)


def lookup_entry_within_index(
    index_handle: BinaryIO,
    predicate: Callable[[BasicIndexEntry], bool],
    looked_up_entry_name: str,
) -> BasicIndexEntry:
    """Looks up the first entry within index that satisfies the predicate

    :param index_handle: file handle of the index
    :param predicate: predicate that tests given entry in index BasicIndexEntry -> bool
    :param looked_up_entry_name: name of the entry we are looking up (for exception)
    :return: index entry satisfying the given predicate
    """
    for entry in walk_index(index_handle):
        if predicate(entry):
            return entry

    raise EntryNotFoundException(looked_up_entry_name)


def lookup_all_entries_within_index(
    index_handle: BinaryIO, predicate: Callable[[BasicIndexEntry], bool]
) -> list[BasicIndexEntry]:
    """
    :param index_handle: file handle of the index
    :param predicate: predicate that tests given entry in index BasicIndexEntry -> bool

    :return: list of index entries satisfying given predicate
    """
    return [entry for entry in walk_index(index_handle) if predicate(entry)]


def find_minor_index(minor_version: str) -> str:
    """Finds the corresponding index for the minor version or raises EntryNotFoundException if
    the index was not found.

    :param minor_version: the minor version representation or None for HEAD

    :return: path to the index file
    """
    # Find the index file
    _, index_file = store.split_object_name(pcs.get_object_directory(), minor_version)
    if not os.path.exists(index_file):
        raise IndexNotFoundException(index_file)
    return index_file


def register_in_pending_index(registered_file: str, profile: Profile) -> None:
    """Registers file in the index corresponding to the minor_version

    If the index for the minor_version does not exist, then it is touched and initialized
    with empty prefix. Then the entry is added to the file.

    :param registered_file: filename that is registered
    :param profile: profile to be registered
    """
    # Create the directory and index (if it does not exist)
    index_filename = pcs.get_job_index()
    touch_index(index_filename)
    registered_checksum = store.compute_checksum(registered_file.encode("utf-8"))

    register_in_index(index_filename, registered_file, registered_checksum, profile)


def register_in_minor_index(
    base_dir: str,
    minor_version: str,
    registered_file: str,
    registered_checksum: str,
    profile: Profile,
) -> None:
    """Registers file in the index corresponding to the minor_version

    If the index for the minor_version does not exist, then it is touched and initialized
    with empty prefix. Then the entry is added to the file.

    :param base_dir: base directory of the minor version
    :param minor_version: sha-1 representation of the minor version of vcs (like e.g. commit)
    :param registered_file: filename that is registered
    :param registered_checksum: sha-1 representation fo the registered file
    :param profile: profile to be registered
    """
    # Create the directory and index (if it does not exist)
    minor_dir, minor_index_file = store.split_object_name(base_dir, minor_version)
    common_kit.touch_dir(minor_dir)
    touch_index(minor_index_file)

    register_in_index(minor_index_file, registered_file, registered_checksum, profile)


def register_in_index(
    index_filename: str,
    registered_file: str,
    registered_file_checksum: str,
    profile: Profile,
) -> None:
    """Registers file in the index corresponding to either minor_version or pending profiles

    :param index_filename: source index file
    :param registered_file: filename that is registered in the index
    :param registered_file_checksum: sha-1 representation fo the registered file
    :param profile: profile to be registered
    """
    modification_stamp = timestamps.timestamp_to_str(os.stat(registered_file).st_mtime)
    entry_name = os.path.split(registered_file)[-1]
    entry = INDEX_ENTRY_CONSTRUCTORS[INDEX_VERSION - 1](
        modification_stamp, registered_file_checksum, entry_name, -1, profile
    )
    write_entry_to_index(index_filename, entry)


def remove_from_index(
    base_dir: str, minor_version: str, removed_file_generator: Collection[str]
) -> None:
    """Removes stream of removed files from the index.

    Iterates through all the removed files, and removes their partial/full occurrence from the
    index. The index is walked just once.

    :param base_dir: base directory of the minor version
    :param minor_version: sha-1 representation of the minor version of vcs (like e.g. commit)
    :param removed_file_generator: generator of filenames, that will be removed from the
        tracking
    """
    # Nothing to remove
    removed_profile_number = len(removed_file_generator)
    if removed_profile_number == 0:
        perun_log.minor_info("Nothing to remove")
        return

    # Get directory and index
    _, minor_version_index = store.split_object_name(base_dir, minor_version)

    if not os.path.exists(minor_version_index):
        raise EntryNotFoundException("", "empty index")

    perun_log.major_info("Removing from index")
    # Lookup all entries for the given function
    with open(minor_version_index, "rb+") as index_handle:
        # Gather all entries from the index
        all_entries = list(walk_index(index_handle))
        all_entries.sort(key=lambda unsorted_entry: unsorted_entry.offset)
        removed_entries = []

        for i, removed_file in enumerate(removed_file_generator):

            def lookup_function(looked_entry: BasicIndexEntry) -> bool:
                """Helper lookup function according to the type of the removed file"""
                if store.is_sha1(removed_file):
                    return looked_entry.checksum == removed_file
                else:
                    return looked_entry.path == removed_file

            count_status = (
                f"{common_kit.format_counter_number(i + 1, removed_profile_number)}/"
                f"{removed_profile_number}"
            )
            try:
                found_entry = lookup_entry_within_index(index_handle, lookup_function, removed_file)
                removed_entries.append(found_entry)
                perun_log.minor_success(
                    f"{count_status} {perun_log.path_style(found_entry.path)}", "deregistered"
                )
            except EntryNotFoundException:
                perun_log.minor_fail(
                    f"{count_status} {perun_log.path_style(removed_file)}", "not found"
                )
                removed_profile_number -= 1

        # Update number of entries
        index_handle.seek(INDEX_NUMBER_OF_ENTRIES_OFFSET)
        index_handle.write(struct.pack("i", len(all_entries) - len(removed_entries)))

        # For each entry remove from the index, starting from the greatest offset
        for entry in all_entries:
            if entry in removed_entries:
                continue
            entry.write_to(index_handle)

        index_handle.truncate()

    perun_log.major_info("Summary")
    if removed_profile_number:
        result_string = perun_log.success_highlight(
            f"{common_kit.str_to_plural(removed_profile_number, 'profile')}"
        )
        perun_log.minor_status("Removal succeeded for", status=result_string)
    else:
        perun_log.minor_info("Nothing to remove")


def get_profile_list_for_minor(base_dir: str, minor_version: str) -> list[BasicIndexEntry]:
    """Read the list of entries corresponding to the minor version from its index.

    :param base_dir: base directory of the models
    :param minor_version: representation of minor version
    :return: list of IndexEntries
    """
    _, minor_index_file = store.split_object_name(base_dir, minor_version)

    result = []
    if os.path.exists(minor_index_file):
        with open(minor_index_file, "rb+") as index_handle:
            index_handle.seek(4)
            index_version = store.read_int_from_handle(index_handle)
            result = list(walk_index(index_handle))
        # Update the version of the index
        if index_version < INDEX_VERSION:
            write_list_of_entries(minor_index_file, result)
    return result


def get_profile_number_for_minor(base_dir: str, minor_version: str) -> dict[str, int]:
    """
    :param base_dir: base directory of the profiles
    :param minor_version: representation of minor version
    :return: dictionary of number of profiles inside the index of the minor_version of types
    """
    _, minor_index_file = store.split_object_name(base_dir, minor_version)

    if os.path.exists(minor_index_file):
        profile_numbers_per_type = {
            profile_type: 0 for profile_type in common_kit.SUPPORTED_PROFILE_TYPES
        }

        with open(minor_index_file, "rb") as index_handle:
            # Read the overall
            index_handle.seek(INDEX_NUMBER_OF_ENTRIES_OFFSET)
            profile_numbers_per_type["all"] = store.read_int_from_handle(index_handle)

            # Check the types of the entry
            for entry in walk_index(index_handle):
                if entry.type in common_kit.SUPPORTED_PROFILE_TYPES:
                    profile_numbers_per_type[entry.type] += 1
            return profile_numbers_per_type
    else:
        return {"all": 0}


def load_custom_index(index_path: str) -> dict[Any, Any]:
    """Loads the content of a custom index file (e.g. temp or stats) as a dictionary.

    The index is json-formatted and compressed. In case the index cannot be read for some reason,
    an empty dictionary is returned.

    :param index_path: path to the index file

    :return: the decompressed and json-decoded index content.
    """
    # Create and init the index file if it does not exist yet
    if not os.path.exists(index_path):
        common_kit.touch_file(index_path)
        save_custom_index(index_path, {})
    # Open and load the file
    try:
        with open(index_path, "rb") as index_handle:
            return json.loads(store.read_and_deflate_chunk(index_handle))
    except (ValueError, zlib.error):
        # Contents either empty or corrupted, init the content to empty dict
        return {}


def save_custom_index(index_path: str, records: list[Any] | dict[Any, Any]) -> None:
    """Saves the index records to the custom index file.
    The index file is created if it does not exist or overwritten if it does.

    :param index_path: path to the index file
    :param records: the index entries/records in a format that can be transformed to json
    """
    with open(index_path, "w+b") as index_handle:
        compressed = store.pack_content(json.dumps(records, indent=2).encode("utf-8"))
        index_handle.write(compressed)


INDEX_ENTRY_CONSTRUCTORS = (BasicIndexEntry, ExtendedIndexEntry)
