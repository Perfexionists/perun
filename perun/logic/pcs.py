"""PCS is a storage for the basic information of one performance control system unit

PCS is structure, that contains the basic information about one unit of performance control system,
contains a wrapper over configurations and other storages. The main representation of the pcs is
by its path.
"""

import os

import perun.logic.store as store
import perun.logic.config as config
import perun.utils.log as log
import perun.vcs as vcs

__author__ = 'Tomas Fiedor'


class PCS(object):
    """Wrapper over performance control system

    PCS represents the performance control systems and its basic methods,
    which are mostly wrappers over the existing modules
    """

    def __init__(self, fullpath):
        """
        Arguments:
            fullpath(str): path to the performance control system
        """
        assert os.path.isdir(fullpath)
        self.path = os.path.join(fullpath, '.perun')
        self.vcs_type = config.local(self.path).get('vcs.type')
        self.vcs_path = os.path.abspath(os.path.join(
            self.path, config.local(self.path).get('vcs.url')
        ))

    def local_config(self):
        """Get local config

        Returns:
            Config: local config object, that can be passed to functions of config module
        """
        return config.local(self.path)

    @staticmethod
    def global_config():
        """Get global config

        Returns:
            Config: global config object, that can be passed to function of config module
        """
        return config.shared()

    def __repr__(self):
        """
        Returns:
            str: string representation of the performance control system
        """
        return "PCS({})".format(self.path)

    def get_head(self):
        """
        Returns:
            str: minor head of the wrapped version control system
        """
        return vcs.get_minor_head(self.vcs_type, self.vcs_path)

    def get_object_directory(self):
        """
        Returns:
            directory: directory, where the objects are stored
        """
        object_directory = os.path.join(self.path, "objects")
        return object_directory

    def get_job_directory(self):
        """
        Returns:
            directory: directory, where job outputs are stored
        """
        return os.path.join(self.path, "jobs")

    def get_config_file(self, config_type):
        """
        Returns:
            str: path of the config of the given type
        """
        if config_type in ('local', 'recursive'):
            return os.path.join(self.path, 'local.yml')
        elif config_type in ('shared', 'global'):
            return os.path.join(config.lookup_shared_config_dir(), 'shared.yml')
        else:
            log.error("wrong configuration type for self.get_config_file: '{}'".format(config_type))


def pass_pcs(func):
    """Decorator for passing pcs object to function

    Provided the current working directory, constructs the PCS object,
    that encapsulates the performance control and passes it as argument.

    Note: Used for CLI interface.

    Arguments:
        func(function): function we are decorating

    Returns:
        func: wrapped function
    """
    def wrapper(*args, **kwargs):
        """Wrapper function for the decorator"""
        perun_directory = store.locate_perun_dir_on(os.getcwd())
        return func(PCS(perun_directory), *args, **kwargs)

    return wrapper
