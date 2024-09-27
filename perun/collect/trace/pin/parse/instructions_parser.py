from typing import List, Any, ClassVar, Dict, Generator, Union
from dataclasses import dataclass

from .parser import (
    PinDynamicOutputParser,
    Granularity,
    InstrumentationLocation,
    ProgramData,
    BasicBlockData,
    BasicBlockLocation,
    DynamicDataEntry,
    FunctionStart,
)
from perun.utils.log import msg_to_stdout

# TODO: Decide if we should merge the PinInstructionOutputParser and PinTimeOutputParser into
#       one - PinDurationOutputParser


@dataclass(eq=False, repr=False)
class InstructionDataEntry(DynamicDataEntry):
    """Represents an entry with information about a basic block during program runtime. The entry
    contains data that identify the basic block and the location where was the entry taken (before
    or after).

    Note: The number of instructions is not stored in the entry because it is a static information
    (it does not change during the run-time) and therefore it is retrieved from the other data
    provided by the pin based on basic block ID.

    The format of an entry contains two flags granularity (basic block only) and location (before
    or after a basic block), and three values that identify the basic block.
    """

    FLAGS: ClassVar[List[str]] = ["granularity", "location"]
    FORMAT: ClassVar[List[Union[List[str], str]]] = [FLAGS, "id", "tid", "pid"]

    granularity: Granularity
    location: InstrumentationLocation

    id: int
    tid: int  # thread ID
    pid: int  # process ID

    def is_located_before(self) -> bool:
        """Identifies if the data entry is located before the instrumentation unit.
        :return bool: True if the entry is from the start of the instrumentation unit
        """
        return self.location == InstrumentationLocation.BEFORE

    def is_function_granularity(self):
        return self.granularity == Granularity.RTN

    def is_in_same_scope(self, other) -> bool:
        """Determine if the other entry is in the same scope, meaning that its pid and tid is
        the same.

        :param InstructionDataEntry other: the entry to compare to

        :returns bool: True if the other entry is in the same scope
        """
        return self.pid == other.pid and self.tid == other.tid

    def __eq__(self, other) -> bool:
        """Determine if two entries are complementary. Two entries are complementary when only
        their location is different.

        :param TimeDataEntry other: the entry to compare to

        :returns bool: True if the other entry is complementary
        """
        return (
            self.id == other.id
            and self.tid == other.tid
            and self.pid == other.pid
            and self.location != other.location
        )

    def __repr__(self) -> str:
        return (
            "RAW time:\n"
            f"\tgranularity: {'Routine' if self.is_function_granularity() else 'Basic Block'}\n"
            f"\tlocation: {'Before' if self.is_located_before else 'After'}\n"
            f"\tid: {self.id}\n"
            f"\ttid: {self.tid}\n"
            f"\tpid: {self.pid}\n"
        )


@dataclass
class BacklogElement:
    entry: InstructionDataEntry
    caller: str
    instructions_count: int


