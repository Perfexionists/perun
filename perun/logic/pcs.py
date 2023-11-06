"""PCS is a storage for the basic information of one performance control system unit

PCS is structure, that contains the basic information about one unit of performance control system,
contains a wrapper over configurations and other storages. The main representation of the pcs is
by its path.
"""
from __future__ import annotations

import os

import perun.logic.config as config
import perun.utils.helpers as helpers

from perun.utils.decorators import singleton_with_args, singleton
from perun.utils.exceptions import NotPerunRepositoryException


def get_safe_path(default: str) -> str:
    """Locates the instance of the perun starting from the current directory. In case the
    directory is not Perun repository, returns the safe default.

    :param str default: default path that is returned in case there is no perun
    :return: string path where the perun instance is located or default
    """
    try:
        return get_path()
    except NotPerunRepositoryException:
        return default


@singleton
def get_path() -> str:
    """Locates the instance of the perun starting from the current working directory

    This basically returns the current instance of the Perun

    :return: string path where the perun instance is located
    :raises NotPerunRepositoryException: when we cannot locate perun on the current directory tree
    """
    return os.path.join(helpers.locate_perun_dir_on(os.getcwd()), ".perun")


@singleton
def get_vcs_type_and_url() -> tuple[str, str]:
    """Returns the type and url of the wrapped version control system

    :return: type and url of the wrapped version control system
    :raises MissingConfigSectionException: when vcs.type or vcs.url is not set in local config
    """
    vcs_type, vcs_url = config.local(get_path()).get_bulk(["vcs.type", "vcs.url"])
    return vcs_type, os.path.abspath(os.path.join(get_path(), vcs_url))


@singleton
def get_vcs_path() -> str:
    """Returns the path to the wrapped version control system

    :return: url to the wrapped version control system
    :raises MissingConfigSectionException: when vcs.url is not set in local config
    """
    return os.path.abspath(os.path.join(get_path(), config.local(get_path()).get("vcs.url")))


@singleton
def local_config() -> config.Config:
    """Get local config for the current Perun context

    :returns Config: local config object, that can be passed to functions of config module
    """
    return config.local(get_path())


@singleton
def global_config() -> config.Config:
    """Get global config for the current Perun context

    :returns Config: global config object, that can be passed to function of config module
    """
    return config.shared()


@singleton
def get_object_directory() -> str:
    """Returns the name of the directory, where objects are stored

    :returns str: directory, where the objects are stored
    """
    object_directory = os.path.join(get_path(), "objects")
    helpers.touch_dir(object_directory)
    return object_directory


@singleton
def get_log_directory() -> str:
    """Returns the name of the directory, where logs are stored

    :return str: directory, where logs are stored
    """
    logs_directory = os.path.join(get_path(), "logs")
    helpers.touch_dir(logs_directory)
    return logs_directory


@singleton
def get_job_directory() -> str:
    """Returns the name of the directory, where pending profiles are stored

    :returns str: directory, where job outputs are stored
    """
    jobs_directory = os.path.join(get_path(), "jobs")
    helpers.touch_dir(jobs_directory)
    return jobs_directory


@singleton
def get_job_index() -> str:
    """Returns the name of the index, where pending profiles are registered

    :returns str: filename, where job outputs are registered
    """
    jobs_directory = get_job_directory()
    return os.path.join(jobs_directory, ".index")


@singleton
def get_stats_directory() -> str:
    """Returns the name of the directory where statistics are stored

    :return str: path to the statistics directory
    """
    stats_directory = os.path.join(get_path(), "stats")
    helpers.touch_dir(stats_directory)
    return stats_directory


@singleton
def get_stats_index() -> str:
    """Returns the path to the index file in stats directory where records about minor versions
    with stats files are stored

    :return str: path to the index file of the statistics directory
    """
    return os.path.join(get_stats_directory(), ".index")


@singleton
def get_tmp_directory() -> str:
    """Returns the name of the directory, where various or temporary files are stored

    :return str: path to the tmp directory
    """
    tmp_directory = os.path.join(get_path(), "tmp")
    helpers.touch_dir(tmp_directory)
    return tmp_directory


@singleton
def get_tmp_index() -> str:
    """Returns the path to the index file in tmp directory, where details about some tmp files
    are stored

    :return str: path to the tmp index file
    """
    tmp_directory = get_tmp_directory()
    return os.path.join(tmp_directory, ".index")


@singleton_with_args
def get_config_file(config_type: str) -> str:
    """Returns the config file for the given config type

    :returns str: path of the config of the given type
    """
    if config_type in ("shared", "global"):
        return os.path.join(config.lookup_shared_config_dir(), "shared.yml")
    return os.path.join(get_path(), "local.yml")
