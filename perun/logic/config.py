"""Config is a wrapper over local and global configuration files.

Config provides collection of methods to work with configuration files, both global and local.
Configurations are implemented as a YAML forward, for possible checks and in order to stay unified
with CI, like e.g. travis, which usually uses yaml format.

There are two types of config: local, corresponding to concrete pcs, and global, which contains
global information and configurations, like e.g. list of registered repositories.
"""
import collections
import os
import re
import sys

from ruamel.yaml import YAML

import perun.logic.store as store
import perun.utils.decorators as decorators
import perun.utils.exceptions as exceptions
import perun.utils.log as perun_log
import perun.utils.streams as streams

__author__ = 'Tomas Fiedor'

Config = collections.namedtuple('Config', ['type', 'path', 'data'])

# TODO: Could there be an issue that the config is changed during the run?
# I think, that each command is run once, so no, but for GUI version this may differ


def init_shared_config_at(path):
    """
    Arguments:
        path(str): path where the empty global config will be initialized
    """
    if not path.endswith('shared.yml') and not path.endswith('shared.yaml'):
        path = os.path.join(path, 'shared.yml')
    store.touch_file(path)

    shared_config = streams.safely_load_yaml_from_stream("""
general:
    editor: vim
    paging: only-log

format:
    status: "\u2503 [type] \u2503 [collector]  \u2503 ([time]) \u2503 [origin] \u2503"
    shortlog: "[id:6] ([stats]) [desc]"
    """)

    write_config_file(shared_config, path)


def init_local_config_at(path, wrapped_vcs):
    """
    Arguments:
        path(str): path where the empty shared config will be initialized
        wrapped_vcs(dict): dictionary with wrapped vcs of type {'vcs': {'type', 'url'}}
    """
    if not path.endswith('local.yml') and not path.endswith('local.yaml'):
        path = os.path.join(path, 'local.yml')
    store.touch_file(path)

    # Create a config for user to set up
    local_config = streams.safely_load_yaml_from_stream("""
vcs:
  type: {0}
  url: {1}

## To collect profiling data from the binary using the set of collectors,
## uncomment and edit the following region:
# cmds:
#   - echo

## To add set of parameters for the profiled command/binary,
## uncomment and edit the following region:
# args:
#   - -e

## To add workloads/inputs for the profiled command/binary,
## uncomment and edit the following region:
# workloads:
#   - hello
#   - world

## To register a collector for generating profiling data,
## uncomment and edit the following region:
# collectors:
#   - name: time
## Try '$ perun collect --help' to obtain list of supported collectors!

## To register a postprocessor for generated profiling data,
## uncomment and edit the following region (!order matters!):
# postprocessors:
#   - name: normalizer
#     params: --remove-zero
#   - name: filter
## Try '$ perun postprocessby --help' to obtain list of supported collectors!
    """.format(wrapped_vcs['vcs']['type'], wrapped_vcs['vcs']['url']))

    write_config_file(local_config, path)


def init_config_at(path, config_type):
    """
    Arguments:
        path(str): path where the empty shared config will be initialized
        config_type(str): type of the config (either shared or local)

    Returns:
        bool: whether the config file was successfully created
    """
    init_function_name = "init_{}_config_at".format(config_type)
    return getattr(sys.modules[__name__], init_function_name)(path)


def read_config_file(path):
    """
    Arguments:
        path(str): source path of the config

    Returns:
        dict: yaml config
    """
    return streams.safely_load_yaml_from_file(path)


def write_config_file(config, path):
    """
    Arguments:
        config(yaml): configuration dictionary
        path(str): path, where the configuration will be stored
    """
    perun_log.msg_to_stdout("Writing config '{}' at {}".format(
        config, path
    ), 2)
    with open(path, 'w') as yaml_file:
        YAML().dump(config, yaml_file)


def is_valid_key(key):
    """Validates that key is in form of ".".join(sections)

    Arguments:
        key(str): string we are validating

    Returns:
        bool: true if the key is in valid format
    """
    valid_key_pattern = re.compile(r"^[a-zA-Z0-9_]+(\.[a-zA-Z0-9_]+)*$")
    return valid_key_pattern.match(key) is not None


def _locate_section_from_query(config_data, sections):
    """
    Iterates through the config_data and queries the subsections from the list
    of the sections, returning the last one.

    Arguments:
        config_data(dict): dictionary representing yaml configuration
        sections(list): list of sections in config

    Returns:
        dict: dictionary representing the section that will be updated
    """

    section_iterator = config_data
    for section in sections:
        if section not in section_iterator.keys():
            section_iterator[section] = {}
        section_iterator = section_iterator[section]
    return section_iterator


