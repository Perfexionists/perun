"""Functions for loading and working with the profiles.

Profiles of perun have .perf extensions and follow a JSON-like format for storing
the data about profiles. The JSON approach is good for human readability and since
the nature of perun enables one to perform efficient deltas, we can achieve good
performance.
"""

import os
import json

import perun.utils.log as perun_log

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
            return json.load(file_handle)
    else:
        perun_log.warn("file '{}' not found")
        return {}


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
        profile_prefix = profile_handle.read(7)

        # Check that it contains the 'profile' prefix
        assert profile_prefix == 'profile'

        # Skip the space
        profile_handle.read(1)

        # Read the profile type terminated by the space
        profile_type = ""
        byte = profile_handle.read(1)
        while byte != ' ':
            profile_type += byte
            byte = profile_handle.read(1)
        return profile_type
