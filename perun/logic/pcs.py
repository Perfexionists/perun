"""PCS is a storage for the basic information of one performance control system unit

PCS is structure, that contains the basic information about one unit of performance control system,
contains a wrapper over configurations and other storages. The main representation of the pcs is
by its path.
"""

import os

import perun.logic.store as store
import perun.logic.config as config

from perun.utils.decorators import singleton, singleton_with_args

__author__ = 'Tomas Fiedor'


@singleton
def get_path():
    """Locates the instance of the perun starting from the current working directory

    This basically returns the current instance of the Perun

    :return: string path where the perun instance is located
    :raises NotPerunRepositoryException: when we cannot locate perun on the current directory tree
    """
    return os.path.join(store.locate_perun_dir_on(os.getcwd()), '.perun')


@singleton
def get_vcs_type():
    """Returns the type of the wrapped version control system

    :return: type of the wrapped version control system
    :raises MissingConfigSectionException: when vcs.type is not set in local config
    """
    return config.local(get_path()).get('vcs.type')


@singleton
def get_vcs_path():
    """Returns the path to the wrapped version control system

    :return: url to the wrapped version control system
    :raises MissingConfigSectionException: when vcs.url is not set in local config
    """
    return os.path.abspath(os.path.join(
        get_path(), config.local(get_path()).get('vcs.url')
    ))


@singleton
def local_config():
    """Get local config for the current Perun context

    :returns Config: local config object, that can be passed to functions of config module
    """
    return config.local(get_path())


@singleton
def global_config():
    """Get global config for the current Perun context

    :returns Config: global config object, that can be passed to function of config module
    """
    return config.shared()


@singleton
def get_object_directory():
    """Returns the name of the directory, where objects are stored

    :returns str: directory, where the objects are stored
    """
    object_directory = os.path.join(get_path(), "objects")
    store.touch_dir(object_directory)
    return object_directory


@singleton
def get_log_directory():
    """Returns the name of the directory, where logs are stored

    :return str: directory, where logs are stored
    """
    logs_directory = os.path.join(get_path(), "logs")
    store.touch_dir(logs_directory)
    return logs_directory


@singleton
def get_job_directory():
    """Returns the name of the directory, where pending profiles are stored

    :returns str: directory, where job outputs are stored
    """
    jobs_directory = os.path.join(get_path(), "jobs")
    store.touch_dir(jobs_directory)
    return jobs_directory


@singleton_with_args
def get_config_file(config_type):
    """Returns the config file for the given config type

    :returns str: path of the config of the given type
    """
    if config_type in ('shared', 'global'):
        return os.path.join(config.lookup_shared_config_dir(), 'shared.yml')
    else:
        return os.path.join(get_path(), 'local.yml')
