from abc import ABC, abstractmethod
from enum import IntEnum
from typing import Generator, Dict, Union

from perun.collect.trace.pin.scan_binary import FunctionInfo


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


class RawDataEntry:
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
    :ivar list args: contains arguments as FunctionArgument if the entry is before routine only and the collection of 
                     arguments was specified by the user
    """

    # RTN_FORMAT also supports function arguments at the end
    RTN_FORMAT = ["granularity", 'location', 'tid', 'pid', 'timestamp', 'rtn_id', 'name']
    BBL_FORMAT = [*RTN_FORMAT, 'bbl_id']

    def __init__(self, data: dict):
        self.name = data['name']
        self.location = data['location']
        self.granularity = data['granularity']
        self.rtn_id = data['rtn_id']
        self.tid = data['tid']
        self.pid = data['pid']
        self.timestamp = data['timestamp']

        self.bbl_id = data['bbl_id'] if self.granularity == Granularity.BBL else None
        self.args = []

    def time_delta(self, other) -> int:
        """ Calculates the time delta from two entries

        :param RawDataEntry other: the data entry complementary to self
        :return int: time delta of the complementary entries
        """
        return abs(self.timestamp - other.timestamp)

    def is_located_before(self) -> bool:
        """ Identifies if the data entry is located before instrumentation unit.
        :return bool: True if the entry is from the entrance to the instrumentation unit, otherwise False
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
        return self.rtn_id == other.rtn_id and self.bbl_id == other.bbl_id and \
               self.name == other.name and \
               self.tid == other.tid and self.pid == other.pid and \
               self.location != other.location

    def __repr__(self) -> str:
        return ("RAW:\n"
                f"function_name: {self.name}\n"
                f"granularity: {self.granularity}\n"
                f"location: {self.location}\n"
                f"function_id: {self.rtn_id}\n"
                f"basic_block_id: {self.bbl_id}\n"
                f"tid: {self.tid}\n"
                f"pid: {self.pid}\n"
                f"timestamp: {self.timestamp}\n")


class Record(ABC):
    """ Class that represents 2 paired data entries created by pin. Holds information about run-time of a routine or a
    basic block along with some additional information for deeper analysis.

    :ivar str name: name of the routine (or routine containing the basic block) that the data belongs to
    :ivar int tid: thread id of the thread in which the routine or basic block run
    :ivar int pid: process id of the process in which the routine/basic block run
    :ivar int time_delta: the run-time of the routine/basic block in microseconds
    :ivar int entry_timestamp: the timestamp at which was the routine/basic block executed
    :ivar str workload: the parameters with which was the program containing the routine/basic block executed
    """

    def __init__(self, start_entry: RawDataEntry, end_entry: RawDataEntry, workload: str):
        """
        :param RawDataEntry start_entry: The entry at the beginning of a function
        :param RawDataEntry end_entry: The entry at the end of the same function as start_entry
        :param str workload: the workload specification of the current run 
        """
        self.name = start_entry.name
        self.tid = start_entry.tid
        self.pid = start_entry.pid
        self.time_delta = start_entry.time_delta(end_entry)
        self.entry_timestamp = start_entry.timestamp

        self.workload = workload 

    @abstractmethod
    def get_profile_data(self) -> dict:
        """ Creates the representation of the data suitable for perun profile.
        """
        pass


class FunctionCallRecord(Record):
    """ Class that represents the function/routine record

    :ivar int rtn_id: identification number of the routine
    :ivar int call_order: the order in which was the function called
    :ivar list args: the arguments passed to the routine in a list as FunctionArument objects
    """

    def __init__(self, start_entry: RawDataEntry, end_entry: RawDataEntry, workload: str, call_order: int):
        """
        :param RawDataEntry start_entry: The entry at the beginning of a function
        :param RawDataEntry end_entry: The entry at the end of the same function as start_entry
        :param str workload: the workload specification of the current run
        """
        super().__init__(start_entry, end_entry, workload)
        self.rtn_id = start_entry.rtn_id
        self.call_order = call_order
        self.args = start_entry.args

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
            #'call-order': self.call_order,
            'timestamp': self.entry_timestamp,
            'amount': self.time_delta
        }

        for arg in self.args:
            profile_data[f'arg_value#{arg.index}'] = arg.value
            profile_data[f'arg_type#{arg.index}'] = arg.type
            profile_data[f'arg_name#{arg.index}'] = arg.name
        return profile_data

    def __repr__(self) -> str:
        repr_str = ('RTN:\n' f'function_name:  {self.name}\n' f'delta:          {self.time_delta}\n'
                    f'function_id:    {self.rtn_id}\n'
                    f'tid:            {self.tid}\n'
                    f'entry:          {self.entry_timestamp}\n'
                    f'order:          {self.call_order}\n'
                    f'args:           {self.args}\n')
        return repr_str


