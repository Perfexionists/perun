from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Generator, Dict, Union, List, Any, Tuple, ClassVar
from perun.utils.log import msg_to_stdout
import pprint

from perun.collect.trace.pin.scan_binary import FunctionInfo, FunctionArgument


class Location(IntEnum):
    """ Enum that represents the different locations of collected data. Differentiates the location of entry in the
    output form pin. Before or after the instrumented unit (routine or basic block)
    """
    BEFORE = 0
    AFTER = 1


class Granularity(IntEnum):
    """ Enum that represents the granularity of instrumentation. Differentiates the routines and basic block entries in
    the output form pin.
    """
    RTN = 0
    BBL = 1


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
    instructions_count: int
    source_code_file_id: int
    source_code_lines: List[int]


@dataclass
class ProgramData:
    functions: List[FunctionData]
    basic_blocks: Dict[int, BasicBlockData]

    source_code_files: List[str]

class RawTimeDataEntry:
    # TODO: Update comment
    """ Class that represents single entry (line) from pin output. The entry can contain information about routine or
    basic block.

    :ivar str name: the name of the routine (or routine containing the basic block)
    :ivar int location: determines the location of the data entry (see Location enum)
    :ivar int granularity: determines if the data entry contains routine or basic block information
    :ivar int rtn_id: identification number of the routine (or the routine containing the basic block)
    :ivar int bbl_id: identification number of the basic block (or None if the entry contains data regarding routine)
    :ivar int tid: thread ID of the thread in which routine or basic block were run.
    :ivar int pid: process ID of the process on which the collection was performed.
    :ivar int timestamp: timestamp when was the function or basic block started or finished
                         (based on location of the entry: BEFORE = started and AFTER = finished)
    :ivar int src_line: line number referring to the location in the source file where the entry originates 
    :ivar int src_line_end: line number referring to the location in the source file where the entry scope ends 
    :ivar str src_file: the source file the entry originates from 
    :ivar list args: contains arguments as FunctionArgument if the entry is before routine only and the collection of 
                     arguments was specified by the user
    """

    # The format of an entry in data emitted by the PIN collector. Format also supports function arguments at its end.
    # flags are three numbers that specify Granularity, Location and third only for basic blocks specifies if the basic
    # block ends a function (always 0 for function/routines).
    FLAGS: List[str] = ['granularity', 'location', 'function_end']
    FORMAT: List[List[str] | str] = [FLAGS, 'id', 'tid', 'pid', 'timestamp']

    def __init__(self, data: dict):
        # Flags
        self.granularity: Granularity = data['granularity']
        self.location: Location = data['location']
        self.function_end: bool | None = data['function_end'] if self.granularity == Granularity.BBL else None

        self.id: int = data['id']
        self.tid: int = data['tid']
        self.pid: int = data['pid']
        self.timestamp: int = data['timestamp']

        # additional routine entry information
        # FIXME: specify type better
        self.args: List[Any] | None = [] if self.granularity == Granularity.RTN else None  # optional arguments

    def time_delta(self, other) -> int:
        """ Calculates the time delta from two entries

        :param RawTimeDataEntry other: the data entry complementary to self
        :return int: time delta of the complementary entries
        """
        return abs(self.timestamp - other.timestamp)

    def is_located_before(self) -> bool:
        """ Identifies if the data entry is located before the instrumentation unit.
        :return bool: True if the entry is from the start of the instrumentation unit, otherwise False
        """
        return self.location == Location.BEFORE

    def is_function_granularity(self) -> bool:
        """ Identifies if the data entry is at the function (routine) granularity
        :return bool: True if the granularity of the entry is at routine level, otherwise False
        """
        return self.granularity == Granularity.RTN

    def __eq__(self, other) -> bool:
        """ Determine if two entries are complementary. Two entries are complementary when their location are opposite
        and everything else is the same.
        """
        return self.id == other.id and \
            self.tid == other.tid and self.pid == other.pid and \
            self.location != other.location

    def __repr__(self) -> str:
        return ("RAW time:\n"
                f"\tgranularity: {'Routine' if self.granularity == Granularity.RTN else 'Basic Block'}\n"
                f"\tlocation: {'Before' if self.location == Location.BEFORE else 'AFTER'}\n"
                f"\tid: {self.id}\n"
                f"\ttid: {self.tid}\n"
                f"\tpid: {self.pid}\n"
                f"\ttimestamp: {self.timestamp}\n")


