"""Set of helper constants and helper named tuples for perun pcs"""

import re
import operator
import collections
import namedlist

from enum import Enum
from perun.utils.structs import PerformanceChange

import click

__author__ = 'Tomas Fiedor'

# File system specific
READ_CHUNK_SIZE = 1024

# Config specific constants and helpers
CONFIG_UNIT_ATTRIBUTES = {
    'collectors': ['name', 'pargs', 'kwargs'],
    'postprocessors': ['name', 'pargs', 'kwargs'],
    'bins': None,
    'workloads': None
}

# Other constants
MAXIMAL_LINE_WIDTH = 60
TEXT_ATTRS = []
TEXT_EMPH_COLOUR = 'green'
TEXT_WARN_COLOUR = 'red'


# Minor Version specific things
MinorVersion = collections.namedtuple("MinorVersion", "date author email checksum desc parents")
MajorVersion = collections.namedtuple("MajorVersion", "name head")

# Profile specific stuff
SUPPORTED_PROFILE_TYPES = ['memory', 'mixed', 'time']
PROFILE_MALFORMED = 'malformed'
PROFILE_TYPE_COLOURS = {
    'time': 'blue',
    'mixed': 'cyan',
    'memory': 'white',
    PROFILE_MALFORMED: 'red'
}
PROFILE_DELIMITER = '|'

HEADER_ATTRS = ['underline']
HEADER_COMMIT_COLOUR = 'green'
HEADER_INFO_COLOUR = 'white'
HEADER_SLASH_COLOUR = 'white'

DESC_COMMIT_COLOUR = 'white'
DESC_COMMIT_ATTRS = ['bold', 'dark']

# Raw output specific thing
RAW_KEY_COLOUR = 'magenta'
RAW_ITEM_COLOUR = 'yellow'
RAW_ATTRS = []

# Job specific
Job = namedlist.namedlist("Job", "collector postprocessors cmd workload args")

COLLECT_PHASE_CMD = 'blue'
COLLECT_PHASE_WORKLOAD = 'cyan'
COLLECT_PHASE_COLLECT = 'magenta'
COLLECT_PHASE_POSTPROCESS = 'yellow'
COLLECT_PHASE_ERROR = 'red'
COLLECT_PHASE_ATTRS = []
COLLECT_PHASE_ATTRS_HIGH = []

# Show specific
pass_profile = click.make_pass_decorator(dict)

# Degradation specific
CHANGE_CMD_COLOUR = 'magenta'
CHANGE_STRINGS = {
    PerformanceChange.Degradation: 'Degradation',
    PerformanceChange.MaybeDegradation: 'Maybe Degradation',
    PerformanceChange.NoChange: 'No Change',
    PerformanceChange.Unknown: 'Unknown',
    PerformanceChange.MaybeOptimization: 'Maybe Optimization',
    PerformanceChange.Optimization: 'Optimization'
}
CHANGE_COLOURS = {
    PerformanceChange.Degradation: 'red',
    PerformanceChange.MaybeDegradation: 'yellow',
    PerformanceChange.NoChange: 'white',
    PerformanceChange.Unknown: 'grey',
    PerformanceChange.MaybeOptimization: 'cyan',
    PerformanceChange.Optimization: 'green'
}
CHANGE_TYPE_COLOURS = {
    'time': 'blue',
    'mixed': 'cyan',
    'memory': 'white',
}
DEGRADATION_ICON = '-'
OPTIMIZATION_ICON = '+'
LINE_PARSING_REGEX = re.compile(
    r"(?P<location>.+)\s"
    r"PerformanceChange[.](?P<result>[A-Za-z]+)\s"
    r"(?P<type>\S+)\s"
    r"(?P<from>\S+)\s"
    r"(?P<to>\S+)\s"
    r"(?P<drate>\S+)\s"
    r"(?P<ctype>\S+)\s"
    r"(?P<crate>\S+)\s"
    r"(?P<minor>\S+)\s"
    r"(?P<cmdstr>.+)"
)


class CollectStatus(Enum):
    """Simple enumeration for statuses of the collectors"""
    OK = 0
    ERROR = 1


class PostprocessStatus(Enum):
    """Simple enumeration for statuses of the postprocessors"""
    OK = 0
    ERROR = 1


def first_index_of_attr(tuple_list, attr, value):
    """Helper function for getting the first index of value in list of tuples

    :param list tuple_list: list of tuples
    :param str attr: name of the attribute we are getting
    :param value: lookedup value
    :return: index of the tuple or exception
    :raises: ValueError when there is no object/tuple with attribute with given value
    """
    list_of_attributes = list(map(operator.attrgetter(attr), tuple_list))
    return list_of_attributes.index(value)


def uid_getter(uid):
    """Helper function for getting the order priority of the uid

    By default the highest priority is the executed binary or command,
    then file and package structure, then modules, objects, concrete functions
    or methods, on lines up to instruction. If we encounter unknown key, then we
    use some kind of lexicographic sorting

    :param tuple uid: the part of the uid
    :return: the rank of the uid in the ordering
    """
    uid_priority = {
        'bin': 0,
        'file': 1, 'source': 1, 'package': 1,
        'module': 2,
        'class': 3, 'struct': 3, 'structure': 3,
        'function': 4, 'func': 4, 'method': 4, 'procedure': 4,
        'line': 5,
        'instruction': 6
    }
    max_value = max(uid_priority.values())
    return uid_priority.get(
        uid[0],
        int("".join(map(str, map(lambda x: x+max_value, map(ord, uid[0])))))
    )
