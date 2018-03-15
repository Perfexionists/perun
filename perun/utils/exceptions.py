"""Collection of helper exception classes"""

__author__ = 'Tomas Fiedor'


class InvalidParameterException(Exception):
    """Raises when the given parameter is invalid"""
    def __init__(self, parameter, parameter_value, choices_msg=""):
        """
        Arguments:
            parameter(str): name of the parameter that is invalid
            parameter_value(object): value of the parameter
            choices_msg(str): string with choices for the valid parameters
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
        Arguments:
            editor(str): name of the invoked editor
            reason(str): reason why the editor failed
        """
        super().__init__("")
        self.editor = editor
        self.reason = reason

    def __str__(self):
        return "error while invoking external '{}' editor: {}".format(
            self.editor, self.reason
        )


class EntryNotFoundException(Exception):
    """Raised when the looked up entry is not within the index"""
    def __init__(self, entry):
        """
        Arguments:
            entry(str): entry we are looking up in the index
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
        Arguments:
            msg(str): format string of the error message
            args(list): list of arguments for format string
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
        Arguments:
            filename(str): filename of the profile in the wrong format
            msg(str): additional message what is wrong withe profile
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
        Arguments:
            module(str): name of the module that does not support the given function
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
        Arguments:
            dictionary(dict): the validated dictionary
            missing_keys(list): list of missing keys in the dictionary
            excess_keys(list): list of excess forbidden keys in the dictionary
        """
        super().__init__("")
        self.dictionary = dictionary
        self.missing_keys = missing_keys
        self.excess_keys = excess_keys

    def __str__(self):
        if not isinstance(self.dictionary, dict):
            msg = "Validated object '{0}' is not a dictionary.".format(self.dictionary)
        elif not self.missing_keys:
            msg = "Validated dictionary '{0}' has excess forbidden keys: '{1}'.".format(
                self.dictionary, ', '.join(self.excess_keys))
        elif not self.excess_keys:
            msg = "Validated dictionary '{0}' is missing required keys: '{1}'.".format(
                self.dictionary, ', '.join(self.missing_keys))
        else:
            msg = ("Validated dictionary '{0}' has excess forbidden keys: '{1}' and is "
                   "missing required keys: '{2}'.".format(self.dictionary,
                                                          ', '.join(self.excess_keys),
                                                          ', '.join(self.missing_keys)))
        return msg


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

    def __str__(self):
        if self.x_len != self.y_len:
            self.msg = ("Points coordinates x and y have different lengths - x:{0}, "
                        "y:{1}.".format(self.x_len, self.y_len))
        elif self.x_len < self.threshold or self.y_len < self.threshold:
            self.msg = ("Too few points coordinates to perform regression - x:{0}, "
                        "y:{1}.".format(self.x_len, self.y_len))
        return self.msg


class InvalidSequenceSplitException(GenericRegressionExceptionBase):
    """Raised when the sequence split would produce too few points to use in regression analysis"""
    def __init__(self, parts, ratio):
        super().__init__("")
        self.parts = parts
        self.ratio = ratio

    def __str__(self):
        self.msg = ("Too few points would be produced by splitting the data into {0} "
                    "parts (resulting ratio: {1}).".format(self.parts, self.ratio))
        return self.msg


class InvalidCoeffsException(GenericRegressionExceptionBase):
    """Raised when data format contains unexpected number of coefficient"""
    def __init__(self, coeffs_count):
        super().__init__("")
        self.coeffs_count = coeffs_count

    def __str__(self):
        self.msg = ("Missing coefficients list or their count different from: {0}.".format(
            str(self.coeffs_count)))
        return self.msg


class InvalidModelException(GenericRegressionExceptionBase):
    """Raised when invalid or unknown regression model is requested"""
    def __init__(self, model):
        super().__init__("")
        self.model = model

    def __str__(self):
        self.msg = "Invalid or unsupported regression model: {0}.".format(str(self.model))
        return self.msg


class InvalidTransformationException(GenericRegressionExceptionBase):
    """Raised when invalid or unknown model transformation is requested"""
    def __init__(self, model, transformation):
        super().__init__("")
        self.model = model
        self.transformation = transformation

    def __str__(self):
        self.msg = ("Invalid or unsupported transformation: {0} for model: {1}."
                    .format(str(self.transformation), str(self.model)))
        return self.msg


class StrategyNotImplemented(Exception):
    """Raised when requested computation method/strategy is not implemented"""
    def __init__(self, strategy):
        """
        Arguments:
            strategy(str): the requested strategy
        """
        super().__init__("")
        self.strategy = strategy

    def __str__(self):
        self.msg = ("Requested computation method '{0}' is currently not implemented."
                    .format(self.strategy))
        return self.msg
