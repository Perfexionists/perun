"""``perun.profile.factory`` specifies collective interface for basic
manipulation with profiles.

The format of profiles is w.r.t. :ref:`profile-spec`. This module contains
helper functions for loading and storing of the profiles either in the
persistent memory or in filesystem (in this case, the profile is in
uncompressed format).

.. _Python JSON library: https://docs.python.org/3.7/library/json.html

For further manipulations refer either to :ref:`profile-conversion-api`
(implemented in ``perun.profile.convert`` module) or :ref:`profile-query-api`
(implemented in ``perun.profile.query module``). For full specification how to
handle the JSON objects in Python refer to `Python JSON library`_.
"""

import json
import os
import time
import re

import perun.logic.config as config
import perun.logic.store as store
import perun.profile.query as query
import perun.utils.log as perun_log
from perun.utils import get_module
from perun.utils.exceptions import IncorrectProfileFormatException, InvalidParameterException
from perun.utils.helpers import SUPPORTED_PROFILE_TYPES, Unit, Job

__author__ = 'Tomas Fiedor'


PROFILE_COUNTER = 0


def lookup_value(container, key, missing):
    """Helper function for getting the key from the container. If it is not present in the container
    or it is empty string or empty object, the function should return the missing constant.

    :param dict container: dictionary container
    :param str key: string representation of the key
    :param str missing: string constant that is returned if key is not present in container,
        or is set to empty string or None.
    :return:
    """
    return str(container.get(key, missing)) or missing


def sanitize_filepart(part):
    """Helper function for sanitization of part of the filenames

    :param part: part of the filename, that needs to be sanitized, i.e. we are removing invalid
        characters
    :return: sanitized string representation of the part
    """
    invalid_characters = r"# %&{}\<>*?/ $!'\":@"
    return "".join('_' if c in invalid_characters else c for c in str(part))


def lookup_param(profile, unit, param):
    """Helper function for looking up the unit in the profile (can be either collector or
    postprocessor and finds the value of the param in it

    :param dict profile: dictionary with profile information w.r.t profile specification
    :param str unit: unit in which the parameter is located
    :param str param: parameter we will use in the resulting profile
    :return:
    """
    unit_param_map = {
        post['name']: post['params'] for post in profile.get('postprocessors', [])
    }
    used_collector = profile['collector_info']
    unit_param_map.update({
        used_collector.get('name', '?'): used_collector.get('params', {})
    })

    # Lookup the unit params
    unit_params = unit_param_map.get(unit)
    if unit_params:
        return sanitize_filepart(list(query.all_key_values_of(unit_params, param))[0]) or "_"
    else:
        return "_"


def generate_profile_name(profile):
    """Constructs the profile name with the extension .perf from the job.

    The profile is identified by its binary, collector, workload and the time
    it was run.

    Valid tags:
        `%collector%`:
            Name of the collector
        `%postprocessors%`:
            Joined list of postprocessing phases
        `%<unit>.<param>%`:
            Parameter of the collector given by concrete name
        `%cmd%`:
            Command of the job
        `%args%`:
            Arguments of the job
        `%workload%`:
            Workload of the job
        `%type%`:
            Type of the generated profile
        `%date%`:
            Current date
        `%origin%`:
            Origin of the profile
        `%counter%`:
            Increasing argument

    :param dict profile: generate the corresponding profile for given name
    :returns str: string for the given profile that will be stored
    """
    global PROFILE_COUNTER
    fmt_parser = re.Scanner([
        (r"%collector%", lambda scanner, token: lookup_value(profile['collector_info'], 'name', "_")),
        (r"%postprocessors%", lambda scanner, token:
            ("after-" + "-and-".join(map(lambda p: p['name'], profile['postprocessors'])))
                if len(profile['postprocessors']) else '_'
         ),
        (r"%[^.]+\.[^%]+%", lambda scanner, token:
            lookup_param(profile, *token[1:-1].split('.', maxsplit=1))
         ),
        (r"%cmd%", lambda scanner, token:
            os.path.split(lookup_value(profile['header'], 'cmd', '_'))[-1]
         ),
        (r"%args%", lambda scanner, token:
            "[" + sanitize_filepart(lookup_value(profile['header'], 'args', '_')) + "]"
         ),
        (r"%workload%", lambda scanner, token:
            "[" + sanitize_filepart(
                os.path.split(lookup_value(profile['header'], 'workload', '_'))[-1]
            ) + "]"
         ),
        (r"%type%", lambda scanner, token: lookup_value(profile['header'], 'type', '_')),
        (r"%date%", lambda scanner, token: time.strftime("%Y-%m-%d-%H-%M-%S", time.gmtime())),
        (r"%origin%", lambda scanner, token: lookup_value(profile, 'origin', '_')),
        (r"%counter%", lambda scanner, token: str(PROFILE_COUNTER)),
        (r"%%", lambda scanner, token: token),
        ('[^%]+', lambda scanner, token: token)
    ])
    PROFILE_COUNTER += 1

    # Obtain the formatting template from the configuration
    template = config.lookup_key_recursively('format.output_profile_template')
    tokens, rest = fmt_parser.scan(template)
    if rest:
        perun_log.error("formatting string '{}' could not be parsed\n\n".format(template) +
                        "Run perun config to modify the formatting pattern. "
                        "Refer to documentation for more information about formatting patterns")
    return "".join(tokens) + ".perf"


