"""PCS is a storage for the basic information of one performance control system unit

PCS is structure, that contains the basic information about one unit of performance control system,
contains a wrapper over configurations and other storages. The main representation of the pcs is
by its path.
"""
from __future__ import annotations

# Standard Imports
from typing import Optional
import os

# Third-Party Imports

# Perun Imports
from perun.logic import config
from perun.select import whole_repository_selection, abstract_base_selection
from perun.utils import decorators
from perun.utils.common import common_kit
from perun.utils.exceptions import NotPerunRepositoryException, UnsupportedModuleException
from perun.vcs.abstract_repository import AbstractRepository
from perun.vcs.git_repository import GitRepository


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


@decorators.singleton
def get_path() -> str:
    """Locates the instance of the perun starting from the current working directory

    This basically returns the current instance of the Perun

    :return: string path where the perun instance is located
    :raises NotPerunRepositoryException: when we cannot locate perun on the current directory tree
    """
    return os.path.join(common_kit.locate_perun_dir_on(os.getcwd()), ".perun")


@decorators.singleton
def vcs() -> AbstractRepository:
    """Returns Repository object

    :raises: UnsupportedModuleException when called with different type
    """
    vcs_type, vcs_url = get_vcs_type_and_url()
    if vcs_type == "git":
        return GitRepository(vcs_url)
    raise UnsupportedModuleException(vcs_type)


@decorators.singleton
def get_vcs_type_and_url() -> tuple[str, str]:
    """Returns the type and url of the wrapped version control system

    :return: type and url of the wrapped version control system
    :raises MissingConfigSectionException: when vcs.type or vcs.url is not set in local config
    """
    vcs_type, vcs_url = config.local(get_path()).get_bulk(["vcs.type", "vcs.url"])
    return vcs_type, os.path.abspath(os.path.join(get_path(), vcs_url))


@decorators.singleton
def get_vcs_path() -> str:
    """Returns the path to the wrapped version control system

    :return: url to the wrapped version control system
    :raises MissingConfigSectionException: when vcs.url is not set in local config
    """
    return os.path.abspath(os.path.join(get_path(), config.local(get_path()).get("vcs.url")))


@decorators.singleton
def local_config() -> config.Config:
    """Get local config for the current Perun context

    :returns Config: local config object, that can be passed to functions of config module
    """
    return config.local(get_path())


@decorators.singleton
def global_config() -> config.Config:
    """Get global config for the current Perun context

    :returns Config: global config object, that can be passed to function of config module
    """
    return config.shared()


@decorators.singleton
def get_object_directory() -> str:
    """Returns the name of the directory, where objects are stored

    :returns str: directory, where the objects are stored
    """
    object_directory = os.path.join(get_path(), "objects")
    common_kit.touch_dir(object_directory)
    return object_directory


@decorators.singleton
def get_log_directory() -> str:
    """Returns the name of the directory, where logs are stored

    :return str: directory, where logs are stored
    """
    logs_directory = os.path.join(get_path(), "logs")
    common_kit.touch_dir(logs_directory)
    return logs_directory


@decorators.singleton
def get_job_directory() -> str:
    """Returns the name of the directory, where pending profiles are stored

    :returns str: directory, where job outputs are stored
    """
    jobs_directory = os.path.join(get_path(), "jobs")
    common_kit.touch_dir(jobs_directory)
    return jobs_directory


@decorators.singleton
def get_job_index() -> str:
    """Returns the name of the index, where pending profiles are registered

    :returns str: filename, where job outputs are registered
    """
    jobs_directory = get_job_directory()
    return os.path.join(jobs_directory, ".index")


@decorators.singleton
def get_stats_directory() -> str:
    """Returns the name of the directory where statistics are stored

    :return str: path to the statistics directory
    """
    stats_directory = os.path.join(get_path(), "stats")
    common_kit.touch_dir(stats_directory)
    return stats_directory


@decorators.singleton
def get_stats_index() -> str:
    """Returns the path to the index file in stats directory where records about minor versions
    with stats files are stored

    :return str: path to the index file of the statistics directory
    """
    return os.path.join(get_stats_directory(), ".index")


@decorators.singleton
def get_tmp_directory() -> str:
    """Returns the name of the directory, where various or temporary files are stored

    :return str: path to the tmp directory
    """
    tmp_directory = os.path.join(get_path(), "tmp")
    common_kit.touch_dir(tmp_directory)
    return tmp_directory


@decorators.singleton
def get_tmp_index() -> str:
    """Returns the path to the index file in tmp directory, where details about some tmp files
    are stored

    :return str: path to the tmp index file
    """
    tmp_directory = get_tmp_directory()
    return os.path.join(tmp_directory, ".index")


@decorators.singleton_with_args
def get_config_file(config_type: str) -> str:
    """Returns the config file for the given config type

    :returns str: path of the config of the given type
    """
    if config_type in ("shared", "global"):
        return os.path.join(config.lookup_shared_config_dir(), "shared.yml")
    return os.path.join(get_path(), "local.yml")


@decorators.singleton_with_args
def selection(
    selection_type: Optional[str] = None,
) -> abstract_base_selection.AbstractBaseSelection:
    """Factory method for creating selection method

    Currently, supports:
      1. Whole Repository Selection: selects everything in the repository
    """
    if selection_type is None:
        selection_type = config.lookup_key_recursively(
            "selection_method", "whole_repository_selection"
        )

    if selection_type == "whole_repository_selection":
        return whole_repository_selection.WholeRepositorySelection()

    raise UnsupportedModuleException(selection_type)
