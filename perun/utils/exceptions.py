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
    """Raised when the function prototype syntax is somehow different than expected"""
    pass


class NotPerunRepositoryException(Exception):
    """Raised when command is not called from within the scope of any Perun repository"""
    pass


class UnsupportedModuleException(Exception):
    """Raised when dynamically loading a module, that is not supported by the perun"""
    def __init__(self, module):
        self.module = module

    def __str__(self):
        return "Module '{}' is not supported by Perun".format(self.module)


class UnsupportedModuleFunctionException(Exception):
    """Raised when supported module does not support the given function.

    I.e. there is no implementation of the given function.
    """
    def __init__(self, module, func):
        """
        Arguments:
            module(str): name of the module that does not support the given function
        """
        self.module = module
        self.func = func

    def __str__(self):
        return "Function '{}' is not implemented withit the '{}' module".format(
            self.module, self.func
        )
