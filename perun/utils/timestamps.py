"""Helper module for working with timestamps within the perun.

Contains helper functions for working with file timestamps, for efficient
writing of the timestamp to file, converting to string format, etc.
"""

import datetime
import struct
import time

__author__ = 'Tomas Fiedor'


def write_timestamp(file_handle, timestamp):
    """Helper function for writing timestamp into the file

    :param file file_handle: opened file handle
    :param float timestamp: timestamp we are writing to file
    """
    binary_timestamp = struct.pack('<I', round(timestamp))
    file_handle.write(binary_timestamp)


def read_timestamp_from_file(file_handle):
    """
    :param file file_handle: opened file handle
    :returns int: timestamp
    """
    timestamp_bytes = file_handle.read(4)
    return struct.unpack('<I', timestamp_bytes)[0]


def timestamp_to_str(timestamp):
    """
    :param int timestamp: timestamp, that will be converted to string
    :returns str: string representation of the timestamp in format %Y-%m-%d %H:%M:%S
    """
    return datetime.datetime.fromtimestamp(round(timestamp)).strftime("%Y-%m-%d %H:%M:%S")


def str_to_timestamp(date_string):
    """
    :param str date_string: string representation of form %Y-%m-%d %H:%M:%S
    :returns int: timestamp representing the string
    """
    return time.mktime(datetime.datetime.strptime(date_string, "%Y-%m-%d %H:%M:%S").timetuple())
