"""Collection of helper exception classes"""

__author__ = 'Tomas Fiedor'


class InvalidParameterException(Exception):
    """Raises when the given parameter is invalid"""
    def __init__(self, parameter, parameter_value, choices_msg=""):
        """
        :param str parameter: name of the parameter that is invalid
        :param object parameter_value: value of the parameter
        :param str choices_msg: string with choices for the valid parameters
        """
        super().__init__("")
        self.parameter = parameter
        self.value = str(parameter_value)
        self.choices_msg = " " + choices_msg

    def __str__(self):
        return "Invalid value '{}' for the parameter '{}'".format(self.value, self.parameter) \
               + self.choices_msg


class MissingConfigSectionException(Exception):
    """Raised when the section in config is missing"""
    pass


class ExternalEditorErrorException(Exception):
    """Raised when there is an error while invoking the external editor"""
    def __init__(self, editor, reason):
        """
        :param str editor: name of the invoked editor
        :param str reason: reason why the editor failed
        """
        super().__init__("")
        self.editor = editor
        self.reason = reason

    def __str__(self):
        return "error while invoking external '{}' editor: {}".format(
            self.editor, self.reason
        )


class MalformedIndexFileException(Exception):
    """Raised when the read index is malformed"""
    def __init__(self, reason):
        """
        :param str reason: the reason that the index is considered to be malformed
        """
        super().__init__("")
        self.reason = reason

    def __str__(self):
        return "working with malformed index file: {}".format(self.reason)


class EntryNotFoundException(Exception):
    """Raised when the looked up entry is not within the index"""
    def __init__(self, entry):
        """
        :param str entry: entry we are looking up in the index
        """
        super().__init__("")
        self.entry = entry

    def __str__(self):
        return "Entry satisfying '{}' predicate not found".format(self.entry)


class VersionControlSystemException(Exception):
    """Raised when there is an issue with wrapped version control system.

    For example, when there is incorrect sha-1 specification of the minor version.
    """
    def __init__(self, msg, *args):
        """
        :param str msg: format string of the error message
        :param list args: list of arguments for format string
        """
        super().__init__(msg)
        self.msg = msg
        self.args = args

    def __str__(self):
        return self.msg.format(*self.args)


class IncorrectProfileFormatException(Exception):
    """Raised when the file is missing or the given format is not in the unified json format"""
    def __init__(self, filename, msg):
        """
        :param str filename: filename of the profile in the wrong format
        :param str msg: additional message what is wrong withe profile
        """
        super().__init__("")
        self.filename = filename
        self.msg = msg

    def __str__(self):
        return self.msg.format(self.filename)


class NotPerunRepositoryException(Exception):
    """Raised when command is not called from within the scope of any Perun repository"""
    def __init__(self, path):
        super().__init__("")
        self.path = path

    def __str__(self):
        return "Current working dir is not a perun repository (or any parent on path {})".format(
            self.path
        )


class UnsupportedModuleException(Exception):
    """Raised when dynamically loading a module, that is not supported by the perun"""
    def __init__(self, module):
        super().__init__("")
        self.module = module

    def __str__(self):
        return "Module '{}' is not supported by Perun".format(self.module)


class UnsupportedModuleFunctionException(Exception):
    """Raised when supported module does not support the given function.

    I.e. there is no implementation of the given function.
    """
    def __init__(self, module, func):
        """
        :param str module: name of the module that does not support the given function
        """
        super().__init__("")
        self.module = module
        self.func = func

    def __str__(self):
        return "Function '{}' is not implemented withit the '{}' module".format(
            self.module, self.func
        )