@dataclass(eq=False, repr=False)
class RawMemoryDataEntry:
    # the before entry contains variable number of arguments at the end
    FORMAT_BEFORE: ClassVar[List[str]] = ['address', 'name', 'parent_address', 'parent_name', 'tid', 'pid', 'source_file', 'source_lines']
    FORMAT_AFTER: ClassVar[List[str]] = ['address', 'name', 'tid', 'pid', 'return_pointer']

    address: int
    name: str
    tid: int
    pid: int
    location: Location

    return_pointer: str | None = None
    parent_address: int | None = None
    parent_name: str | None = None
    source_file: str | None = None
    source_lines: List[int] = field(default_factory=list)

    args: List[int] = field(default_factory=list)


    def __eq__(self, other) -> bool:
        return self.address == other.address and self.name == other.name and \
               self.tid == other.tid and self.pid == other.pid and \
               self.location != other.location

    def __repr__(self):
        repr_string: str = ("RAW memory:\n"
                            f"\tlocation: {'Before' if self.location == Location.BEFORE else 'After'}\n"
                            f"\taddress: {self.address}\n"
                            f"\tname: {self.name}\n"
                            f"\ttid: {self.tid}\n"
                            f"\tpid: {self.pid}\n")
        if self.location == Location.BEFORE:
            repr_string += (f"\tparent: {self.parent_address} {self.parent_name}\n"
                            f"\tsource location: {self.source_lines} {self.source_file}\n"
                            f"\targs: {self.args}\n")
        else:
            repr_string += f"\treturn pointer: {self.return_pointer}\n"
        return repr_string



class Record(ABC):
    # TODO: update comments
    """ Class that represents 2 paired data entries created by pin. Holds information about run-time of a routine or a
    basic block along with some additional information for deeper analysis.

    :ivar str name: name of the routine (or routine containing the basic block) that the data belongs to
    :ivar int tid: thread id of the thread in which the routine or basic block run
    :ivar int pid: process id of the process in which the routine/basic block run
    :ivar int time_delta: the run-time of the routine/basic block in microseconds
    :ivar int entry_timestamp: the timestamp at which was the routine/basic block executed
    :ivar int src_line: line number referring to the line of the location in the source file the routine/basic block 
                        originates from 
    :ivar str src_file: the source file the entry originates from 
    :ivar str workload: the parameters with which was the program containing the routine/basic block executed
    """

    def __init__(self, start_entry: RawTimeDataEntry, end_entry: RawTimeDataEntry, caller: str, workload: str):
        """
        :param RawTimeDataEntry start_entry: The entry at the beginning of a function
        :param RawTimeDataEntry end_entry: The entry at the end of the same function as start_entry
        :param str workload: the workload specification of the current run 
        """
        self.tid = start_entry.tid
        self.pid = start_entry.pid
        self.time_delta = start_entry.time_delta(end_entry)
        self.entry_timestamp = start_entry.timestamp
        self.caller = caller

        self.workload = workload

    @abstractmethod
    def get_profile_data(self) -> dict:
        """ Creates the representation of the data suitable for perun profile.
        """
        pass


