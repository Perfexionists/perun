from typing import List, Any, Optional, ClassVar, Dict, Generator, Tuple, Union
from dataclasses import dataclass, field

from .parser import (
    PinDynamicOutputParser,
    InstrumentationLocation,
    ProgramData,
    DynamicDataEntry,
)
from perun.utils.log import msg_to_stdout


@dataclass(eq=False, repr=False)
class MemoryDataEntry(DynamicDataEntry):
    """Represents an entry with information about memory manipulation functions (e.g. malloc or
    free) during program runtime. The entry contains data that identify the function along with
    its arguments, return values, and location where was the entry taken (before or after).

    There are two different formats for the before and after entry. Firstly the before entry
    contains name and address of the function as well as address and name of its caller function.
    Other than that, the TID and PID are also present. To locate the call this entry corresponds
    to in the source code, the source file and line are there as well. At the end it also allows
    for variable number of argument values. The after entry then contains only the necessary
    information to pair these entries and the return value in form of an address.
    """

    FORMAT_BEFORE: ClassVar[List[str]] = [
        "address",
        "name",
        "parent_address",
        "parent_name",
        "tid",
        "pid",
        "source_file",
        "source_line",
    ]
    FORMAT_AFTER: ClassVar[List[str]] = ["address", "name", "tid", "pid", "return_pointer"]

    address: int
    name: str
    tid: int
    pid: int
    location: InstrumentationLocation

    return_pointer: Optional[str] = None
    parent_address: Optional[int] = None
    parent_name: Optional[str] = None
    source_line: Optional[int] = None
    source_file: Optional[str] = None

    args: List[int] = field(default_factory=list)

    def is_located_before(self):
        return self.location == InstrumentationLocation.BEFORE

    def __eq__(self, other) -> bool:
        """Determine if two entries are complementary. Two entries are complementary when only
        their location is different.

        :param MemoryDataEntry other: the entry to compare to

        :returns bool: True if the other entry is complementary
        """
        return (
            self.address == other.address
            and self.name == other.name
            and self.tid == other.tid
            and self.pid == other.pid
            and self.location != other.location
        )

    def __repr__(self):
        repr_string: str = (
            "RAW memory:\n"
            f"\tlocation: {'Before' if self.is_located_before() else 'After'}\n"
            f"\taddress: {self.address}\n"
            f"\tname: {self.name}\n"
            f"\ttid: {self.tid}\n"
            f"\tpid: {self.pid}\n"
        )
        if self.is_located_before():
            repr_string += (
                f"\tparent: {self.parent_address} {self.parent_name}\n"
                f"\tsource location: {self.source_line} {self.source_file}\n"
                f"\targs: {self.args}\n"
            )
        else:
            repr_string += f"\treturn pointer: {self.return_pointer}\n"
        return repr_string


