"""Set of helper constants and helper named tuples for perun pcs"""

from enum import Enum
import collections

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

# List of current versions of format and magic constants
INDEX_ENTRIES_START_OFFSET = 12
INDEX_NUMBER_OF_ENTRIES_OFFSET = 8
INDEX_MAGIC_PREFIX = b'pidx'
INDEX_VERSION = 1

IndexEntry = collections.namedtuple("IndexEntry", "time checksum path offset")

# Minor Version specific things
MinorVersion = collections.namedtuple("MinorVersion", "date author email checksum desc parents")

# Profile specific stuff
SUPPORTED_PROFILE_TYPES = ['memory', 'mixed', 'time']
PROFILE_MALFORMED = 'malformed'
PROFILE_TYPE_COLOURS = {
    'time': 'blue',
    'mixed': 'cyan',
    'memory': 'white',
    PROFILE_MALFORMED: 'red'
}

HEADER_ATTRS = ['underline']
HEADER_COMMIT_COLOUR = 'green'
HEADER_INFO_COLOUR = 'grey'
HEADER_SLASH_COLOUR = 'grey'

# Raw output specific thing
RAW_KEY_COLOUR = 'magenta'
RAW_ITEM_COLOUR = 'yellow'
RAW_ATTRS = []

# Job specific
Job = collections.namedtuple("Job", "collector postprocessors bin workload args")
COLLECT_PHASE_BIN = 'blue'
COLLECT_PHASE_WORKLOAD = 'cyan'
COLLECT_PHASE_COLLECT = 'magenta'
COLLECT_PHASE_POSTPROCESS = 'yellow'
COLLECT_PHASE_ERROR = 'red'
COLLECT_PHASE_ATTRS = []
COLLECT_PHASE_ATTRS_HIGH = []


class CollectStatus(Enum):
    OK = 0
    ERROR = 1


class PostprocessStatus(Enum):
    OK = 0
    ERROR = 1