class FunctionCallRecord(Record):
    #TODO: update comments
    """ Class that represents the function/routine record

    :ivar int rtn_id: identification number of the routine
    :ivar int call_order: the order in which was the function called
    :ivar list args: the arguments passed to the routine in a list as FunctionArgument objects
    """

    def __init__(self, start_entry: RawTimeDataEntry, end_entry: RawTimeDataEntry,
                 caller: str, call_order: int,
                 workload: str, program_data: ProgramData):
        """
        :param RawTimeDataEntry start_entry: The entry at the beginning of a function
        :param RawTimeDataEntry end_entry: The entry at the end of the same function as start_entry
        :param str workload: the workload specification of the current run
        """
        super().__init__(start_entry, end_entry, caller, workload)
        function: FunctionData = program_data.functions[start_entry.id]

        self.name = function.name
        self.id = start_entry.id
        self.call_order = call_order
        self.args = start_entry.args

        self.src_line_start = function.source_code_line_start
        self.src_line_end = function.source_code_line_end
        self.src_file = program_data.source_code_files[function.source_code_file_id]

    def get_profile_data(self) -> dict:
        """ Creates suitable representation of the record data for the perun profile.

        :return dict: representation of data for perun profile
        """

        profile_data = {
            'workload': self.workload,
            'subtype': 'time delta',
            'type': 'mixed',
            'tid': self.tid,
            'uid': self.name,
            # 'call-order': self.call_order,
            'caller': self.caller,
            'timestamp': self.entry_timestamp,
            'amount': self.time_delta,
            'source-lines': [line for line in range(self.src_line_start, self.src_line_end+1)],
            'source-file': self.src_file,
        }

        for arg in self.args:
            profile_data[f'arg_value#{arg.index}'] = arg.value
            profile_data[f'arg_type#{arg.index}'] = arg.type
            profile_data[f'arg_name#{arg.index}'] = arg.name
        return profile_data

    def __repr__(self) -> str:
        return ('RTN:\n' 
                f'function_name:     {self.name}\n'
                f'delta:             {self.time_delta}\n'
                f'function_id:       {self.id}\n'
                f'tid:               {self.tid}\n'
                f'entry:             {self.entry_timestamp}\n'
                f'order:             {self.call_order}\n'
                f'source_line_start: {self.src_line_start}\n'
                f'source_line_end:   {self.src_line_end}\n'
                f'source_file:       {self.src_file}\n'
                f'caller_name:       {self.caller}\n'
                f'args:              {self.args}\n')


class BasicBlockRecord(Record):
    """ Class that represents the basic block record.

    :ivar int rtn_id: identification number for the routine that contains this basic block
    :ivar int bbl_id: identification number for the basic block
    :ivar int src_line_end: line number referring to location in source code where the basic block ends 
    """

    def __init__(self, start_entry: RawTimeDataEntry, end_entry: RawTimeDataEntry, caller: str,
                 workload: str, program_data: ProgramData):
        """
        :param RawTimeDataEntry start_entry: The entry at the beginning of a function
        :param RawTimeDataEntry end_entry: The entry at the end of the same function as start_entry
        :param str workload: the workload specification of the current run
        """
        super().__init__(start_entry, end_entry, caller, workload)
        basic_block: BasicBlockData = program_data.basic_blocks[start_entry.id]
        self.name: str = basic_block.function_name
        self.id: int = start_entry.id
        self.instructions_count: int = basic_block.instructions_count
        self.src_lines: List[int] = basic_block.source_code_lines
        self.src_file: str = program_data.source_code_files[basic_block.source_code_file_id]

    def get_profile_data(self) -> dict:
        """ Creates suitable representation of the record data for the perun profile.
        :return dict: representation of data for perun profile
        """
        return {
            'amount': self.time_delta,
            'timestamp': self.entry_timestamp,
            'uid': "BBL#" + self.name + "#" + str(self.id),
            'tid': self.tid,
            'caller': self.caller,
            'type': 'mixed',
            'subtype': 'time delta',
            'workload': self.workload,
            'source-lines': self.src_lines,
            'source-file': self.src_file,
            'instructions-count': self.instructions_count,
        }

    def __repr__(self) -> str:
        return ('BBL:\n'
                f'function_name:    {self.name}\n'
                f'function_caller:  {self.caller}\n'
                f'block_id:         {self.id}\n'
                f'tid:              {self.tid}\n'
                f'delta:            {self.time_delta}\n'
                f'entry:            {self.entry_timestamp}\n'
                f'source_lines:     {self.src_lines}\n'
                f'source_file:      {self.src_file}\n'
                f'instructions:     {self.instructions_count}\n')