def load_profile_from_file(file_name, is_raw_profile):
    """Loads profile w.r.t :ref:`profile-spec` from file.

    :param str file_name: file path, where the profile is stored
    :param bool is_raw_profile: if set to true, then the profile was loaded
        from the file system and is thus in the JSON already and does not have
        to be decompressed and unpacked to JSON format.
    :returns: JSON dictionary w.r.t. :ref:`profile-spec`
    :raises IncorrectProfileFormatException: raised, when **filename** contains
        data, which cannot be converted to valid :ref:`profile-spec`
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


def generate_units(collector):
    """Generate information about units used by the collector.

    Note that this is mostly placeholder for future extension, how the units will be handled.
    Arguments:
        collector(module): collector module that collected the data

    Returns:
        dict: dictionary with map of resources to units
    """
    return collector.COLLECTOR_DEFAULT_UNITS


def generate_header_for_profile(job):
    """
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
        'units': generate_units(collector)
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
    profile = {'origin': pcs.get_head()}
    profile.update(collected_data)
    profile.update({'header': generate_header_for_profile(job)})
    profile.update({'collector_info': generate_collector_info(job)})
    profile.update({'postprocessors': generate_postprocessor_info(job)})
    return profile


def store_profile_at(profile, file_path):
    """Stores profile w.r.t. :ref:`profile-spec` to output file.

    :param dict profile: dictionary with profile w.r.t. :ref:`profile-spec`
    :param str file_path: output path, where the `profile` will be stored
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


def to_config_tuple(profile):
    """Converts the profile to the tuple representing its configuration

    :param dict profile: profile we are converting to configuration tuple
    :returns: tuple of (collector.name, cmd, args, workload, [postprocessors])
    """
    profile_header = profile['header']
    return (
        profile['collector_info']['name'],
        profile_header.get('cmd', ''),
        profile_header.get('args', ''),
        profile_header.get('workload', ''),
        [postprocessor['name'] for postprocessor in profile['postprocessors']]
    )


def extract_job_from_profile(profile):
    """Extracts information from profile about job, that was done to generate the profile.

    Fixme: Add assert that profile is profile
    Arguments:
        profile(dict): dictionary with valid profile

    Returns:
        Job: job according to the profile informations
    """
    collector_record = profile['collector_info']
    collector = Unit(collector_record['name'], collector_record['params'])

    posts = []
    for postprocessor in profile['postprocessors']:
        posts.append(Unit(postprocessor['name'], postprocessor['params']))

    cmd = profile['header']['cmd']
    params = profile['header']['params']
    workload = profile['header']['workload']

    return Job(collector, posts, cmd, workload, params)


def is_key_aggregatable_by(profile, func, key, keyname):
    """Check if the key can be aggregated by the function.

    Everything is countable and hence 'count' and 'nunique' (number of unique values) are
    valid aggregation functions for everything. Otherwise (e.g. sum, mean), we need numerical
    values.

    Arguments:
        profile(dict): profile that will be used against in the validation
        func(function): function used for aggregation of the data
        key(str): key that will be aggregated in the graph
        keyname(str): name of the validated key

    Returns:
        bool: true if the key is aggregatable by the function

    Raises:
        InvalidParameterException: if the of_key does not support the given function
    """
    # Everything is countable ;)
    if func in ('count', 'nunique'):
        return True

    # Get all valid numeric keys and validate
    valid_keys = set(query.all_numerical_resource_fields_of(profile))
    if key not in valid_keys:
        choices = "(choose either count/nunique as aggregation function;"
        choices += " or from the following keys: {})".format(
            ", ".join(map(str, valid_keys))
        )
        raise InvalidParameterException(keyname, key, choices)
    return True


class ProfileInfo(object):
    """Structure for storing information about profiles.

    This is mainly used for formatted output of the profile list using
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

        self.origin = path
        self.realpath = os.path.relpath(real_path, os.getcwd())
        self.type = loaded_profile['header']['type']
        self.time = mtime
        self.cmd = loaded_profile['header']['cmd']
        self.args = loaded_profile['header']['params']
        self.workload = loaded_profile['header']['workload']
        self.collector = loaded_profile['collector_info']['name']
        self.postprocessors = [
            postprocessor['name'] for postprocessor in loaded_profile['postprocessors']
        ]
        self.checksum = None
        self.config_tuple = (
            self.collector, self.cmd, self.args, self.workload,
            ",".join(self.postprocessors)
        )

    valid_attributes = [
        "realpath", "type", "time", "cmd", "args", "workload", "collector", "checksum", "origin"
    ]