@decorators.validate_arguments(['key'], is_valid_key)
def set_key_at_config(config, key, value):
    """
    Arguments:
        config(Config): named tuple with config we are writing
        key(str): list of section separated by dots
        value(arbitrary): value we are writing to the key at config
    """
    *sections, last_section = key.split('.')
    _locate_section_from_query(config.data, sections)[last_section] = value
    write_config_file(config.data, config.path)


@decorators.validate_arguments(['key'], is_valid_key)
def append_key_at_config(config, key, value):
    """
    Fixme: What if there is nothing?
    Arguments:
        config(Config): named tuple with config we are writing
        key(str): list of section separated by dots
        value(arbitrary): value we are writing to the key at config
    """
    *sections, last_section = key.split('.')
    section_location = _locate_section_from_query(config.data, sections)
    if last_section not in section_location.keys():
        section_location[last_section] = []
    section_location[last_section].append(value)
    write_config_file(config.data, config.path)


def _ascend_by_section_safely(section_iterator, section_key):
    """
    Ascend by one level in the section_iterator. In case the section_key
    is not in the section_iterator, MissingConfigSectionException is raised.

    Arguments:
        section_iterator(dict): dictionary with sections
        section_key(str): section in dictionary

    Returns:
        dict: section after ascending by the section key
    """
    if section_key not in section_iterator:
        raise exceptions.MissingConfigSectionException("Missing section '{}' in config file".format(
            section_key
        ))
    return section_iterator[section_key]


@decorators.validate_arguments(['key'], is_valid_key)
def get_key_from_config(config, key):
    """
    Arguments:
        config(Config): named tuple with config we are writing
        key(str): list of section separated by dots

    Returns:
        value: value of the key at config
    """
    sections = key.split('.')

    section_iterator = config.data
    for section in sections:
        section_iterator = _ascend_by_section_safely(section_iterator, section)
    return section_iterator


def load_config(config_dir, config_type):
    """
    Arguments:
        config_dir(str): directory, where the config is stored
        config_type(str): type of the config (either shared or local)

    Returns:
        config: loaded config
    """
    config_file = os.sep.join([config_dir, ".".join([config_type, 'yml'])])

    try:
        if not os.path.exists(config_file):
            init_config_at(config_file, config_type)

        return Config(config_type, config_file, read_config_file(config_file))
    except IOError as io_error:
        perun_log.error("error initializing {} config: {}".format(
            config_type, str(io_error)
        ))


def lookup_shared_config_dir():
    """
    Returns:
        str: dir, where the shared config will be stored
    """
    environment_dir = os.environ.get('PERUN_CONFIG_DIR')
    if environment_dir:
        return environment_dir

    home_directory = os.path.expanduser("~")

    if sys.platform == 'win32':
        perun_config_dir = os.path.join(home_directory, 'AppData', 'Local', 'perun')
    elif sys.platform == 'linux':
        perun_config_dir = os.path.join(home_directory, '.config', 'perun')
    else:
        perun_log.error("currently unsupported platform: ".format(sys.platform))

    store.touch_dir_range(home_directory, perun_config_dir)
    return perun_config_dir


@decorators.singleton
def shared():
    """
    Returns config corresponding to the shared configuration data, i.e.
    such that is shared by all of the perun locations.

    Returns:
        config: returns shared config file
    """
    shared_config_dir = lookup_shared_config_dir()
    return load_config(shared_config_dir, 'shared')


@decorators.singleton_with_args
def local(path):
    """
    Returns config corresponding to the local configuration data,
    located at @p path.

    Arguments:
        path(src): path corresponding to the perun instance

    Returns:
        config: returns local config for given path
    """
    assert os.path.isdir(path)
    return load_config(path, 'local')


def lookup_key_recursively(path, key):
    """Recursively looks up the key first in the local config and then in the global.

    This is used e.g. for formatting strings or editors, where first we have our local configs,
    that have higher priority. In case there is nothing set in the config, we will check the
    global config.

    Arguments:
        path(str): path to the local config
        key(str): key we are looking up
    """
    try:
        return get_key_from_config(local(path), key)
    except exceptions.MissingConfigSectionException:
        return get_key_from_config(shared(), key)
