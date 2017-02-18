"""Set of helper constants and helper named tuples for perun pcs"""

import collections

__author__ = 'Tomas Fiedor'

# List of current versions of format and magic constants
INDEX_MAGIC_PREFIX = b'pidx'
INDEX_VERSION = 1

IndexEntry = collections.namedtuple("IndexEntry", "time checksum path offset")
