"""PCS is a storage for the basic information of one performance control system unit

PCS is structure, that contains the basic information about one unit of performance control system,
contains a wrapper over configurations and other storages. The main representation of the pcs is
by its path.
"""

import os

import perun.core.logic.config as config

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
        self.wrapped_vcs_type = config.get_key_from_config(config.local(self.path), 'vcs.type')
        self.wrapped_vcs_url = os.path.abspath(os.path.join(
            self.path, os.path.join(
                config.get_key_from_config(config.local(self.path), 'vcs.url'), ".git"
            )
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

    def get_object_directory(self):
        """
        Returns:
            directory: directory, where the objects are stored
        """
        object_directory = os.path.join(self.path, "objects")
        return object_directory