def _form_caller_name(function_calls_backlog: List[Tuple[RawTimeDataEntry, str]], called_function_name: str, program_data: ProgramData) -> str:
    # TODO: update comments
    """ Provided the function calls list find the function that called given function. Any recursion is
    traced back to the original caller.

    :param list function_calls_backlog: a list of RawDataEntry objects representing function calls in reversed order
                                        (most recently called function at the begging of the list)
    :param str called_function_name: the name of the called function in the specified function calls backlog
    :returns str: name of the function that called the specified function
    """
    if not function_calls_backlog:
        return ""

    last_function_entry: Tuple[RawTimeDataEntry, str] = function_calls_backlog[-1]
    last_function: RawTimeDataEntry = last_function_entry[0]
    last_function_caller: str = last_function_entry[1]
    last_function_name: str = program_data.functions[last_function.id].name

    if last_function_caller == "":
        # root function - should be main
        return last_function_name

    if last_function_caller.startswith((last_function_name, called_function_name)):
        # TODO: do we need called function name at all?
        # skips recursion by voiding sequences of same names in the caller field
        return last_function_caller

    # forms the caller name from the last entry in the backlog
    return last_function_name + "#" + last_function_caller


def _parse_source_files_table(file_descriptor) -> Tuple[List[str], str | None]:
    # The table consists of entries in format: '<file_name>;<id>' and is store
    # in reverse order in the PIN output file.

    # TODO: change the order of the format and output

    source_files: List[str] = []
    current_line: str = file_descriptor.readline()

    while current_line:
        if ';' not in current_line:
            return source_files, current_line

        entry: List[str] = current_line.strip().split(';', 1)
        source_files.insert(0, entry[0])

        current_line = file_descriptor.readline()

    return source_files, current_line


def _parse_routines_table(file_descriptor, function_arguments_map: Dict[str, FunctionInfo]) -> Tuple[List[FunctionData], str | None]:
    # The table consists of entries in format: '<id>;<name>;<source_code_file_id>;<line_start>;<line_end>'
    routine_entry_format: List[str] = ['id', 'name', 'source_code_file_id',
                                       'source_code_line_start', 'source_code_line_end']

    functions: List[FunctionData] = []
    current_line: str = file_descriptor.readline()

    while current_line:
        if ';' not in current_line:
            return functions, current_line

        entry: List[str | int] = current_line.strip().split(';')
        if len(entry) != len(routine_entry_format):
            return functions, current_line

        # Convert numerical values to int
        for idx, item in enumerate(routine_entry_format):
            entry[idx] = int(entry[idx]) if 'name' != item else entry[idx]

        data: Dict[str, str | int | List[FunctionArgument]] = dict(zip(routine_entry_format, entry))
        has_collectable_arguments = function_arguments_map and data['name'] in function_arguments_map.keys()
        data['arguments'] = function_arguments_map[data['name']].arguments if has_collectable_arguments else []

        functions.append(FunctionData(**data))

        current_line = file_descriptor.readline()

    return functions, None


def _parse_basic_blocks_table(file_descriptor) -> Tuple[Dict[int, BasicBlockData], str | None]:
    # The table consists of entries in format: '<id>;<function_name>;<instructions_count>;<source_code_file_id>;<source_code_lines>'
    basic_block_entry_format: List[str] = ['id', 'function_name', 'instructions_count',
                                           'source_code_file_id', 'source_code_lines']

    basic_blocks: Dict[int, BasicBlockData] = {}
    current_line: str = file_descriptor.readline()

    while current_line:
        if ';' not in current_line:
            return basic_blocks, current_line

        entry: List[str | int] = current_line.strip().split(';')
        if len(entry) < len(basic_block_entry_format):  # variable number of source code lines at the end of the format
            return basic_blocks, current_line

        # Convert numerical values to int
        idx = 0
        # Base format values
        for key in basic_block_entry_format[:-1]:  # skips the source code lines which are handled after
            entry[idx] = int(entry[idx]) if 'function_name' != key else entry[idx]
            idx += 1

        # The variable number of line numbers at the end of entry
        line_numbers: List[int] = []
        for item in entry[len(basic_block_entry_format)-1:]:
            if not item.isnumeric():
                # unexpected format - expected lines at the end of entry
                return basic_blocks, current_line
            line_number: int = int(entry[idx])
            if line_number != 0:
                line_numbers.append(line_number)
            idx += 1

        data: Dict[str, str | int | List[int]] = dict(zip(basic_block_entry_format[:-1], entry))
        data[basic_block_entry_format[-1]] = line_numbers

        basic_blocks[entry[0]] = BasicBlockData(**data)

        current_line = file_descriptor.readline()

    return basic_blocks, None


