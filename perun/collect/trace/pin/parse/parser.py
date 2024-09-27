from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, Union, List, TextIO, Callable, Optional, Type, TypeVar

from perun.collect.trace.pin.scan_binary import FunctionArgument, FunctionInfo
from perun.utils.log import msg_to_stdout

TABLE_SEPARATOR_MARK = "#"
ENTRY_VALUE_SEPARATOR = ";"


class InstrumentationLocation(IntEnum):
    """Enum that represents the different locations of collected data. Differentiates the location
    of entry in the output form pin. Before or after the instrumented unit (routine or basic block)
    """

    BEFORE = 0
    AFTER = 1


class Granularity(IntEnum):
    """Enum that represents the granularity of instrumentation. Differentiates the routines RTN
    (functions) and basic block BBL entries in the output form pin.
    """

    RTN = 0
    BBL = 1


class BasicBlockLocation(IntEnum):
    """Enum that represents position of a basic block in a function. Differentiates the basic block
    entries in the output form pin.

    FUNCTION_START - Basic block that starts a function contains the call instruction. Note that
    this basic block is a part of the body of the current function and the function it calls will
    be in the next basic block.

    FUNCTION_END - Basic blocks that ends a function contains the return instruction.

    FUNCTION_BODY - Any other basic block.
    """

    FUNCTION_START = 0
    FUNCTION_BODY = 1
    FUNCTION_END = 2


@dataclass
class FunctionData:
    id: int
    name: str
    source_code_file_id: int
    source_code_line_start: int
    source_code_line_end: int

    arguments: List[FunctionArgument]


@dataclass
class BasicBlockData:
    id: int
    function_name: str
    location_in_function: BasicBlockLocation
    instructions_count: int
    source_code_file_id: int
    source_code_lines: List[int]

    def is_function_end(self):
        return self.location_in_function == BasicBlockLocation.FUNCTION_END

    def is_function_start(self):
        return self.location_in_function == BasicBlockLocation.FUNCTION_START


class DynamicDataEntry:
    pass


DynamicEntry = TypeVar("DynamicEntry", bound=DynamicDataEntry)


@dataclass
class ProgramData:
    functions: List[FunctionData] = field(default_factory=list)
    basic_blocks: Dict[int, BasicBlockData] = field(default_factory=dict)

    source_code_files: List[str] = field(default_factory=list)

    def get_function_name(self, identifier: int, granularity: Granularity.RTN) -> str:
        function_name: str = ""
        if granularity == Granularity.BBL and identifier in self.basic_blocks:
            function_name = self.basic_blocks[identifier].function_name
        elif granularity == Granularity.RTN and identifier < len(self.functions):
            function_name = self.functions[identifier].name
        return function_name


@dataclass()
class FunctionStart:
    expected: bool
    function_pid: Optional[int]
    function_tid: Optional[int]

    def is_in_same_scope(self, data_entry: DynamicEntry) -> bool:
        """Determine if provided entry matches the scope in which a new function is expected to
        start.

        :param DynamicDataEntry data_entry: a data entry from PIN output

        :returns bool: True if the provided entry matches expected scope
        """

        # if there is no scope the program just started and main function is expected
        no_scope: bool = self.function_pid is None and self.function_tid is None
        data_entry_scope_matches: bool = (
            self.function_pid == data_entry.pid and self.function_tid == data_entry.tid
        )
        return no_scope or data_entry_scope_matches


