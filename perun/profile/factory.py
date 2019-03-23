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
import operator

import perun.logic.pcs as pcs
import perun.logic.config as config
import perun.logic.store as store
import perun.logic.index as index
import perun.vcs as vcs
import perun.profile.query as query
import perun.utils.log as perun_log

from perun.utils import get_module
from perun.utils.exceptions import InvalidParameterException, MissingConfigSectionException
from perun.utils.helpers import Job
from perun.utils.structs import Unit

__author__ = 'Tomas Fiedor'


PROFILE_COUNTER = 0
DEFAULT_SORT_KEY = 'time'


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
        (r"%collector%", lambda scanner, token:
            lookup_value(profile['collector_info'], 'name', "_")
        ),
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


def load_list_for_minor_version(minor_version):
    """Returns profiles assigned to the given minor version.

    :param str minor_version: identification of the commit (preferably sha1)
    :returns list: list of ProfileInfo parsed from index of the given minor_version
    """
    # Compute the
    profiles = index.get_profile_list_for_minor(pcs.get_object_directory(), minor_version)
    profile_info_list = []
    for index_entry in profiles:
        inside_info = {
            'header': {
                'type': index_entry.type,
                'cmd': index_entry.cmd,
                'args': index_entry.args,
                'workload': index_entry.workload
            },
            'collector_info': {'name': index_entry.collector},
            'postprocessors': [
                {'name': p} for p in index_entry.postprocessors
            ]
        }
        _, profile_name = store.split_object_name(pcs.get_object_directory(), index_entry.checksum)
        profile_info \
            = ProfileInfo(index_entry.path, profile_name, index_entry.time, inside_info)
        profile_info_list.append(profile_info)

    return profile_info_list


def generate_units(collector):
    """Generate information about units used by the collector.

    Note that this is mostly placeholder for future extension, how the units will be handled.

    :param module collector: collector module that collected the data
    :returns dict: dictionary with map of resources to units
    """
    return collector.COLLECTOR_DEFAULT_UNITS


def generate_header_for_profile(job):
    """
    :param Job job: job with information about the computed profile
    :returns dict: dictionary in form of {'header': {}} corresponding to the perun specification
    """
    try:
        collector = get_module('.'.join(['perun.collect', job.collector.name]))
    except ImportError:
        perun_log.error("could not find the package for collector {}".format(job.collector.name))

    return {
        'type': collector.COLLECTOR_TYPE,
        'cmd': job.cmd,
        'args': job.args,
        'workload': job.workload,
        'units': generate_units(collector)
    }


def generate_collector_info(job):
    """
    :param Job job: job with information about the computed profile
    :returns dict: dictionary in form of {'collector_info': {}} corresponding to the perun
        specification
    """
    return {
        'name': job.collector.name,
        'params': job.collector.params
    }


def generate_postprocessor_info(job):
    """
    :param Job job: job with information about the computed profile
    :returns dict: dictionary in form of {'postprocess_info': []} corresponding to the perun spec
    """
    return [
        {
            'name': postprocessor.name,
            'params': postprocessor.params
        } for postprocessor in job.postprocessors
    ]


def finalize_profile_for_job(collected_data, job):
    """
    :param dict collected_data: collected profile through some collector
    :param Job job: job with informations about the computed profile
    :returns dict: valid profile JSON file
    """
    profile = {'origin': vcs.get_minor_head()}
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

    :param dict profile: profile we are converting to string
    :returns str: string representation of profile
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


def config_tuple_to_cmdstr(config_tuple):
    """Converts tuple to command string

    :param tuple config_tuple: tuple of (collector, cmd, args, workload, postprocessors)
    :return: string representing the executed command
    """
    return " ".join(filter(lambda x: x, config_tuple[1:4]))


def extract_job_from_profile(profile):
    """Extracts information from profile about job, that was done to generate the profile.

    Fixme: Add assert that profile is profile

    :param dict profile: dictionary with valid profile
    :returns Job: job according to the profile informations
    """
    collector_record = profile['collector_info']
    collector = Unit(collector_record['name'], collector_record['params'])

    posts = []
    for postprocessor in profile['postprocessors']:
        posts.append(Unit(postprocessor['name'], postprocessor['params']))

    cmd = profile['header']['cmd']
    args = profile['header']['args']
    workload = profile['header']['workload']

    return Job(collector, posts, cmd, workload, args)