class PinMemoryOutputParser(PinDynamicOutputParser):
    """Parser for the 'memory' mode of the PIN engine that produces perun profile entries
    with size allocated and deallocated at specific addresses for memory manipulation functions
    such as malloc or free.
    """

    def __init__(self, dynamic_data_file: str, program_data: ProgramData, **kwargs):
        super().__init__(dynamic_data_file)
        self.program_data: ProgramData = program_data
        self.workload = kwargs["workload"]

        self.function_call_backlog: List[MemoryDataEntry] = []

    def _parse_current_dynamic_entry(self):
        """Parse a single entry (line) from data collected by PIN into a MemoryDataEntry object.

        :returns MemoryDataEntry: the raw entry converted into an object
        """
        entry: List[Union[str, int]] = self._current_raw_entry.strip().split(";")
        entry_size: int = len(entry)

        # convert numerical values to int
        for idx in range(entry_size):
            if entry[idx].isnumeric():
                entry[idx] = int(entry[idx])

        if entry_size >= len(MemoryDataEntry.FORMAT_BEFORE):
            entry_base_data: List[Union[str, int]] = entry[: len(MemoryDataEntry.FORMAT_BEFORE)]
            entry_arguments_data: List[Union[str, int]] = entry[
                len(MemoryDataEntry.FORMAT_BEFORE) :
            ]
            data = dict(zip(MemoryDataEntry.FORMAT_BEFORE, entry_base_data))
            data |= {"args": entry_arguments_data, "location": InstrumentationLocation.BEFORE}
        else:  # MemoryDataEntry.FORMAT_AFTER
            data: Dict[str, Union[str, int]] = dict(zip(MemoryDataEntry.FORMAT_AFTER, entry))
            data["location"] = InstrumentationLocation.AFTER

        return MemoryDataEntry(**data)

    def parse_dynamic_data_file(self) -> Generator[Dict[str, Union[str, int]], None, None]:

        self._file_descriptor = open(self.file_path, "r")
        self._advance()

        while self._current_entry:
            if self._current_entry.is_located_before():
                if self._current_entry.name in ["free", "delete"]:
                    # the free and delete do not require after entry - yield the profile data
                    yield self._form_profile_data(start_entry=self._current_entry)
                else:
                    # save before entry to backlog
                    self.function_call_backlog.append(self._current_entry)

            else:  # InstrumentationLocation.AFTER
                # match after entry to a before entry in backlog
                before_entry: Optional[MemoryDataEntry] = None
                for index in range(len(self.function_call_backlog) - 1, -1, -1):
                    if self.function_call_backlog[index] == self._current_entry:
                        before_entry = self.function_call_backlog[index]
                        self.function_call_backlog.pop(index)
                        break
                if not before_entry:
                    msg_to_stdout("[DEBUG]: Closing entry does not have a pair in the backlog.", 3)
                    self._advance()
                    continue

                yield self._form_profile_data(
                    start_entry=before_entry, end_entry=self._current_entry
                )

            self._advance()

        if self.function_call_backlog:
            # NOTE: currently the pintool sometimes produces additional duplicate before entries
            # for malloc that are not closed they are safely ignored in backlog without any
            # information loss. Similarly, for new and delete there is a duplicate call of malloc
            # and free respectively, these are kept for time being since their parent is
            # specified as the new or delete, therefore they don't really introduce any confusion
            # to the profile.
            msg_to_stdout(
                "[Debug]: Unpaired memory entries in "
                f"backlog: {len(self.function_call_backlog)}.",
                3,
            )

    def _form_profile_data(
        self, start_entry: MemoryDataEntry, end_entry: Optional[MemoryDataEntry] = None
    ) -> Dict[str, Any]:
        """Based on the provided entries forms the perun profile data entry.

        :param MemoryDataEntry start_entry: the entry before a memory manipulation function
        :param MemoryDataEntry end_entry: the entry after a memory manipulation function if
                                          available (free and delete don't require this)

        :returns dict: the perun profile entry
        """
        arg_info_based_on_entry_name: Dict[str, List[Tuple[str, str]]] = {
            "new": [("size_t", "size")],
            "delete": [("void*", "pointer_address")],
            "malloc": [("size_t", "size")],
            "free": [("void*", "pointer_address")],
            "calloc": [("int", "count"), ("size_t", "size")],
            "realloc": [("void*", "pointer_address"), ("size_t", "size")],
        }

        amount_based_on_entry_name: int = 0
        if start_entry.name == "calloc":
            amount_based_on_entry_name = start_entry.args[0] * start_entry.args[1]
        elif start_entry.name == "realloc":
            amount_based_on_entry_name = start_entry.args[1]
        elif start_entry.name in ["malloc", "new"]:
            amount_based_on_entry_name = start_entry.args[0]
        elif start_entry.name in ["free", "delete"]:
            amount_based_on_entry_name = 0

        profile_data: Dict[str, Union[str, int]] = {
            "workload": self.workload,
            "type": "memory",
            "amount": amount_based_on_entry_name,
            "tid": start_entry.tid,
            "uid": f"{start_entry.name}#{start_entry.parent_name}",
            "caller": start_entry.parent_name,
            # NOTE: This is the line of memory function call (not implementation of the memory
            # function)
            "source-lines": start_entry.source_line,
            "source-file": start_entry.source_file,
        }

        if end_entry:
            profile_data |= {"return-value": end_entry.return_pointer, "return-value-type": "void*"}

        for idx, arg_value in enumerate(start_entry.args):
            argument_info: Tuple[str, str] = arg_info_based_on_entry_name[start_entry.name][idx]
            profile_data |= {
                f"arg_value#{idx}": arg_value,
                f"arg_type#{idx}": argument_info[0],
                f"arg_name#{idx}": argument_info[1],
            }

        return profile_data
