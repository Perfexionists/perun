"""Collection of helper exception classes"""
from __future__ import annotations

import traceback
from typing import Any


class InvalidParameterException(Exception):
    """Raises when the given parameter is invalid"""

    def __init__(self, parameter: str, parameter_value: Any, choices_msg: str = "") -> None:
        """
        :param str parameter: name of the parameter that is invalid
        :param object parameter_value: value of the parameter
        :param str choices_msg: string with choices for the valid parameters
        """
        super().__init__("")
        self.parameter = parameter
        self.value = str(parameter_value)
        self.choices_msg = " " + choices_msg

    def __str__(self) -> str:
        return (
            f"Invalid value '{self.value}' for the parameter '{self.parameter}'" + self.choices_msg
        )


class MissingConfigSectionException(Exception):
    """Raised when the section in config is missing"""

    def __init__(self, section_key: str) -> None:
        super().__init__("")
        self.section_key = section_key

    def __str__(self) -> str:
        return (
            f"key '{self.section_key}' is not specified in configuration.\n"
            "See docs/config.rst for more details."
        )


class TagOutOfRangeException(Exception):
    """Raised when the requested profile tag is out of range."""

    def __init__(self, position: int, total: int, tag_source: str) -> None:
        super().__init__("")
        self.pos = position
        self.total = total
        self.tag = tag_source

    def __str__(self) -> str:
        return (
            f"invalid tag '{self.pos}@{self.tag}' (choose from interval <0@{self.tag},"
            f" {self.total}@{self.tag}>)"
        )


class ExternalEditorErrorException(Exception):
    """Raised when there is an error while invoking the external editor"""

    def __init__(self, editor: str, reason: str) -> None:
        """
        :param str editor: name of the invoked editor
        :param str reason: reason why the editor failed
        """
        super().__init__("")
        self.editor = editor
        self.reason = reason

    def __str__(self) -> str:
        return f"error while invoking external '{self.editor}' editor: {self.reason}"


class MalformedIndexFileException(Exception):
    """Raised when the read index is malformed"""

    def __init__(self, reason: str) -> None:
        """
        :param str reason: the reason that the index is considered to be malformed
        """
        super().__init__("")
        self.reason = reason

    def __str__(self) -> str:
        return f"working with malformed index file: {self.reason}"


class EntryNotFoundException(Exception):
    """Raised when the looked up entry is not within the index"""

    def __init__(self, entry: str, cause: str = "") -> None:
        """
        :param str entry: entry we are looking up in the index
        """
        super().__init__("")
        self.entry = entry
        self.cause = cause

    def __str__(self) -> str:
        msg = f"entry '{self.entry}' not" if self.entry else "none of the entries"
        return msg + f" found in the index{': ' + self.cause if self.cause else ''}"


class IndexNotFoundException(Exception):
    """Raised when the index file for the minor version does not exist"""

    def __init__(self, minor_version: str) -> None:
        """
        :param str minor_version: the minor version that was supposed to have an index file
        """
        super().__init__("")
        self.minor_version = minor_version

    def __str__(self) -> str:
        return f"Index file for the minor version '{self.minor_version}' was not found."


class StatsFileNotFoundException(Exception):
    """Raised when the looked up stats file does not exist"""

    def __init__(self, filename: str) -> None:
        super().__init__("")
        self.path = filename
        self.msg = f"The requested stats file '{self.path}' does not exist"

    def __str__(self) -> str:
        return self.msg


class InvalidTempPathException(Exception):
    """Raised when the looked up temporary path (file or directory) does not exist or the given
    path is of invalid type for the given operation (file path for directory operation etc.)
    """

    def __init__(self, msg: str) -> None:
        super().__init__("")
        self.msg = msg

    def __str__(self) -> str:
        return self.msg


class ProtectedTempException(Exception):
    """Raised when an attempt to delete protected temp file is made."""

    def __init__(self, msg: str) -> None:
        super().__init__("")
        self.msg = msg

    def __str__(self) -> str:
        return self.msg


