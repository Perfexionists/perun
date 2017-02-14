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
