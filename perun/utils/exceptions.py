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
    def __init__(self, section_key):
        super().__init__("")
        self.section_key = section_key

    def __str__(self):
        return "key '{}' is not specified in configuration.\nSee docs/config.rst for more details."


class TagOutOfRangeException(Exception):
    """Raised when the requested profile tag is out of range."""
    def __init__(self, position, total):
        super().__init__("")
        self.position = position
        self.total = total

    def __str__(self):
        return "invalid tag '{}' (choose from interval <{}, {}>)".format(
            "{}@i".format(self.position), "0@i", "{}@i".format(self.total))


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
    def __init__(self, entry, cause=""):
        """
        :param str entry: entry we are looking up in the index
        """
        super().__init__("")
        self.entry = entry
        self.cause = cause

    def __str__(self):
        msg = "entry '{}' not".format(self.entry) if self.entry else "none of the entries"
        return msg + " found in the index{}".format(": " + self.cause if self.cause else '')


class IndexNotFoundException(Exception):
    """Raised when the index file for the minor version does not exist"""
    def __init__(self, minor_version):
        """
        :param str minor_version: the minor version that was supposed to have an index file
        """
        super().__init__("")
        self.minor_version = minor_version

    def __str__(self):
        return "Index file for the minor version '{}' was not found.".format(self.minor_version)


class StatsFileNotFoundException(Exception):
    """Raised when the looked up stats file does not exist"""
    def __init__(self, filename):
        super().__init__("")
        self.path = filename
        self.msg = "The requested stats file '{}' does not exist".format(self.path)

    def __str__(self):
        return self.msg


class InvalidTempPathException(Exception):
    """Raised when the looked up temporary path (file or directory) does not exist or the given
    path is of invalid type for the given operation (file path for directory operation etc.)"""
    def __init__(self, msg):
        super().__init__("")
        self.msg = msg

    def __str__(self):
        return self.msg


class ProtectedTempException(Exception):
    """Raised when an attempt to delete protected temp file is made."""
    def __init__(self, msg):
        super().__init__("")
        self.msg = msg

    def __str__(self):
        return self.msg


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


class InvalidBinaryException(Exception):
    """Raised when collector parameter 'binary' is not actually executable ELF file"""
    def __init__(self, binary):
        """
        :param str binary: the supplied binary parameter
        """
        super().__init__("")
        self.binary = binary
        self.msg = ("Supplied binary parameter '{0}' does not exist or is not an "
                    "executable ELF file.".format(self.binary))

    def __str__(self):
        return self.msg


class SystemTapScriptCompilationException(Exception):
    """Raised when an error is encountered during the compilation of a SystemTap script"""
    def __init__(self, logfile, code):
        """
        :param str logfile: log file that contains more details regarding the error
        :param int code: the exit code of the compilation process
        """
        super().__init__("")
        self.logfile = logfile
        self.code = code

    def __str__(self):
        return ("SystemTap script compilation failure (code: {}), see the corresponding {} file."
                .format(self.code, self.logfile))


class SystemTapStartupException(Exception):
    """Raised when a SystemTap error is encountered during its startup"""
    def __init__(self, logfile):
        """
        :param str logfile: log file that contains more details regarding the error
        """
        super().__init__("")
        self.logfile = logfile

    def __str__(self):
        return "SystemTap startup error, see the corresponding {} file.".format(self.logfile)


class HardTimeoutException(Exception):
    """Raised when various sleep calls exceed specified hard timeout threshold"""
    def __init__(self, msg):
        """
        :param str msg: specific exception message
        """
        super().__init__("")
        self.msg = msg
        if not msg:
            self.msg += 'Hard timeout was reached during sleep operation'

    def __str__(self):
        return self.msg


class ResourceLockedException(Exception):
    """Raised when certain trace collector resource is already being used by another process"""
    def __init__(self, resource, pid):
        super().__init__()
        self.resource = resource
        self.pid = pid

    def __str__(self):
        return ("The required resource (binary or kernel module) '{}' is already being used by "
                "another profiling process with a pid {}.".format(self.resource, self.pid))


class MissingDependencyException(Exception):
    """Raised when some dependency is missing on a system"""
    def __init__(self, dependency):
        super().__init__()
        self.dependency = dependency

    def __str__(self):
        return "Missing dependency command '{}'".format(self.dependency)


class UnexpectedPrototypeSyntaxError(Exception):
    """Raised when the function prototype syntax is somehow different than expected"""
    def __init__(self, prototype_name, syntax_error="unknown cause"):
        """
        :param str prototype_name: name of the prototype where the issue happened
        """
        super().__init__("")
        self.prototype_name = prototype_name
        self.cause = syntax_error

    def __str__(self):
        return "prototype of function '{}' is wrong: {}".format(self.prototype_name, self.cause)


class SignalReceivedException(BaseException):
    """Raised when a handled signal is encountered. BaseException used to avoid collision with
    other exception handlers that catch 'Exception' classes."""
    def __init__(self, signum, frame):
        """
        :param int signum: a representation of the encountered signal
        :param object frame: a frame / stack trace object
        """
        super().__init__("")
        self.signum = signum
        self.frame = frame

    def __str__(self):
        return "Received signal: {}".format(self.signum)
