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

from perun.utils.exceptions import IncorrectProfileFormatException
from perun.utils.helpers import SUPPORTED_PROFILE_TYPES, Unit, Job
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
    return "{0}-{1}-{2}-{3}.perf".format(
        os.path.split(job.cmd)[-1],
        job.collector.name,
        os.path.split(job.workload)[-1],
        time.strftime("%Y-%m-%d-%H-%M-%S", time.gmtime())
    )


def load_profile_from_file(file_name, is_raw_profile):
    """
    Arguments:
        file_name(str): path to the file
        is_raw_profile(bool): true if the profile is in json format already

    Returns:
        dict: JSON dictionary

    Raises:
        IncorrectProfileFormatException: when the profile file does not exist
    """
    if not os.path.exists(file_name):
        raise IncorrectProfileFormatException(file_name, "file '{}' not found")

    with open(file_name, 'rb') as file_handle:
        return load_profile_from_handle(file_name, file_handle, is_raw_profile)


def load_profile_from_handle(file_name, file_handle, is_raw_profile):
    """
    Fixme: Add check that the loaded profile is in valid format!!!

    Arguments:
        file_name(str): name of the file opened in the handle
        file_handle(file): opened file handle
        is_raw_profile(bool): true if the profile is in json format already

    Returns:
        dict: JSON representation of the profile

    Raises:
        IncorrectProfileFormatException: when the profile cannot be parsed by json.loads(body)
            or when the profile is not in correct supported format or when the profile is malformed
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
            raise IncorrectProfileFormatException(file_name, "malformed profile '{}'")

    # Try to load the json, if there is issue with the profile
    try:
        return json.loads(body)
    except ValueError:
        raise IncorrectProfileFormatException(file_name, "profile '{}' is not in profile format")


def generate_header_for_profile(job):
    """
    TODO: Add units of the header

    Arguments:
        job(Job): job with information about the computed profile

    Returns:
        dict: dictionary in form of {'header': {}} corresponding to the perun specification
    """
    try:
        collector = get_module('.'.join(['perun.collect', job.collector.name]))
    except ImportError:
        perun_log.error("could not find package for collector {}".format(job.collector.name))

    return {
        'type': collector.COLLECTOR_TYPE,
        'cmd': job.cmd,
        'params': job.args,
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
        'name': job.collector.name,
        'params': job.collector.params
    }


def generate_postprocessor_info(job):
    """
    Arguments:
        job(Job): job with information about the computed profile

    Returns:
        dict: dictionary in form of {'postprocess_info': []} corresponding to the perun spec
    """
    return [
        {
            'name': postprocessor.name,
            'params': postprocessor.params
        } for postprocessor in job.postprocessors
    ]


def finalize_profile_for_job(pcs, collected_data, job):
    """
    Arguments:
        pcs(PCS): wrapped perun control system
        collected_data(dict): collected profile through some collector
        job(Job): job with informations about the computed profile

    Returns:
        dict: valid profile JSON file
    """
    assert 'global' in collected_data.keys() or 'snapshots' in collected_data.keys()

    profile = {'origin': pcs.get_head()}
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


def to_string(profile):
    """Converts profile from dictionary to string

    Arguments:
        profile(dict): profile we are converting to string

    Returns:
        str: string representation of profile
    """
    return json.dumps(profile)


def extract_job_from_profile(profile):
    """Extracts information from profile about job, that was done to generate the profile.

    Fixme: Add assert that profile is profile
    Arguments:
        profile(dict): dictionary with valid profile

    Returns:
        Job: job according to the profile informations
    """
    assert 'collector_info' in profile.keys()
    collector_record = profile['collector_info']
    collector = Unit(collector_record['name'], collector_record['params'])

    assert 'postprocessors' in profile.keys()
    posts = []
    for postprocessor in profile['postprocessors']:
        posts.append(Unit(postprocessor['name'], postprocessor['params']))

    assert 'header' in profile.keys()
    cmd = profile['header']['cmd']
    params = profile['header']['params']
    workload = profile['header']['workload']

    return Job(collector, posts, cmd, workload, params)


class ProfileInfo(object):
    """Structure for storing information about profiles.

    This is mainly used for formated output of the profile list using
    the command line interface
    """
    def __init__(self, path, real_path, mtime, is_raw_profile=False):
        """
        Arguments:
            path(str): contains the name of the file, which identifies it in the index
            real_path(str): real path to the profile, i.e. how can it really be accessed
                this is either in jobs, in objects or somewhere else
            mtime(str): time of the modification of the profile
            is_raw_profile(bool): true if the stored profile is raw, i.e. in json and not
                compressed
        """
        # Load the data from JSON, which contains additional information about profile
        loaded_profile = load_profile_from_file(real_path, is_raw_profile)

        self.path = path
        self.id = os.path.relpath(real_path, os.getcwd())
        self.type = loaded_profile['header']['type']
        self.time = mtime
        self.cmd = loaded_profile['header']['cmd']
        self.args = loaded_profile['header']['params']
        self.workload = loaded_profile['header']['workload']
        self.collector = loaded_profile['collector_info']['name']
        self.checksum = None

    valid_attributes = [
        "path", "type", "time", "cmd", "args", "workload", "collector", "checksum", "id"
    ]
