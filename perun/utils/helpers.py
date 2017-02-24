"""Set of helper constants and helper named tuples for perun pcs"""

import collections

__author__ = 'Tomas Fiedor'

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
SUPPORTED_PROFILE_TYPES = ['time', 'memory', 'mixed']
PROFILE_MALFORMED = 'malformed'