class PinInstructionOutputParser(PinDynamicOutputParser):
    """Parser for the 'instruction' mode of the PIN engine. It expects only basic block entries
    in the output from PIN and uses instruction count as a duration resource (amount) in the
    perun profile.
    """

    def __init__(self, dynamic_data_file: str, program_data: ProgramData, **kwargs):
        super().__init__(dynamic_data_file)
        self.workload = kwargs["workload"]
        self.program_data: ProgramData = program_data

        self.function_call_backlog: List[BacklogElement] = []
        self.basic_block_backlog: List[BacklogElement] = []

        # Notes if the start of the function is expected in the following entry. Start of a main
        # function is expected at the beginning, however, the pid and tid are not known.
        self._function_start: FunctionStart = FunctionStart(
            expected=True, function_pid=None, function_tid=None
        )
        self._function_call_counter: int = 0

    def _parse_current_dynamic_entry(self) -> InstructionDataEntry:
        """Parse a single entry (line) from data collected by PIN into a InstructionDataEntry object.

        :returns InstructionDataEntry: the raw entry converted into an object
        """
        entry: List[str] = self._current_raw_entry.strip().split(";")
        data: Dict[str, int] = dict(
            zip(InstructionDataEntry.FORMAT[0], [int(flag) for flag in entry[0]])
        )
        data |= dict(zip(InstructionDataEntry.FORMAT[1:], [int(element) for element in entry[1:]]))
        return InstructionDataEntry(**data)

    def parse_dynamic_data_file(self) -> Generator[Dict[str, Union[str, int]], None, None]:
        """Parses the dynamic data file from PIN engine in the 'instructions' mode."""
        self._file_descriptor = open(self.file_path, "r")
        self._advance()

        while self._current_entry:
            if self._current_entry.granularity != Granularity.BBL:
                # TODO: Exception
                raise Exception(
                    "The PinInstructionsParser expects only basic blocks in the dynamic "
                    "data file."
                )

            basic_block: BasicBlockData = self.program_data.basic_blocks[self._current_entry.id]

            # Before a basic block
            if self._current_entry.is_located_before():
                # The entry is opening a basic block - it is stored in the backlog until a
                # complementary closing entry is found
                function_caller_name: str = self._form_caller_name()
                self.basic_block_backlog.append(
                    BacklogElement(
                        self._current_entry, function_caller_name, basic_block.instructions_count
                    )
                )

                # Simulation of function call stack The basic blocks contain information about
                # call and return instruction presence. Based on this information the function
                # call stack is simulated in the function_calls_backlog
                is_in_scope_of_function_start: bool = (
                    self._function_start.function_pid is None
                    and self._function_start.function_tid is None
                    or (
                        self._function_start.function_pid == self._current_entry.pid
                        and self._function_start.function_tid == self._current_entry.tid
                    )
                )
                if self._function_start.expected and is_in_scope_of_function_start:
                    self._function_call_counter += 1
                    # Initial count from current basic block plus the call instruction located in
                    # previous basic block. The other instructions in the function body will be
                    # added as encountered.
                    instructions_count: int = basic_block.instructions_count + 1
                    self._function_start: FunctionStart = FunctionStart(
                        expected=False, function_pid=None, function_tid=None
                    )
                    if basic_block.location_in_function == BasicBlockLocation.FUNCTION_START:
                        # The first basic block contains a call instruction
                        instructions_count -= 1
                        self._function_start = FunctionStart(
                            expected=True,
                            function_pid=self._current_entry.pid,
                            function_tid=self._current_entry.tid,
                        )
                    self.function_call_backlog.append(
                        BacklogElement(
                            self._current_entry, function_caller_name, instructions_count
                        )
                    )
                else:
                    # find the function this basic block belongs to and update the instructions
                    # count
                    function_index: int = self._find_backlog_index_of_parent_function()
                    if function_index < 0:
                        # TODO: exception
                        raise Exception(
                            "Could not locate parent function of current basic block in backlog."
                        )
                    self.function_call_backlog[
                        function_index
                    ].instructions_count += basic_block.instructions_count
                    if basic_block.location_in_function == BasicBlockLocation.FUNCTION_START:
                        # The basic block starts a new function with a call instruction at its
                        # end. The instruction is therefore excluded from the total count for the
                        # function it belongs to and the next basic block with the same scope (
                        # tid and pid) is considered a start of a new function.
                        self.function_call_backlog[function_index].instructions_count -= 1
                        self._function_start = FunctionStart(
                            expected=True,
                            function_pid=self._current_entry.pid,
                            function_tid=self._current_entry.tid,
                        )

                self._advance()
                continue

            # After a basic block
            # Search the backlog for its complementary entry and emit the data for the profile
            before_entry_index = self._find_backlog_index_of_before_entry()
            if before_entry_index < 0:
                msg_to_stdout("[DEBUG]: Closing entry does not have a pair in the backlog.", 3)
                self._advance()
                continue

            before_entry: InstructionDataEntry = self.basic_block_backlog[before_entry_index].entry
            caller_name: str = self.basic_block_backlog[before_entry_index].caller
            profile_data: Dict[str, Any] = self._form_profile_data(
                before_entry, self._current_entry, caller_name
            )
            self.basic_block_backlog.pop(before_entry_index)
            yield profile_data

            if basic_block.location_in_function == BasicBlockLocation.FUNCTION_END:
                # This basic block ends a function, when collection only basic blocks,
                # the function call stack needs to be simulated. Thus, the function calls backlog
                # is searched for relevant entry and the data is converted to a profile entry.
                function_start_entry_index: int = self._find_backlog_index_of_parent_function()
                if function_start_entry_index < 0:
                    # TODO: exception
                    raise Exception(
                        "Could not locate parent function of current basic block in backlog."
                    )
                function_start: BacklogElement = self.function_call_backlog[
                    function_start_entry_index
                ]
                profile_data = self._form_profile_data(
                    function_start.entry,
                    self._current_entry,
                    function_start.caller,
                    treat_as_function=True,
                    instructions_amount_in_function=function_start.instructions_count,
                )
                self.function_call_backlog.pop(function_start_entry_index)

                # find the function this function was called by (based on the scope - tid and
                # pid) and increment its instructions counter NOTE: This means that the main
                # function will contain count of all executed instructions
                if self.function_call_backlog:
                    function_index: int = self._find_backlog_index_of_caller_function()
                    self.function_call_backlog[
                        function_index
                    ].instructions_count += function_start.instructions_count
                yield profile_data

            self._advance()

        if self.function_call_backlog or self.basic_block_backlog:
            msg_to_stdout(
                "[DEBUG]: Unpaired entries in backlogs: "
                f"Functions - {len(self.function_call_backlog)} and "
                f"Basic blocks - {len(self.basic_block_backlog)}.",
                3,
            )

    def _find_backlog_index_of_before_entry(self) -> int:
        """Based on the current entry, finds an entry located before the same basic block.
        Since the backlog contains only entries located before a basic block, this function
        expects the current entry to be located after a basic block when called.

        :returns int: the index of the last complementary entry in the backlog or -1
        """
        # TODO: since the -1 is valid index, we should maybe change the return value to None
        if self._current_entry.is_located_before():
            return -1

        for index in range(len(self.basic_block_backlog) - 1, -1, -1):
            if self.basic_block_backlog[index].entry == self._current_entry:
                return index
        return -1

    def _find_backlog_index_of_caller_function(self) -> int:
        """Based on current entry, finds the index of an entry with information about the
        caller function of the function current basic block belongs to.

        Note: This is required to distinguish between different combinations of PIDs and
        TIDs in the backlog.

        :returns int: the index of the last complementary entry in the backlog or -1
        """
        # TODO: since the -1 is valid index, we should maybe change the return value to None
        for index in range(len(self.function_call_backlog) - 1, -1, -1):
            if self.function_call_backlog[index].entry.is_in_same_scope(self._current_entry):
                return index

        # TODO: exception
        raise Exception("Could not locate caller of a function in backlog.")

    def _find_backlog_index_of_parent_function(self) -> int:
        """Based on current entry, finds the index of an entry with information about the parent
        function of the basic block in the current entry. Expects the current entry to be basic
        block granularity when called.

        :returns int: the index of the last complementary entry in the backlog or -1
        """
        # TODO: since the -1 is valid index, we should maybe change the return value to None
        if self._current_entry.granularity != Granularity.BBL:
            return -1

        for index in range(len(self.function_call_backlog) - 1, -1, -1):
            if not self.function_call_backlog[index].entry.is_in_same_scope(self._current_entry):
                continue

            function_id: int = self.function_call_backlog[index].entry.id
            function_name: str = self.program_data.basic_blocks[function_id].function_name
            expected_function_name: str = self.program_data.basic_blocks[
                self._current_entry.id
            ].function_name
            if function_name == expected_function_name:
                return index
        return -1

    def _form_profile_data(
        self,
        start_entry: InstructionDataEntry,
        end_entry: InstructionDataEntry,
        caller: str,
        treat_as_function: bool = False,
        instructions_amount_in_function: int = 0,
    ) -> Dict[str, Any]:
        """Based on two complementary entries with information about the same basic block,
        creates the perun profile data entry.

        :param InstructionDataEntry start_entry: the entry before the basic block
        :param InstructionDataEntry end_entry: the entry after the basic block
        :param str caller: the path of function names from the function the basic block belongs to,
                           to the main function
        :param bool treat_as_function: treats the entries as if they belonged to a function (creates
                                       function profile entry)
        :param int instructions_amount_in_function: number of instruction in the function
                                                    represented by the entries

        :returns dict: a perun profile data entry
        """

        basic_block_start: BasicBlockData = self.program_data.basic_blocks[start_entry.id]
        basic_block_end: BasicBlockData = self.program_data.basic_blocks[end_entry.id]

        profile_data: Dict[str, Any] = {
            "type": "mixed",
            "subtype": "time delta",
            "caller": caller,
            "workload": self.workload,
            "tid": start_entry.tid,
            "pid": start_entry.tid,
        }

        if treat_as_function:
            # Creates an function profile entry from a basic block entries
            profile_data |= {
                "uid": basic_block_start.function_name,
                "amount": instructions_amount_in_function,
                # NOTE: For now stores whole range to match the basic block format. This is an
                # experimental way.
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
            profile_data |= {
                "uid": f"BBL#{self.program_data.basic_blocks[start_entry.id].function_name}#{start_entry.id}",
                "amount": basic_block_start.instructions_count,
                "source-lines": basic_block_start.source_code_lines,
                "source-file": self.program_data.source_code_files[
                    basic_block_start.source_code_file_id
                ],
            }
        return profile_data

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
        #  with the tid and pid combination? Needs some testing on application with different tid
        #  and pid.
        caller_index: int = self._find_backlog_index_of_caller_function()
        caller_function_entry: InstructionDataEntry = self.function_call_backlog[caller_index].entry
        caller_of_caller_function: str = self.function_call_backlog[caller_index].caller
        caller_function_name: str = self.program_data.get_function_name(
            caller_function_entry.id, Granularity.BBL
        )

        if not caller_of_caller_function:
            # if the caller function does not have a caller it must be the root function - should
            # be main
            return caller_function_name

        if caller_of_caller_function.startswith(caller_function_name):
            # skips recursion by voiding sequences of same names in the caller field
            return caller_of_caller_function

        # form the caller name from the last entry in the backlog
        return caller_function_name + "#" + caller_of_caller_function