def _parse_static_data_file(file_path: str, function_arguments_map: Dict[str, FunctionInfo]) -> ProgramData:
    print('start of static parsing')
    with open(file_path, 'r') as fd:
        current_line: str = fd.readline()

        functions_data: List[FunctionData] = []
        basic_blocks_data: Dict[int, BasicBlockData] = {}
        source_code_files: List[str] = []

        while current_line:
            is_table_separator = current_line.startswith('#')
            if is_table_separator and 'Files' in current_line:
                print('file table')
                source_code_files, next_line = _parse_source_files_table(fd)
            elif is_table_separator and 'Routines' in current_line:
                print('rtn table')
                functions_data, next_line = _parse_routines_table(fd, function_arguments_map)
            elif is_table_separator and 'Basic blocks' in current_line:
                print('bbl table')
                basic_blocks_data, next_line = _parse_basic_blocks_table(fd)
            elif is_table_separator:
                # TODO: change exception
                raise Exception('Unexpected table separator in one of the PIN output files')

            current_line = fd.readline() if not next_line else next_line

    print('end of static parsing')
    return ProgramData(functions_data, basic_blocks_data, source_code_files)


def _rindex(source: List[Tuple[RawTimeDataEntry, str]], element: RawTimeDataEntry) -> int:
    for index in range(len(source)-1, -1, -1):
        if source[index][0] == element:
            return index
    return -1

def _parse_time_mode(options: Dict[str, bool | str], dynamic_data_file: str, workload: str, program_data: ProgramData) -> Generator[Dict[str, Union[str, int]], None, None]:
    with open(dynamic_data_file, 'r') as raw_data:
        backlog_rtn: List[Tuple[RawTimeDataEntry, str]] = []
        backlog_bbl: List[Tuple[RawTimeDataEntry, str]] = []

        function_call_counter: int = 0
        entry_counter: int = 0

        for entry in raw_data:
            entry_counter += 1
            current_data_entry: RawTimeDataEntry = _parse_raw_entry(entry, program_data)

            # Decide which backlog to use based on the current data
            backlog: List[Tuple[RawTimeDataEntry, str]] = backlog_rtn if current_data_entry.is_function_granularity() else backlog_bbl

            if current_data_entry.is_located_before():
                # The entry is opening a function or basic block - it is stored in
                # the backlog until a complementary entry is found
                function_caller_name: str = ''
                if current_data_entry.is_function_granularity():
                    function_call_counter += 1
                    current_function: FunctionData = program_data.functions[current_data_entry.id]
                    function_caller_name = _form_caller_name(backlog_rtn, current_function.name, program_data)
                else:
                    current_basic_block: BasicBlockData = program_data.basic_blocks[current_data_entry.id]
                    function_caller_name = _form_caller_name(backlog_rtn, current_basic_block.function_name, program_data)

                backlog.append((current_data_entry, function_caller_name))
                continue

            # The entry is closing a function or basic block - Search the backlog
            # for its complementary entry line and emit the data about it for the profile
            other_data_entry_index: int = _rindex(backlog, current_data_entry)
            if other_data_entry_index == -1:
                msg_to_stdout('[DEBUG]: Closing entry does not have a pair in the backlog.', 3)
                continue

            other_data_entry, function_caller_name = backlog[other_data_entry_index]

            # Create new record from the pair of lines (entry point and the exit point)
            if current_data_entry.is_function_granularity():
                record = FunctionCallRecord(start_entry=other_data_entry, end_entry=current_data_entry,
                                            call_order=function_call_counter, caller=function_caller_name,
                                            workload=workload, program_data=program_data)
            else:
                record = BasicBlockRecord(start_entry=other_data_entry, end_entry=current_data_entry,
                                          caller=function_caller_name,
                                          workload=workload, program_data=program_data)
            backlog.pop(other_data_entry_index)
            yield record.get_profile_data()

        if backlog_rtn:
            msg_to_stdout(f'[DEBUG]: Routines backlog contains {len(backlog_rtn)} unpaired entries.', 3)
            #for rtn in backlog_rtn:
            #    msg_to_stdout(str(rtn), 3)

        if backlog_bbl:
            msg_to_stdout(f'[DEBUG]: Basic blocks backlog contains {len(backlog_bbl)} unpaired entries.', 3)
            ids_set = set()
            for basic_block, caller in backlog_bbl:
                ids_set.add(basic_block.id)
            for bbl_id in ids_set:
                print(program_data.basic_blocks[bbl_id])


