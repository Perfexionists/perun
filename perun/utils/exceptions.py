"""Collection of helper exception classes"""

__author__ = 'Tomas Fiedor'


class InvalidParameterException(Exception):
    """Raises when the given parameter is invalid"""
    pass


class MissingConfigSectionException(Exception):
    """Raised when the section in config is missing"""
    pass