class PinStaticOutputParser:
    """Parser for the static information collected by the PIN tracer engine. The static information
    remains unchanged during the whole program execution, therefore it is separated to decrease
    repetitive output.

    :ivar str file_path: the path to the file containing static data collected by pintool
    :ivar dict function_information: the information gathered about the function and its
                                     arguments before the collection process
    """

    def __init__(
        self, static_data_file: str, function_information: Dict[str, FunctionInfo] = None
    ) -> None:
        """Initialize a parser of the static information gathered during the collection of PIN
        engine.

        :param str static_data_file: the path to the file that contains static information about
                                     routines, basic blocks, and source code files
        :param dict function_information: the information about functions gathered
                                          before the PIN engine collection
        """
        self.file_path: str = static_data_file
        self.function_information: Dict[str, FunctionInfo] = function_information

        self._file_descriptor: Optional[TextIO] = None
        self._current_line: str = ""

        self._program_data: ProgramData = ProgramData()

    def _advance(self) -> None:
        self._current_line = ""
        if self._file_descriptor is not None:
            self._current_line = self._file_descriptor.readline()

    def parse_static_data(self) -> ProgramData:
        """Parses the static data file generated by PIN and returns generic information about
        the program.

        :returns ProgramData: an object containing the program's function and basic block data
        """
        self._file_descriptor = open(self.file_path, "r")
        self._advance()

        table_parsers: Dict[str, Callable] = {
            "Files": self._parse_source_files_table,
            "Routines": self._parse_routines_table,
            "Basic blocks": self._parse_basic_blocks_table,
        }

        while self._current_line:
            is_table_separator: bool = self._current_line.startswith(TABLE_SEPARATOR_MARK)

            if not is_table_separator:
                self._advance()
                continue

            table_name: str = self._current_line.strip().lstrip(TABLE_SEPARATOR_MARK)
            if table_name in table_parsers.keys():
                table_parser: Callable = table_parsers[table_name]
                table_parser()  # reads next line before finishing
            else:
                msg_to_stdout(f"[Debug]: Skipping table with unknown separator: #{table_name}", 3)
                self._advance()

        self._file_descriptor.close()
        return self._program_data

    def _parse_source_files_table(self) -> None:
        """Parses the source files table that contains absolute paths to source code files.

        The table consists of entries in format: '<file_name>;<id>' and is store
        in reverse order in the PIN output file.

        TODO: change the order of the format and output (requires pintool changes)
        """
        source_files: List[str] = []
        self._advance()

        while self._current_line:
            if ENTRY_VALUE_SEPARATOR not in self._current_line:
                # The sequence of the table entries has ended
                break

            entry: List[str] = self._current_line.strip().split(ENTRY_VALUE_SEPARATOR, 1)
            source_files.insert(0, entry[0])
            self._advance()

        self._program_data.source_code_files = source_files

    def _parse_routines_table(self) -> None:
        """Parses the routines table that contains static information about collected functions.

        The table consists of entries in format:
            '<id>;<name>;<source_code_file_id>;<line_start>;<line_end>'
        """
        entry_format: List[str] = [
            "id",
            "name",
            "source_code_file_id",
            "source_code_line_start",
            "source_code_line_end",
        ]
        functions: List[FunctionData] = []
        self._advance()

        while self._current_line:
            if ENTRY_VALUE_SEPARATOR not in self._current_line:
                self._program_data.functions = functions
                return

            entry: List[Union[str, int]] = self._current_line.strip().split(ENTRY_VALUE_SEPARATOR)
            if len(entry) != len(entry_format):
                # format does no longer match therefore end the parsing of this table
                break

            # Convert numerical values to int
            for idx, item in enumerate(entry_format):
                entry[idx] = int(entry[idx]) if "name" != item else entry[idx]

            data: Dict[str, Union[str, int, List[FunctionArgument]]] = dict(
                zip(entry_format, entry)
            )
            data["arguments"] = []
            if data["name"] in self.function_information:  # has collectable arguments
                data["arguments"] = self.function_information[data["name"]].arguments
            functions.append(FunctionData(**data))

            self._advance()

        self._program_data.functions = functions

    def _parse_basic_blocks_table(self) -> None:
        """Parses the basic blocks table that contains static information about collected basic
        blocks.

        The table consists of entries in format:
            '<id>;<function_name>;<instructions_count>;<source_code_file_id>;<source_code_lines>'
        """
        entry_format: List[str] = [
            "id",
            "function_name",
            "location_in_function",
            "instructions_count",
            "source_code_file_id",
            "source_code_lines",
        ]
        entry_format_size: int = len(entry_format)

        basic_blocks: Dict[int, BasicBlockData] = {}
        self._advance()

        while self._current_line:
            if ENTRY_VALUE_SEPARATOR not in self._current_line:
                break

            entry: List[Union[str, int]] = self._current_line.strip().split(ENTRY_VALUE_SEPARATOR)
            if len(entry) < entry_format_size:
                # Expected at least one source code line number at the end
                break

            # Convert numerical values to int
            # Base format values - skips the source code lines which are handled after
            for idx, key in enumerate(entry_format[:-1]):
                entry[idx] = int(entry[idx]) if "function_name" != key else entry[idx]

            # The variable number of source code line numbers at the end of entry
            line_numbers: List[int] = []
            for idx, item in enumerate(entry[entry_format_size - 1 :]):
                idx = idx + entry_format_size - 1  # adjust to the entry space
                if not item.isnumeric():
                    # unexpected format - expected source code line numbers at the end of an entry
                    self._program_data.basic_blocks = basic_blocks
                    return
                line_number: int = int(entry[idx])
                if line_number != 0:
                    line_numbers.append(line_number)

            data: Dict[str, Union[str, int, List[int]]] = dict(zip(entry_format[:-1], entry))
            data[entry_format[-1]] = line_numbers
            basic_blocks[entry[0]] = BasicBlockData(**data)

            self._advance()

        self._program_data.basic_blocks = basic_blocks


class PinDynamicOutputParser(ABC):
    """Parser for the dynamic information collected by the PIN tracer engine. The dynamic
    information changes during the whole program execution dynamically.

    :ivar str file_path: the path to the file containing static data collected by pintool
    """

    def __init__(self, dynamic_data_file: str):
        """Initialize a parser of the dynamic information gathered during the collection of PIN
        engine.

        :param str dynamic_data_file: the path to the file that contains dynamic information about
                                      routines and/or basic blocks
        """
        self.file_path: str = dynamic_data_file

        self._file_descriptor: Optional[TextIO] = None
        self._current_raw_entry: str = ""
        self._current_entry: Optional[Type[DynamicEntry]] = None
        self._entry_counter: int = 0

    def _advance(self) -> None:
        """Reads the next line from the file and parses it as a dynamic entry."""
        self._current_raw_entry = ""
        if self._file_descriptor is not None:
            self._current_raw_entry = self._file_descriptor.readline()

        # Parse the line and update counter
        self._current_entry = None
        if self._current_raw_entry:
            self._current_entry = self._parse_current_dynamic_entry()
            self._entry_counter += 1

    @abstractmethod
    def _parse_current_dynamic_entry(self) -> DynamicEntry:
        pass

    @abstractmethod
    def parse_dynamic_data_file(self):
        pass
