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
    Arguments:
        file_handle(file): opened file handle
        timestamp(float): timestamp we are writing to file
    """
    print("Writing timestamp {}".format(timestamp))
    binary_timestamp = struct.pack('<I', round(timestamp))
    file_handle.write(binary_timestamp)


def read_timestamp_from_file(file_handle):
    """
    Arguments:
        file_handle(file): opened file handle

    Returns:
        int: timestamp
    """
    timestamp_bytes = file_handle.read(4)
    return struct.unpack('<I', timestamp_bytes)[0]


def timestamp_to_str(timestamp):
    """
    Arguments:
        timestamp(int): timestamp, that will be converted to string

    Returns:
        str: string representation of the timestamp in format %Y-%m-%d %H:%M:%S
    """
    return datetime.datetime.fromtimestamp(round(timestamp)).strftime("%Y-%m-%d %H:%M:%S")


def str_to_timestamp(date_string):
    """
    Arguments:
        date_string(str): string representation of form %Y-%m-%d %H:%M:%S

    Returns:
        int: timestamp representing the string
    """
    return time.mktime(datetime.datetime.strptime(date_string, "%Y-%m-%d %H:%M:%S").timetuple())