class DictionaryKeysValidationFailed(Exception):
    """Raised when validated dictionary is actually not a dictionary or has missing/excess keys"""
    def __init__(self, dictionary, missing_keys, excess_keys):
        """
        :param dict dictionary: the validated dictionary
        :param list missing_keys: list of missing keys in the dictionary
        :param list excess_keys: list of excess forbidden keys in the dictionary
        """
        super().__init__("")
        self.dictionary = dictionary
        self.missing_keys = missing_keys
        self.excess_keys = excess_keys
        if not isinstance(self.dictionary, dict):
            self.msg = "Validated object '{0}' is not a dictionary.".format(self.dictionary)
        elif not self.missing_keys:
            self.msg = "Validated dictionary '{0}' has excess forbidden keys: '{1}'.".format(
                self.dictionary, ', '.join(self.excess_keys))
        elif not self.excess_keys:
            self.msg = "Validated dictionary '{0}' is missing required keys: '{1}'.".format(
                self.dictionary, ', '.join(self.missing_keys))
        else:
            self.msg = ("Validated dictionary '{0}' has excess forbidden keys: '{1}' and is "
                        "missing required keys: '{2}'.".format(self.dictionary,
                                                               ', '.join(self.excess_keys),
                                                               ', '.join(self.missing_keys)))

    def __str__(self):
        return self.msg


# Regression analysis exception hierarchy
class GenericRegressionExceptionBase(Exception):
    """Base class for all regression specific exception

    All specific exceptions should be derived from the base
    - this allows to catch all regression exceptions in one clause

    """
    def __init__(self, msg):
        """Base constructor with exception message"""
        super().__init__("")
        self.msg = msg

    def __str__(self):
        return self.msg


class InvalidPointsException(GenericRegressionExceptionBase):
    """Raised when regression data points count is too low or
    the x and y coordinates count is different"""
    def __init__(self, x_len, y_len, threshold):
        super().__init__("")
        self.x_len = x_len
        self.y_len = y_len
        self.threshold = threshold
        if self.x_len != self.y_len:
            self.msg = ("Points coordinates x and y have different lengths - x:{0}, "
                        "y:{1}.".format(self.x_len, self.y_len))
        elif self.x_len < self.threshold or self.y_len < self.threshold:
            self.msg = ("Too few points coordinates to perform regression - x:{0}, "
                        "y:{1}.".format(self.x_len, self.y_len))

    def __str__(self):
        return self.msg


class InvalidSequenceSplitException(GenericRegressionExceptionBase):
    """Raised when the sequence split would produce too few points to use in regression analysis"""
    def __init__(self, parts, ratio):
        super().__init__("")
        self.parts = parts
        self.ratio = ratio
        self.msg = ("Too few points would be produced by splitting the data into {0} "
                    "parts (resulting ratio: {1}).".format(self.parts, self.ratio))

    def __str__(self):
        return self.msg


class InvalidModelException(GenericRegressionExceptionBase):
    """Raised when invalid or unknown regression model is requested"""
    def __init__(self, model):
        super().__init__("")
        self.model = model
        self.msg = "Invalid or unsupported regression model: {0}.".format(str(self.model))

    def __str__(self):
        return self.msg


class InvalidTransformationException(GenericRegressionExceptionBase):
    """Raised when invalid or unknown model transformation is requested"""
    def __init__(self, model, transformation):
        super().__init__("")
        self.model = model
        self.transformation = transformation
        self.msg = ("Invalid or unsupported transformation: {0} for model: {1}."
                    .format(str(self.transformation), str(self.model)))

    def __str__(self):
        return self.msg


class StrategyNotImplemented(Exception):
    """Raised when requested computation method/strategy is not implemented"""
    def __init__(self, strategy):
        """
        :param str strategy: the requested strategy
        """
        super().__init__("")
        self.strategy = strategy
        self.msg = ("Requested computation method '{0}' is currently not implemented."
                    .format(self.strategy))

    def __str__(self):
        return self.msg


class TraceStackException(Exception):
    """Raised when trace stack processing encounters error"""
    def __init__(self, record, trace_stack):
        """
        :param namedtuple record: the record that was being processed 
        :param list trace_stack: the actual trace stack
        """
        super().__init__("")
        self.record = record
        self.call_stack = trace_stack
        self.msg = 'Trace stack corruption, record: ' + str(record)
        if not trace_stack:
            self.msg += '\nstack: \n  empty'
        else:
            self.msg += '\nstack:' + '\n  '.join(map(str, trace_stack))

    def __str__(self):
        return self.msg