class VersionControlSystemException(Exception):
    """Raised when there is an issue with wrapped version control system.

    For example, when there is incorrect sha-1 specification of the minor version.
    """

    def __init__(self, msg: str, *args: Any) -> None:
        """
        :param str msg: format string of the error message
        :param list args: list of arguments for format string
        """
        super().__init__(msg)
        self.msg = msg
        self.args = args

    def __str__(self) -> str:
        return self.msg.format(*self.args)


class IncorrectProfileFormatException(Exception):
    """Raised when the file is missing or the given format is not in the unified json format"""

    def __init__(self, filename: str, msg: str) -> None:
        """
        :param str filename: filename of the profile in the wrong format
        :param str msg: additional message what is wrong withe profile
        """
        super().__init__("")
        self.filename = filename
        self.msg = msg

    def __str__(self) -> str:
        return self.msg.format(self.filename)


class NotPerunRepositoryException(Exception):
    """Raised when command is not called from within the scope of any Perun repository"""

    def __init__(self, path: str) -> None:
        super().__init__("")
        self.path = path

    def __str__(self) -> str:
        return f"Current working dir is not a perun repository (or any parent on path {self.path})"


class UnsupportedModuleException(Exception):
    """Raised when dynamically loading a module, that is not supported by the perun"""

    def __init__(self, module: str) -> None:
        super().__init__("")
        self.module = module

    def __str__(self) -> str:
        return f"Module '{self.module}' is not supported by Perun"


class UnsupportedModuleFunctionException(Exception):
    """Raised when supported module does not support the given function.

    I.e. there is no implementation of the given function.
    """

    def __init__(self, module: str, func: str) -> None:
        """
        :param str module: name of the module that does not support the given function
        """
        super().__init__("")
        self.module = module
        self.func = func

    def __str__(self) -> str:
        return f"Function '{self.module}' is not implemented within the '{self.func}' module"


class DictionaryKeysValidationFailed(Exception):
    """Raised when validated dictionary is actually not a dictionary or has missing/excess keys"""

    def __init__(
        self,
        dictionary: dict[str, Any],
        missing_keys: list[str],
        excess_keys: list[str],
    ) -> None:
        """
        :param dict dictionary: the validated dictionary
        :param list missing_keys: list of missing keys in the dictionary
        :param list excess_keys: list of excess forbidden keys in the dictionary
        """
        super().__init__("")
        self.dictionary = dictionary
        self.missing_keys = missing_keys or []
        self.excess_keys = excess_keys or []
        self.msg = "Invalid dictionary {} with forbidden keys ({}) and missing keys ({}).".format(
            self.dictionary, ", ".join(self.excess_keys), ", ".join(self.missing_keys)
        )

    def __str__(self) -> str:
        return self.msg


# Regression analysis exception hierarchy
class GenericRegressionExceptionBase(Exception):
    """Base class for all regression specific exception

    All specific exceptions should be derived from the base
    - this allows to catch all regression exceptions in one clause

    """

    def __init__(self, msg: str) -> None:
        """Base constructor with exception message"""
        super().__init__("")
        self.msg = msg


class InvalidPointsException(GenericRegressionExceptionBase):
    """Raised when regression data points count is too low or
    the x and y coordinates count is different"""

    def __init__(self, x_len: int, y_len: int, threshold: int) -> None:
        super().__init__("")
        self.x_len = x_len
        self.y_len = y_len
        self.threshold = threshold
        self.too_few = self.x_len < self.threshold or self.y_len < self.threshold
        self.msg = "{0} point coordinates to perform regression - x:{1}, y:{2}.".format(
            "Too few" if self.too_few else "Different", self.x_len, self.y_len
        )

    def __str__(self) -> str:
        return self.msg