def is_key_aggregatable_by(profile, func, key, keyname):
    """Check if the key can be aggregated by the function.

    Everything is countable and hence 'count' and 'nunique' (number of unique values) are
    valid aggregation functions for everything. Otherwise (e.g. sum, mean), we need numerical
    values.

    :param dict profile: profile that will be used against in the validation
    :param function func: function used for aggregation of the data
    :param str key: key that will be aggregated in the graph
    :param str keyname: name of the validated key
    :returns bool: true if the key is aggregatable by the function
    :raises InvalidParameterException: if the of_key does not support the given function
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


def sort_profiles(profile_list, reverse_profiles=True):
    """Sorts the profiles according to the key set in either configuration.

    The key can either be specified in temporary configuration, or in any of the local or global
    configs as the key :ckey:`format.sort_profiles_by` attributes. Be default, profiles are sorted
    by time. In case of any errors (invalid sort key or missing key) the profiles will be sorted by
    default key as well.

    :param list profile_list: list of ProfileInfo object
    :param true reverse_profiles: true if the order of the sorting should be reversed
    """
    sort_order = DEFAULT_SORT_KEY
    try:
        sort_order = config.lookup_key_recursively('format.sort_profiles_by')
        # If the stored key is invalid, we use the default time as well
        if sort_order not in ProfileInfo.valid_attributes:
            perun_log.warn("invalid sort key '{}'".format(sort_order) +
                           " Profiles will be sorted by '{}'\n\n".format(sort_order) +
                           "Please set sort key in config or cli to one"
                           " of ({}".format(", ".join(ProfileInfo.valid_attributes)) + ")")
            sort_order = DEFAULT_SORT_KEY
    except MissingConfigSectionException:
        perun_log.warn("missing set option 'format.sort_profiles_by'!"
                       " Profiles will be sorted by '{}'\n\n".format(sort_order) +
                       "Please run 'perun config edit' and set 'format.sort_profiles_by' to one"
                       " of ({}".format(", ".join(ProfileInfo.valid_attributes)) + ")")

    profile_list.sort(key=operator.attrgetter(sort_order), reverse=reverse_profiles)


def merge_resources_of(lhs, rhs):
    """Merges the resources of lhs and rhs profiles

    :param dict lhs: left operator of the profile merge
    :param dict rhs: right operator of the profile merge
    :return: profile with merged resources
    """
    # Return lhs/rhs if rhs/lhs is empty
    if not rhs:
        return lhs
    if not lhs:
        return rhs

    # Note that we assume  that lhs and rhs are the same type ;)
    if 'global' in lhs.keys() and lhs['global']:
        lhs['global']['resources'].extend(rhs['global']['resources'])
        lhs['global']['timestamp'] += rhs['global']['timestamp']

    if 'snapshots' in lhs.keys():
        lhs['snapshots'].extend(rhs['snapshots'])

    return lhs


class ProfileInfo(object):
    """Structure for storing information about profiles.

    This is mainly used for formatted output of the profile list using
    the command line interface
    """
    def __init__(self, path, real_path, mtime, profile_info, is_raw_profile=False):
        """
        :param str path: contains the name of the file, which identifies it in the index
        :param str real_path: real path to the profile, i.e. how can it really be accessed
            this is either in jobs, in objects or somewhere else
        :param str mtime: time of the modification of the profile
        :param bool is_raw_profile: true if the stored profile is raw, i.e. in json and not
            compressed
        """

        self._is_raw_profile = is_raw_profile
        self.source = path
        self.realpath = os.path.relpath(real_path, os.getcwd())
        self.time = mtime
        self.type = profile_info['header']['type']
        self.cmd = profile_info['header']['cmd']
        self.args = profile_info['header']['args']
        self.workload = profile_info['header']['workload']
        self.collector = profile_info['collector_info']['name']
        self.postprocessors = [
            postprocessor['name'] for postprocessor in profile_info['postprocessors']
        ]
        self.checksum = None
        self.config_tuple = (
            self.collector, self.cmd, self.args, self.workload,
            ",".join(self.postprocessors)
        )

    def load(self):
        """Loads the profile from given file

        This is basically a wrapper that loads the profile, whether it is raw (i.e. in pending)
        or not raw and stored in index

        :return: loaded profile in dictionary format, w.r.t :ref:`profile-spec`
        """
        return store.load_profile_from_file(self.realpath, self._is_raw_profile)

    valid_attributes = [
        "realpath", "type", "time", "cmd", "args", "workload", "collector", "checksum", "source"
    ]
