"""Collection of helper exception classes"""

__author__ = 'Tomas Fiedor'


class InvalidParameterException(Exception):
    """Raises when the given parameter is invalid"""
    pass


class MissingConfigSectionException(Exception):
    """Raised when the section in config is missing"""
    pass


class EntryNotFoundException(Exception):
    """Raised when the looked up entry is not within the index"""
    pass


class UnexpectedPrototypeSyntaxError(Exception):
    """ Raised when the function prototype syntax is somehow different than expected """
    pass

