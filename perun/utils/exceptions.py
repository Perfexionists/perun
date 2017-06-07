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
    def __init__(self, entry):
        """
        Arguments:
            entry(str): entry we are looking up in the index
        """
        self.entry = entry

    def __str__(self):
        return "Entry satisfying '{}' predicate not found".format(self.entry)


class UnexpectedPrototypeSyntaxError(Exception):
    """Raised when the function prototype syntax is somehow different than expected"""
    pass


class VersionControlSystemException(Exception):
    """Raised when there is an issue with wrapped version control system.

    For example, when there is incorrect sha-1 specification of the minor version.
    """
    def __init__(self, msg, *args):
        """
        Arguments:
            msg(str): format string of the error message
            args(list): list of arguments for format string
        """
        self.msg = msg
        self.args = args

    def __str__(self):
        return self.msg.format(*self.args)


class IncorrectProfileFormatException(Exception):
    """Raised when the file is missing or the given format is not in the unified json format"""
    def __init__(self, filename, msg):
        """
        Arguments:
            filename(str): filename of the profile in the wrong format
            msg(str): additional message what is wrong withe profile
        """
        self.filename = filename
        self.msg = msg

    def __str__(self):
        return self.msg.format(self.filename)


class NotPerunRepositoryException(Exception):
    """Raised when command is not called from within the scope of any Perun repository"""
    def __init__(self, path):
        self.path = path

    def __str__(self):
        return "Current working dir is not a perun repository (or any parent on path {})".format(
            self.path
        )


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
