import perun.utils.decorators as decorators
import perun.utils.exceptions as exceptions
import perun.utils.log as perun_log
import perun.core.logic.store as store

import collections
import os
import re
import sys
import yaml
__author__ = 'Tomas Fiedor'

Config = collections.namedtuple('Config', ['type', 'path', 'data'])

# TODO: Could there be an issue that the config is changed during the run?
# I think, that each command is run once, so no, but for GUI version this may differ


def init_shared_config_at(path):
    """
    Arguments:
        path(str): path where the empty shared config will be initialized
        
    Returns:
        bool: whether the config file was successfully created
    """
    store.touch_file(path)

    shared_config = """"""

    write_config_file(path, shared_config)
    return True


def init_local_config_at(path):
    """
    Arguments:
        path(str): path where the empty shared config will be initialized

    Returns:
        bool: whether the config file was successfully created
    """
    store.touch_file(path)

    # empty config is created
    local_config = """"""

    write_config_file(path, local_config)
    return True


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
    with open(path, 'r') as yaml_file:
        return yaml.safe_load(yaml_file)


def write_config_file(config, path):
    """
    Arguments:
        config(yaml): configuration dictionary
        path(str): path, where the configuration will be stored
    """
    with open(path, 'w') as yaml_file:
        yaml.dump(config, yaml_file)


def is_valid_key(key):
    """Validates that key is in form of ".".join(sections)

    Arguments:
        key(str): string we are validating

    Returns:
        bool: true if the key is in valid format
    """
    valid_key_pattern = re.compile(r"^[a-zA-Z0-9]+(\.[a-zA-Z0-9]+)*$")
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
    _locate_section_from_query(config.data, sections)[last_section].append(value)


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
    pass
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
    config_file = os.sep.join(config_dir, ".".join(config_type, 'yml'))

    if not os.path.exists(config_file):
        if not init_config_at(config_file, config_type):
            perun_log.error("Could not initialize {} config at {}".format(
                config_type,
                config_dir
            ))

    return Config(config_type, config_dir, read_config_file(config_file))


@decorators.singleton
def shared():
    """
    Returns config corresponding to the global configuration data, i.e.
    such that is shared by all of the perun locations.

    Returns:
        config: returns global config file
    """
    shared_config_dir = os.path.dirname(os.path.realpath(__file__))
    return load_config(shared_config_dir, 'local')


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
