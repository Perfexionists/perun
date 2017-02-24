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
        with open(file_name, 'r') as file_handle:
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
    return json.load(file_handle)


def peek_profile_type(profile_name):
    """Retrieves from the binary file the type of the profile from the header.

    Peeks inside the binary file of the profile_name and returns the type of the
    profile, without reading it whole.
    Arguments:
        profile_name(str): filename of the profile

    Returns:
        str: type of the profile
    """
    with open(profile_name, 'rb') as profile_handle:
        profile_chunk = store.read_and_deflate_chunk(profile_handle, 64)
        prefix, profile_type, *_ = profile_chunk.split(" ")

        # Return that the stored profile is malformed
        if prefix != 'profile' or profile_type not in SUPPORTED_PROFILE_TYPES:
            return PROFILE_MALFORMED
        else:
            return profile_type