def _parse_memory_mode(dynamic_data_file: str, workload: str) -> Generator[Dict[str, Union[str, int]], None, None]:
    with open(dynamic_data_file, 'r') as raw_data:
        backlog: List[RawMemoryDataEntry] = []

        for entry in raw_data:

            current_entry_data: List[str | int] = entry.strip().split(';')
            current_entry_size: int = len(current_entry_data)

            # convert numerical values to int
            for idx in range(current_entry_size):
                if current_entry_data[idx].isnumeric():
                    current_entry_data[idx] = int(current_entry_data[idx])

            if current_entry_size >= len(RawMemoryDataEntry.FORMAT_BEFORE):
                # parse before entry
                current_entry_base_data: List[str | int] = current_entry_data[:len(RawMemoryDataEntry.FORMAT_BEFORE)]
                current_entry_arguments_data: List[str | int] = current_entry_data[len(RawMemoryDataEntry.FORMAT_BEFORE):]
                data = dict(zip(RawMemoryDataEntry.FORMAT_BEFORE, current_entry_base_data))
                data |= {'args': current_entry_arguments_data,
                         'location': Location.BEFORE}
                before_data_entry: RawMemoryDataEntry = RawMemoryDataEntry(**data)

                if current_entry_data[1] in ['free', 'delete']:
                    # yield the profile data since free and delete don't require after entry
                    profile_data: Dict[str, str | int] = {
                        'workload': workload,
                        'type': 'memory',
                        'amount': 0,
                        'tid': before_data_entry.tid,
                        'uid': f'{before_data_entry.name}#{before_data_entry.parent_name}',
                        'caller': f'{before_data_entry.parent_name}',
                        'source-lines': before_data_entry.source_lines,
                        'source-file': before_data_entry.source_file,
                        'arg_value#0': before_data_entry.args[0],
                        'arg_type#0': 'void*',
                        'arg_name#0': 'pointer_address'
                    }
                    yield profile_data
                else:
                    # save before entry to backlog
                    backlog.append(before_data_entry)

            elif current_entry_size == len(RawMemoryDataEntry.FORMAT_AFTER):

                # parse after entry
                data: Dict[str, str | int] = dict(zip(RawMemoryDataEntry.FORMAT_AFTER, current_entry_data))
                data |= {'location': Location.AFTER}
                after_data_entry: RawMemoryDataEntry = RawMemoryDataEntry(**data)

                # match after entry to a before entry in backlog
                before_data_entry: RawMemoryDataEntry | None = None
                for index in range(len(backlog) - 1, -1, -1):
                    if backlog[index] == after_data_entry:
                        before_data_entry = backlog[index]
                        backlog.pop(index)
                        break

                amount_based_on_entry_name: int = 0
                if before_data_entry.name == 'malloc':
                    amount_based_on_entry_name = before_data_entry.args[0]
                elif before_data_entry.name == 'calloc':
                    amount_based_on_entry_name = before_data_entry.args[0] * before_data_entry.args[1]
                elif before_data_entry.name == 'realloc':
                    amount_based_on_entry_name = before_data_entry.args[1]
                elif before_data_entry.name == 'new':
                    amount_based_on_entry_name = before_data_entry.args[0]

                arg_info_based_on_entry_name: Dict[str, List[Tuple[str, str]]] = {
                    'malloc': [('size_t', 'size')],
                    'calloc': [('int', 'count'), ('size_t', 'size')],
                    'realloc': [('void*', 'pointer_address'), ('size_t', 'size')],
                    'new': [('size_t', 'size')]
                }

                # create profile data and yield it
                profile_data: Dict[str, int | str] = {
                    'workload': workload,
                    'type': 'memory',
                    'amount': amount_based_on_entry_name,
                    'tid': before_data_entry.tid,
                    'uid': f'{before_data_entry.name}#{before_data_entry.parent_name}',
                    'caller': before_data_entry.parent_name,
                    'source-lines': before_data_entry.source_lines,
                    'source-file': before_data_entry.source_file,
                    'return-value': after_data_entry.return_pointer,
                    'return-value-type': 'void*'
                }
                for idx, arg_value in enumerate(before_data_entry.args):
                    argument_info: Tuple[str, str] = arg_info_based_on_entry_name[before_data_entry.name][idx]
                    profile_data[f'arg_value#{idx}'] = arg_value
                    profile_data[f'arg_type#{idx}'] = argument_info[0]
                    profile_data[f'arg_name#{idx}'] = argument_info[1]

                yield profile_data
            else:
                # TODO: exception
                Exception('Bad pintool output format!')
        if backlog:
            # NOTE: currently the pintool produces additional duplicate before entries for malloc that are not closed
            # they are safely ignored in backlog without any information loss. Similarly, for new and delete there is a
            # duplicate call of malloc and free respectively, these are kept for time being since their parent is
            # specified as the new or delete, therefore they don't really introduce any confusion to the profile.
            msg_to_stdout('[Debug]: Unpaired memory entries in backlog.', 3)
            for entry in backlog:
                print(entry)


