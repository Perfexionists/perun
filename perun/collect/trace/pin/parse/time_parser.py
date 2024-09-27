from dataclasses import dataclass
from typing import List, Any, Optional, ClassVar, Dict, Generator, Tuple, Union

from perun.collect.trace.pin.scan_binary import FunctionArgument
from perun.utils.log import msg_to_stdout
from .parser import (
    PinDynamicOutputParser,
    Granularity,
    InstrumentationLocation,
    ProgramData,
    FunctionData,
    BasicBlockData,
    FunctionStart,
)


@dataclass(eq=False, repr=False)
class TimeDataEntry:
    """Represents an entry with information about function during program runtime. The entry
    contains data that identify the function along with its arguments, location and timestamp
    when was the entry taken.

    The format of an entry contains two flags granularity (function or basic block) and location
    (before or after a function or basic block), three values that identify the function (or
    basic block), and the timestamp when was the entry taken. Format also supports function
    arguments at its end.
    """

    FLAGS: ClassVar[List[str]] = ["granularity", "location"]
    FORMAT: ClassVar[List[Union[List[str], str]]] = [FLAGS, "id", "tid", "pid", "timestamp"]

    granularity: Granularity
    location: InstrumentationLocation

    id: int
    tid: int  # thread ID
    pid: int  # process ID
    timestamp: int

    # additional routine entry information
    args: Optional[List[FunctionArgument]] = None

    def is_located_before(self) -> bool:
        """Identifies if the data entry is located before the instrumentation unit.
        :return bool: True if the entry is from the start of the instrumentation unit, otherwise False
        """
        return self.location == InstrumentationLocation.BEFORE

    def time_delta(self, other) -> int:
        """Calculates the time delta from two entries

        :param RawTimeDataEntry other: the data entry complementary to self
        :return int: time delta of the complementary entries
        """
        return abs(self.timestamp - other.timestamp)

    def is_function_granularity(self) -> bool:
        """Identifies if the data entry is at the function (routine) granularity

        :return bool: True if the granularity of the entry is at routine level, otherwise False
        """
        return self.granularity == Granularity.RTN

    def is_in_same_scope(self, other) -> bool:
        """Determine if the other entry is in the same scope, meaning that its PID and TID is
        the same.

        :param TimeDataEntry other: the entry to compare to

        :returns bool: True if the other entry is in the same scope
        """
        return self.pid == other.pid and self.tid == other.tid

    def __eq__(self, other) -> bool:
        """Determines if two entries are for the same function (or basic block) and are
        complementary. Two entries are complementary when their location are opposite.
        """
        return (
            self.id == other.id
            and self.tid == other.tid
            and self.pid == other.pid
            and self.location != other.location
        )

    def __repr__(self) -> str:
        return (
            "Raw time entry:\n"
            f"\tgranularity: {'Routine' if self.is_function_granularity() else 'Basic Block'}\n"
            f"\tlocation: {'Before' if self.is_located_before() else 'After'}\n"
            f"\tid: {self.id}\n"
            f"\ttid: {self.tid}\n"
            f"\tpid: {self.pid}\n"
            f"\ttimestamp: {self.timestamp}\n"
        )

    def get_data_for_profile(self, other) -> Dict[str, Any]:
        """Extracts relevant information from the entry for the perun performance profile.

        NOTE: Will not check if the other entry is compatible because when collecting only basic blocks
        the basic block entries are used to create profile data for functions. These basic block entries
        will have correct location, however, their id will be different since they are different basic blocks.

        :param TimeDataEntry other: the complementary data entry

        :return dict: partial perun performance profile entry
        """

        profile_data: Dict[str, Any] = {
            "tid": self.tid,
            "pid": self.pid,
            "timestamp": self.timestamp if self.is_located_before() else other.timestamp,
            "amount": self.time_delta(other),
        }

        if not self.args:
            return profile_data

        for argument in self.args:
            profile_data |= {
                f"arg_value#{argument.index}": argument.value,
                f"arg_type#{argument.index}": argument.type,
                f"arg_name#{argument.index}": argument.name,
            }

        return profile_data


