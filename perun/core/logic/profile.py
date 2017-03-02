"""Functions for loading and working with the profiles.

Profiles of perun have .perf extensions and follow a JSON-like format for storing
the data about profiles. The JSON approach is good for human readability and since
the nature of perun enables one to perform efficient deltas, we can achieve good
performance.
"""

import os
import json
import time

import perun.core.logic.store as store
import perun.utils.log as perun_log

from perun.utils.helpers import SUPPORTED_PROFILE_TYPES
from perun.utils import get_module

__author__ = 'Tomas Fiedor'


def generate_profile_name(job):
    """Constructs the profile name with the extension .perf from the job.

    The profile is identified by its binary, collector, workload and the time
    it was run.

    Arguments:
        job(Job): generate profile name for file corresponding to the job

    Returns:
        str: string for the given profile that will be stored
    """
    return "{0.bin}-{0.collector}-{0.workload}-{1}.perf".format(
        job, time.strftime("%Y-%m-%d-%H-%M-%S", time.gmtime())
    )


def load_profile_from_file(file_name, is_raw_profile):
    """
    Arguments:
        file_name(str): path to the file
        is_raw_profile(bool): true if the profile is in json format already

    Returns:
        dict: JSON dictionary
    """
    if os.path.exists(file_name):
        with open(file_name, 'rb') as file_handle:
            return load_profile_from_handle(file_handle, is_raw_profile)
    else:
        perun_log.warn("file '{}' not found")
        return {}


def load_profile_from_handle(file_handle, is_raw_profile):
    """
    Arguments:
        file_handle(file): opened file handle
        is_raw_profile(bool): true if the profile is in json format already

    Returns:
        dict: JSON representation of the profile
    """
    if is_raw_profile:
        body = file_handle.read().decode('utf-8')
    else:
        # Read deflated contents and split to header and body
        contents = store.read_and_deflate_chunk(file_handle)
        header, body = contents.split('\0')
        prefix, profile_type, profile_size = header.split(' ')

        # Check the header, if the body is not malformed
        if prefix != 'profile' or profile_type not in SUPPORTED_PROFILE_TYPES or \
                len(body) != int(profile_size):
            perun_log.error("malformed profile")

    return json.loads(body)


def generate_header_for_profile(job):
    """
    TODO: Add type of the profile
    TODO: Add units of the header

    Arguments:
        job(Job): job with information about the computed profile

    Returns:
        dict: dictionary in form of {'header': {}} corresponding to the perun specification
    """
    try:
        collector = get_module('.'.join(['perun.collect', job.collector]))
    except ImportError:
        perun_log.error("could not find package for collector {}".format(job.collector))

    return {
        'type': collector.COLLECTOR_TYPE,
        'cmd': job.cmd,
        'params': job.params,
        'workload': job.workload,
        'units': [
            None
        ]
    }


def generate_collector_info(job):
    """
    Arguments:
        job(Job): job with information about the computed profile

    Returns:
        dict: dictionary in form of {'collector_info': {}} corresponding to the perun specification
    """
    return {
        'name': job.collector,
        'params': None
    }


def generate_postprocessor_info(job):
    """
    Arguments:
        job(Job): job with information about the computed profile

    Returns:
        dict: dictionary in form of {'postprocess_info': []} corresponding to the perun spec
    """
    return [
        {'name': postprocessor} for postprocessor in job.postprocessors
    ]


def generate_profile_for_job(collected_data, job):
    """
    Arguments:
        collected_data(dict): collected profile through some collector
        job(Job): job with informations about the computed profile

    Returns:
        dict: valid profile JSON file
    """
    assert 'global' in collected_data.keys() or 'snapshots' in collected_data.keys()

    profile = {}
    profile.update({'header': generate_header_for_profile(job)})
    profile.update({'collector_info': generate_collector_info(job)})
    profile.update({'postprocessors': generate_postprocessor_info(job)})
    profile.update(collected_data)
    return profile


def store_profile_at(profile, file_path):
    """
    Arguments:
        profile(dict): profile in JSON format
        file_path(str): path to the file of the profile
    """
    with open(file_path, 'w') as profile_handle:
        json.dump(profile, profile_handle, indent=2)
