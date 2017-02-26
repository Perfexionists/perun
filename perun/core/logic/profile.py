"""Functions for loading and working with the profiles.

Profiles of perun have .perf extensions and follow a JSON-like format for storing
the data about profiles. The JSON approach is good for human readability and since
the nature of perun enables one to perform efficient deltas, we can achieve good
performance.
"""

import os
import json

import perun.core.logic.store as store
import perun.utils.log as perun_log

from perun.utils.helpers import SUPPORTED_PROFILE_TYPES, PROFILE_MALFORMED

__author__ = 'Tomas Fiedor'


def load_profile_from_file(file_name):
    """
    Arguments:
        file_name(str): path to the file

    Returns:
        dict: JSON dictionary
    """
    if os.path.exists(file_name):
        with open(file_name, 'rb') as file_handle:
            return load_profile_from_handle(file_handle)
    else:
        perun_log.warn("file '{}' not found")
        return {}


def load_profile_from_handle(file_handle):
    """
    Arguments:
        file_handle(file): opened file handle

    Returns:
        dict: JSON representation of the profile
    """
    # Read deflated contents and split to header and body
    contents = store.read_and_deflate_chunk(file_handle)
    header, body = contents.split('\0')
    prefix, profile_type, profile_size = header.split(' ')

    # Check the header, if the body is not malformed
    if prefix != 'profile' or profile_type not in SUPPORTED_PROFILE_TYPES or \
            len(body) != int(profile_size):
        perun_log.error("malformed profile")

    return json.loads(body)