class InvalidSequenceSplitException(GenericRegressionExceptionBase):
    """Raised when the sequence split would produce too few points to use in regression analysis"""

    def __init__(self, parts: float, ratio: float) -> None:
        super().__init__("")
        self.parts = parts
        self.ratio = ratio
        self.msg = (
            f"Too few points would be produced by splitting the data into {self.parts} parts "
            f"(resulting ratio: {self.ratio})."
        )

    def __str__(self) -> str:
        return self.msg


class InvalidModelException(GenericRegressionExceptionBase):
    """Raised when invalid or unknown regression model is requested"""

    def __init__(self, model: str) -> None:
        super().__init__("")
        self.model = model
        self.msg = f"Invalid or unsupported regression model: {self.model}."

    def __str__(self) -> str:
        return self.msg


class InvalidTransformationException(GenericRegressionExceptionBase):
    """Raised when invalid or unknown model transformation is requested"""

    def __init__(self, model: str, transformation: str) -> None:
        super().__init__("")
        self.model = model
        self.transformation = transformation
        self.msg = (
            f"Invalid or unsupported transformation: {self.transformation} for model: {self.model}."
        )

    def __str__(self) -> str:
        return self.msg


class InvalidBinaryException(Exception):
    """Raised when collector parameter 'binary' is not actually executable ELF file"""

    def __init__(self, binary: str) -> None:
        """
        :param str binary: the supplied binary parameter
        """
        super().__init__("")
        self.binary = binary
        self.msg = (
            f"Supplied binary parameter '{self.binary}' does not exist or is not an executable ELF"
            " file."
        )

    def __str__(self) -> str:
        return self.msg


class SystemTapScriptCompilationException(Exception):
    """Raised when an error is encountered during the compilation of a SystemTap script"""

    def __init__(self, logfile: str, code: int) -> None:
        """
        :param str logfile: log file that contains more details regarding the error
        :param int code: the exit code of the compilation process
        """
        super().__init__("")
        self.logfile = logfile
        self.code = code

    def __str__(self) -> str:
        return (
            f"SystemTap script compilation failure (code: {self.code}), see the corresponding"
            f" {self.logfile} file."
        )


class SystemTapStartupException(Exception):
    """Raised when a SystemTap error is encountered during its startup"""

    def __init__(self, logfile: str) -> None:
        """
        :param str logfile: log file that contains more details regarding the error
        """
        super().__init__("")
        self.logfile = logfile

    def __str__(self) -> str:
        return f"SystemTap startup error, see the corresponding {self.logfile} file."


class ResourceLockedException(Exception):
    """Raised when certain trace collector resource is already being used by another process"""

    def __init__(self, resource: str, pid: int) -> None:
        super().__init__()
        self.resource = resource
        self.pid = pid

    def __str__(self) -> str:
        return (
            f"The required resource (binary or kernel module) '{self.resource}' "
            f"is already being used by another profiling process with a pid {self.pid}."
        )


class MissingDependencyException(Exception):
    """Raised when some dependency is missing on a system"""

    def __init__(self, dependency: str) -> None:
        super().__init__()
        self.dependency = dependency

    def __str__(self) -> str:
        return f"Missing dependency command '{self.dependency}'"


class UnexpectedPrototypeSyntaxError(Exception):
    """Raised when the function prototype syntax is somehow different than expected"""

    def __init__(self, prototype_name: str, syntax_error: str = "unknown cause") -> None:
        """
        :param str prototype_name: name of the prototype where the issue happened
        """
        super().__init__()
        self.prototype_name = prototype_name
        self.cause = syntax_error

    def __str__(self) -> str:
        return f"wrong prototype of function '{self.prototype_name}': {self.cause}"


class SignalReceivedException(BaseException):
    """Raised when a handled signal is encountered. BaseException used to avoid collision with
    other exception handlers that catch 'Exception' classes."""

    def __init__(self, signum: int, frame: traceback.StackSummary) -> None:
        """
        :param int signum: a representation of the encountered signal
        :param object frame: a frame / stack trace object
        """
        super().__init__("")
        self.signum = signum
        self.frame = frame

    def __str__(self) -> str:
        return f"Received signal: {self.signum}"
