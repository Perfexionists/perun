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
        self.parameter = parameter
        self.value = str(parameter_value)
        self.choices_msg = " " + choices_msg

    def __str__(self):
        return "Invalid value '{}' for the parameter '{}'".format(self.value, self.parameter) \
               + self.choices_msg


class MissingConfigSectionException(Exception):
    """Raised when the section in config is missing"""
    pass


class InvalidConfigOperationException(Exception):
    """Raised when the operation given to the config handler is not supported"""
    def __init__(self, store_type, operation, key, value):
        """
        Arguments:
            operation(str): name of the operation
        """
        self.store_type = store_type
        self.operation = operation
        self.key = key
        self.value = value

    def __str__(self):
        msg = "unsupported {} config operation '{}'".format(self.store_type, self.operation)
        msg += "with key '{}'".format(self.key) if self.key and not self.value else ""
        msg += "with value '{}'".format(self.value) if self.value and not self.key else ""
        msg += "with key/value '{}/{}'".format(
            self.key, self.value
        ) if self.value and self.key else ""
        return msg


class ExternalEditorErrorException(Exception):
    """Raised when there is an error while invoking the external editor"""
    def __init__(self, editor, reason):
        """
        Arguments:
            editor(str): name of the invoked editor
            reason(str): reason why the editor failed
        """
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


class DictionaryKeysValidationFailed(Exception):
    """Raised when validated dictionary is actually not a dictionary or has missing/excess keys"""
    def __init__(self, dictionary, missing_keys, excess_keys):
        """
        Arguments:
            dictionary(dict): the validated dictionary
            missing_keys(list): list of missing keys in the dictionary
            excess_keys(list): list of excess forbidden keys in the dictionary
        """
        if type(dictionary) is not dict:
            self.msg = "Validated object '{0}' is not a dictionary.".format(dictionary)
        elif not missing_keys:
            self.msg = "Validated dictionary '{0}' has excess forbidden keys: '{1}'.".format(
                dictionary, ', '.join(excess_keys))
        elif not excess_keys:
            self.msg = "Validated dictionary '{0}' is missing required keys: '{1}'.".format(
                dictionary, ', '.join(missing_keys))
        else:
            self.msg = "Validated dictionary '{0}' has excess forbidden keys: '{1}' "
            "and is missing required keys: '{2}'.".format(dictionary, ', '.join(excess_keys), ', '.join(missing_keys))


# Regression analysis exception hierarchy
class GenericRegressionExceptionBase(Exception):
    """Base class for all regression specific exception

    All specific exceptions should be derived from the base
    - this allows to catch all regression exceptions in one clause

    """
    def __init__(self, msg):
        """Base constructor with exception message"""
        self.msg = msg


class InvalidPointsException(GenericRegressionExceptionBase):
    """Raised when regression data points count is too low or the x and y coordinates count is different"""
    def __init__(self, x_len, y_len, threshold=2, msg=None):
        self.x_len = x_len
        self.y_len = y_len
        if msg is not None:
            self.msg = msg
        elif x_len != y_len:
            self.msg = "Points coordinates x and y have different lengths - x:{0}, y:{1}.".format(x_len, y_len)
        elif x_len < threshold or y_len < threshold:
            self.msg = "Too few points coordinates to perform regression - x:{0}, y:{1}.".format(x_len, y_len)


class InvalidSequenceSplitException(GenericRegressionExceptionBase):
    """Raised when the sequence split would produce too few points to use in regression analysis"""
    def __init__(self, ratio, msg=None):
        self.ratio = ratio
        if msg is not None:
            self.msg = msg
        else:
            self.msg = "Too few points would be produced by splitting the data into {0} parts.".format(ratio)


class InvalidCoeffsException(GenericRegressionExceptionBase):
    """Raised when data format contains unexpected number of coefficient"""
    def __init__(self, coeffs_count, msg=None):
        self.coeffs_count = coeffs_count
        if msg is not None:
            self.msg = msg
        else:
            self.msg = "Missing coefficients list or their count different from: {0}.".format(str(coeffs_count))


class InvalidModelException(GenericRegressionExceptionBase):
    """Raised when invalid or unknown regression model is required"""
    def __init__(self, model, msg=None):
        self.model = model
        if msg is not None:
            self.msg = msg
        else:
            self.msg = "Invalid or unsupported regression model: {0}.".format(str(model))