class BasicBlockRecord(Record):
    """ Class that represents the basic block record.

    :ivar int rtn_id: identification number for the routine that contains this basic block
    :ivar int bbl_id: identification number for the basic block
    """
    def __init__(self, start_entry: RawDataEntry, end_entry: RawDataEntry, workload: str):
        """
        :param RawDataEntry start_entry: The entry at the beginning of a function
        :param RawDataEntry end_entry: The entry at the end of the same function as start_entry
        :param str workload: the workload specification of the current run
        """
        super().__init__(start_entry, end_entry, workload)
        self.rtn_id = start_entry.rtn_id
        self.bbl_id = start_entry.bbl_id

    def get_profile_data(self) -> dict:
        """ Creates suitable representation of the record data for the perun profile.
        :return dict: representation of data for perun profile
        """
        return {
            'amount': self.time_delta,
            'timestamp': self.entry_timestamp,
            'uid': "BBL#" + self.name + "#" + str(self.bbl_id),
            'tid': self.tid,
            'type': 'mixed',
            'subtype': 'time delta',
            'workload': self.workload
        }

    def __repr__(self) -> str:
        return ('BBL:\n'
                f'function_name:  {self.name}\n'
                f'function_id:    {self.rtn_id}\n'
                f'block_id:       {self.bbl_id}\n'
                f'tid:            {self.tid}\n'
                f'delta:          {self.time_delta}\n'
                f'entry:          {self.entry_timestamp}\n')


def parse_data(file: str, workload: str, functions_information: list = []) -> Generator[Dict[str, Union[str, int]], None, None]:
    """ Parses the raw data output from pin and creates Records from it which 
    are then converted to perun profile
    """

    # Transform function information into a map based on name
    functions_map = {}
    if functions_information:
        for function_info in functions_information:
            functions_map[function_info.name] = function_info


    with open(file, 'r') as raw_data:
        backlog_rtn = []
        backlog_bbl = []

        function_call_counter = 0
        entry_counter = 0

        for entry in raw_data:
            entry_counter += 1

            data = _parse_raw_entry(entry, functions_map)

            # Decide which backlog to use based on the current data
            if data.is_function_granularity():
                function_call_counter += 1
                backlog = backlog_rtn
            else:
                backlog = backlog_bbl

            if not data.is_located_before():
                # Search backlog for its complementary (entry point) line
                if data in backlog:
                    data_entry_index = backlog.index(data)
                    data_entry = backlog[data_entry_index]

                    # Create new record from the pair of lines (entry point and the exit point)
                    if data.is_function_granularity():
                        record = FunctionCallRecord(start_entry=data_entry, end_entry=data, 
                                                    workload=workload, call_order=function_call_counter)
                    else:
                        record = BasicBlockRecord(start_entry=data_entry, end_entry=data, workload=workload)

                    backlog.pop(data_entry_index)
                    yield record.get_profile_data()
            else:
                # Stash entry point line, so that it can be easily found when complementary line (exit point) is loaded.
                # It's necessary to insert at the beginning of the array so that recursive functions are paired correctly
                backlog.insert(0, data)


def _parse_raw_entry(raw_entry: str, functions_map: Dict[str, FunctionInfo]) -> RawDataEntry:
    """ Parse a single entry (line) from data collected by pin into a RawDataEntry object. 

    :param str raw_entry: line from data collected by pin
    :param  raw_entry: line from data collected by pin
    :returns RawDataEntry: the line represented as an object
    """

    entry = raw_entry.strip('\n').split(';')
    current_format = RawDataEntry.BBL_FORMAT if int(entry[0]) == Granularity.BBL else RawDataEntry.RTN_FORMAT
    data = {}

    # An entry always contains integers and a single string, the name of the function
    for key, value in zip(current_format, entry):
        data[key] = int(value) if key != 'name' else value
    data = RawDataEntry(data)

    if functions_map and len(entry) > len(current_format):  # There are additional function arguments

        function = functions_map[data.name]  # Information about function collected by pyelftools
        argument_values = entry[len(current_format):]  # Values of function arguments collected by PIN

        # Assign values to the argument info collected by the pyelftools
        for argument, value in zip(function.arguments, argument_values):
            if 'char*' in argument.type:  # Store only length of a string
                value = len(value)
            elif 'char' in argument.type:  # Store ordinal value instead of character
                value = ord(value)
            argument.value = int(value)

        data.args = function.arguments

    return data