def _parse_instructions_mode(dynamic_data_file: str, workload: str, program_data: ProgramData) -> Generator[Dict[str, Union[str, int]], None, None]:
    yield {'a': 'b'}


def parse_data(options: Dict[str, Any], dynamic_data_file: str, static_data_file: str, workload: str,
               functions_information: list = []) -> Generator[Dict[str, Union[str, int]], None, None]:
    """ Parses the raw data output from pin and creates Records from it
    """

    # Transform function information from DWARF debug info into a map based on name
    function_arguments_map = {}
    if functions_information:
        for function_info in functions_information:
            function_arguments_map[function_info.name] = function_info

    # Parse static data
    # Combine the data collected by PIN with the DWARF info
    program_data: ProgramData = _parse_static_data_file(static_data_file, function_arguments_map)
    pprint.pprint(program_data)

    # Parse dynamic data
    if options['mode'] == 'instructions':
        yield from _parse_instructions_mode(dynamic_data_file, workload, program_data)
    elif options['mode'] == 'memory':
        yield from _parse_memory_mode(dynamic_data_file, workload)
    else:
        yield from _parse_time_mode(options, dynamic_data_file, workload, program_data)


def _parse_raw_entry(raw_entry: str, program_data: ProgramData) -> RawTimeDataEntry:
    # TODO: update comment
    """ Parse a single entry (line) from data collected by pin into a RawTimeDataEntry object.
    For now works only with time mode.

    :param str raw_entry: line from data collected by pin
    :param dict functions_map: information about functions gathered from debug information
    :returns RawDataEntry: the line represented as an object
    """

    entry: List[str] = raw_entry.strip().split(';')
    data: Dict[str, int] = {}
    data |= dict(zip(RawTimeDataEntry.FORMAT[0], [int(flag) for flag in entry[0]]))
    data |= dict(zip(RawTimeDataEntry.FORMAT[1:], [int(element) for element in entry[1:]]))
    data_entry: RawTimeDataEntry = RawTimeDataEntry(data)

    if data_entry.is_function_granularity() and len(entry) > len(RawTimeDataEntry.FORMAT):  # There are additional function arguments

        function: FunctionData = program_data.functions[data_entry.id]
        argument_values: List[str] = entry[len(RawTimeDataEntry.FORMAT):]  # Values of function arguments collected by PIN

        # Assign values to the argument info collected by the pyelftools
        for argument, value in zip(function.arguments, argument_values):
            if 'char*' in argument.type:  # Store only length of a string
                value = len(value)
            elif 'char' in argument.type:  # Store ordinal value instead of character
                value = ord(value)
            argument.value = int(value)

        data_entry.args = function.arguments

    return data_entry