class PinTimeOutputParser(PinDynamicOutputParser):
    """Parser for the 'time' mode of the PIN engine that produces perun profile entries
    with time duration of functions and/or basic blocks.
    """

    def __init__(self, dynamic_data_file: str, program_data: ProgramData, **kwargs) -> None:
        super().__init__(dynamic_data_file)
        self.basic_blocks_only: bool = kwargs["collect_basic_blocks_only"]
        self.workload: str = kwargs["workload"]
        self.program_data: ProgramData = program_data

        self.function_call_backlog: List[Tuple[TimeDataEntry, str]] = []
        self.basic_block_backlog: List[Tuple[TimeDataEntry, str]] = []

        # Notes if the start of the function is expected in the following entry. Start of a main
        # function is expected at the beginning, however, the pid and tid are not known.
        self._function_start: FunctionStart = FunctionStart(
            expected=True, function_pid=None, function_tid=None
        )
        self._function_call_counter: int = 0

    def _parse_current_dynamic_entry(self) -> TimeDataEntry:
        """Parse a single entry (line) from data collected by PIN into a TimeDataEntry object.

        :returns TimeDataEntry: the raw entry converted into an object
        """
        entry: List[str] = self._current_raw_entry.strip().split(";")

        # Parse base format common for both functions and basic blocks
        flags: str = entry[0]
        other_base_format_elements: List[str] = entry[1 : len(TimeDataEntry.FORMAT)]
        other_base_format_keys: List[str] = TimeDataEntry.FORMAT[1:]
        data: Dict[str, int] = dict(zip(TimeDataEntry.FORMAT[0], [int(flag) for flag in flags]))
        data |= dict(
            zip(other_base_format_keys, [int(element) for element in other_base_format_elements])
        )
        data_entry: TimeDataEntry = TimeDataEntry(**data)

        # Parse the optional arguments at the end of a function entry
        if data_entry.is_function_granularity() and len(entry) > len(TimeDataEntry.FORMAT):
            # There are additional function arguments present in the entry
            function: FunctionData = self.program_data.functions[data_entry.id]
            # Values of function arguments
            argument_values: List[str] = entry[len(TimeDataEntry.FORMAT) :]

            for argument, value in zip(function.arguments, argument_values):
                if "char*" in argument.type:  # Store the length of a string
                    value = len(value)
                elif "char" in argument.type:  # Store the ordinal value instead of character
                    value = ord(value)
                argument.value = int(value)

            data_entry.args = function.arguments

        return data_entry

    def parse_dynamic_data_file(self) -> Generator[Dict[str, Union[str, int]], None, None]:
        """Parses the dynamic data file from PIN engine in the 'time' mode."""
        self._file_descriptor = open(self.file_path, "r")
        self._advance()

        while self._current_entry:
            # Decide which backlog to use for the current entry and retrieve related static data
            basic_block: Optional[BasicBlockData] = None
            backlog: List[Tuple[TimeDataEntry, str]] = self.function_call_backlog
            if self.basic_blocks_only or not self._current_entry.is_function_granularity():
                backlog = self.basic_block_backlog
                basic_block = self.program_data.basic_blocks[self._current_entry.id]

            # Before an instrumentation primitive (function or basic block)
            if self._current_entry.is_located_before():
                # The entry is opening a function or a basic block - it is stored in the backlog
                # until a complementary closing entry is found
                if self._current_entry.is_function_granularity():
                    self._function_call_counter += 1

                function_caller_name: str = self._form_caller_name()
                backlog.append((self._current_entry, function_caller_name))

                # When collecting only basic blocks, each of them needs to be checked for a
                # function start in order to simulate the function calls stack.
                if (
                    self.basic_blocks_only
                    and self._function_start.expected
                    and self._function_start.is_in_same_scope(self._current_entry)
                ):
                    self._function_call_counter += 1
                    self._function_start: FunctionStart = FunctionStart(
                        expected=False, function_pid=None, function_tid=None
                    )
                    if basic_block.is_function_start():
                        # The first basic block contains a call instruction at its end. Thus,
                        # the next basic block in the same scope will be considered as a start of
                        # a function
                        self._function_start = FunctionStart(
                            expected=True,
                            function_pid=self._current_entry.pid,
                            function_tid=self._current_entry.tid,
                        )
                    self.function_call_backlog.append((self._current_entry, function_caller_name))
                elif self.basic_blocks_only:
                    if basic_block.is_function_start():
                        # The first basic block contains a call instruction at its end. Thus,
                        # the next basic block in the same scope will be considered as a start of
                        # a function
                        self._function_start = FunctionStart(
                            expected=True,
                            function_pid=self._current_entry.pid,
                            function_tid=self._current_entry.tid,
                        )
                self._advance()
                continue

            # After an instrumentation primitive (function or basic block)
            # Search the backlog for its complementary entry and emit the data for the profile
            before_entry_index = self._find_backlog_index_of_before_entry(backlog)
            if before_entry_index < 0:
                msg_to_stdout("[DEBUG]: Closing entry does not have a pair in the backlog.", 3)
                self._advance()
                continue

            before_entry, function_caller_name = backlog[before_entry_index]
            profile_data: Dict[str, Any] = self._form_profile_data(
                before_entry, self._current_entry, function_caller_name
            )
            backlog.pop(before_entry_index)
            yield profile_data

            if self.basic_blocks_only and basic_block.is_function_end():
                # This basic block ends a function, when collection only basic blocks,
                # the function call stack needs to be simulated. Thus, the function calls backlog
                # is searched for relevant entry and the data is converted to a profile entry.
                function_start_entry_index: int = self._find_backlog_index_of_parent_function()
                if function_start_entry_index < 0:
                    # TODO: exception
                    raise Exception(
                        "Could not locate parent function of a basic block "
                        "in the function backlog."
                    )
                function_start_entry, function_start_caller = self.function_call_backlog[
                    function_start_entry_index
                ]

                profile_data = self._form_profile_data(
                    function_start_entry,
                    self._current_entry,
                    function_start_caller,
                    treat_as_function=True,
                )
                self.function_call_backlog.pop(function_start_entry_index)
                yield profile_data

            self._advance()

        if self.function_call_backlog or self.basic_block_backlog:
            msg_to_stdout(
                "[DEBUG]: Unpaired entries in backlogs: "
                f"Functions - {len(self.function_call_backlog)} and "
                f"Basic blocks - {len(self.basic_block_backlog)}.",
                3,
            )

    def _find_backlog_index_of_before_entry(self, backlog: List[Tuple[TimeDataEntry, str]]) -> int:
        """Based on the current entry, finds an entry located before the same basic block (or
        function).

        :returns int: the index of the last complementary entry in the backlog or -1
        """
        for index in range(len(backlog) - 1, -1, -1):
            if backlog[index][0] == self._current_entry:
                return index
        return -1

    def _find_backlog_index_of_caller_function(self) -> int:
        """Based on current entry, finds the index of an entry with information about the
        caller function of the function or basic block represented by the current entry.

        :returns int: the index of the last complementary entry in the backlog or -1
        """
        for index in range(len(self.function_call_backlog) - 1, -1, -1):
            if self.function_call_backlog[index][0].is_in_same_scope(self._current_entry):
                return index
        return -1

    def _find_backlog_index_of_parent_function(self) -> int:
        """Based on current entry, finds the index of an entry with information about the parent
        function of the basic block. In other words, finds the entry in function calls backlog that
        represents the function that current basic block entry belongs to. Expects the current entry
        to be basic block granularity.

        :returns int: the index of the last complementary entry in the backlog or -1
        """
        if self._current_entry.granularity != Granularity.BBL:
            return -1

        for index in range(len(self.function_call_backlog) - 1, -1, -1):
            if not self.function_call_backlog[index][0].is_in_same_scope(self._current_entry):
                continue

            current_function_name: str = self.program_data.basic_blocks[
                self.function_call_backlog[index][0].id
            ].function_name
            expected_function_name: str = self.program_data.basic_blocks[
                self._current_entry.id
            ].function_name
            if current_function_name == expected_function_name:
                return index
        return -1

    def _form_caller_name(self) -> str:
        """The caller name is a path from the called function back to the main
        function represented as sequence of the function names separated by the '#' character.
        This allows creation of tree representation of the callgraph.

        :returns str: path from the caller function name of the current entry to the main function
                      separated with '#' character
        """
        if not self.function_call_backlog:
            return ""

        # Find the index of the caller The backlog can contain function entries from different
        # processes and threads, therefore the caller might not be the last entry in the backlog.
        # TODO: This might not be robust enough. What happens with a function that is the first
        #  with the tid and pid combination? - Needs to check the tid and pid existence as well
        #  in the above if statement.
        caller_index: int = self._find_backlog_index_of_caller_function()
        if caller_index < 0:
            # TODO: exception
            raise Exception("Could not locate caller of a function in backlog.")

        caller_function_entry: TimeDataEntry = self.function_call_backlog[caller_index][0]
        caller_of_caller_function: str = self.function_call_backlog[caller_index][1]

        if caller_function_entry.is_function_granularity():
            caller_function_name: str = self.program_data.functions[caller_function_entry.id].name
        else:
            # The caller function entry is in fact a basic block at the start of the function
            # when only basic blocks are collected. In this case parser operates only with the
            # basic blocks so function names need to be retrieved from the information obout
            # basic blocks of the program.
            caller_function_name = self.program_data.basic_blocks[
                caller_function_entry.id
            ].function_name

        if self._current_entry.is_function_granularity():
            function_name: str = self.program_data.functions[self._current_entry.id].name
        else:
            function_name = self.program_data.basic_blocks[self._current_entry.id].function_name

        if not caller_of_caller_function:
            # if the caller function does not have a caller it must be the root function - should
            # be main
            return caller_function_name

        if caller_function_name == function_name and self._current_entry.is_function_granularity():
            # skips recursion by voiding sequences of same names in the caller field
            return caller_of_caller_function

        # form the caller name from the last entry in the backlog
        return caller_function_name + "#" + caller_of_caller_function

    def _form_profile_data(
        self,
        start_entry: TimeDataEntry,
        end_entry: TimeDataEntry,
        caller: str,
        treat_as_function: bool = False,
    ) -> Dict[str, Any]:
        """Based on two complementary entries with information about the same basic block (or
        function), creates the perun profile data entry.

        :param TimeDataEntry start_entry: the entry before the basic block (or function)
        :param TimeDataEntry end_entry: the entry after the basic block (or function)
        :param str caller: the path of function names starting at the function (or basic block)
                           and ending at the main function
        :param bool treat_as_function: treats the entries as if they belonged to a function (creates
                                       function profile entry)

        :returns dict: a perun profile data entry
        """
        profile_data: Dict[str, Any] = start_entry.get_data_for_profile(end_entry)
        if not profile_data:
            return {}

        profile_data |= {
            "type": "mixed",
            "subtype": "time delta",
            "caller": caller,
            "workload": self.workload,
        }

        if start_entry.is_function_granularity():
            function: FunctionData = self.program_data.functions[start_entry.id]
            profile_data |= {
                "uid": self.program_data.functions[start_entry.id].name,
                # For now stores whole range to match the basic block format.
                "source-lines": list(
                    range(function.source_code_line_start, function.source_code_line_end + 1)
                ),
                "source-file": self.program_data.source_code_files[function.source_code_file_id],
            }
        elif self.basic_blocks_only and treat_as_function:
            # When collecting only basic blocks the function profile data is inferred from them
            basic_block_start: BasicBlockData = self.program_data.basic_blocks[start_entry.id]
            basic_block_end: BasicBlockData = self.program_data.basic_blocks[end_entry.id]
            profile_data |= {
                "uid": basic_block_start.function_name,
                # NOTE: For now stores whole range to match the basic block format. This is an
                # experimental way, but should work fine.
                "source-lines": list(
                    range(
                        min(basic_block_start.source_code_lines),
                        max(basic_block_end.source_code_lines) + 1,
                    )
                ),
                "source-file": self.program_data.source_code_files[
                    basic_block_start.source_code_file_id
                ],
            }
        else:
            basic_block: BasicBlockData = self.program_data.basic_blocks[start_entry.id]
            profile_data |= {
                "uid": f"BBL#{basic_block.function_name}#{start_entry.id}",
                "source-lines": basic_block.source_code_lines,
                "source-file": self.program_data.source_code_files[basic_block.source_code_file_id],
            }
        return profile_data
