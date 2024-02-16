"""Collection of helper exception classes"""
from __future__ import annotations

# Standard Imports
from typing import Any, TYPE_CHECKING

# Third-Party Imports

# Perun Imports

if TYPE_CHECKING:
    import traceback


class InvalidParameterException(Exception):
    """Raises when the given parameter is invalid"""

    __slots__ = ["parameter", "value", "choices_msg"]

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

    __slots__ = ["section_key"]

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

    __slots__ = ["pos", "total", "tag"]

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

    __slots__ = ["editor", "reason"]

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

    __slots__ = ["reason"]

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

    __slots__ = ["entry", "cause"]

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

    __slots__ = ["minor_version"]

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

    __slots__ = ["path", "msg"]

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

    __slots__ = ["msg"]

    def __init__(self, msg: str) -> None:
        super().__init__("")
        self.msg = msg

    def __str__(self) -> str:
        return self.msg


class ProtectedTempException(Exception):
    """Raised when an attempt to delete protected temp file is made."""

    __slots__ = ["msg"]

    def __init__(self, msg: str) -> None:
        super().__init__("")
        self.msg = msg

    def __str__(self) -> str:
        return self.msg


class VersionControlSystemException(Exception):
    """Raised when there is an issue with wrapped version control system.

    For example, when there is incorrect sha-1 specification of the minor version.
    """

    __slots__ = ["msg", "args"]

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

    __slots__ = ["filename", "msg"]

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

    __slots__ = ["path"]

    def __init__(self, path: str) -> None:
        super().__init__("")
        self.path = path

    def __str__(self) -> str:
        return f"aborted by user: current working dir ({self.path}) is not a Perun repository"


class UnsupportedModuleException(Exception):
    """Raised when dynamically loading a module, that is not supported by the perun"""

    __slots__ = ["module"]

    def __init__(self, module: str) -> None:
        super().__init__("")
        self.module = module

    def __str__(self) -> str:
        return f"Module '{self.module}' is not supported by Perun"


class DictionaryKeysValidationFailed(Exception):
    """Raised when validated dictionary is actually not a dictionary or has missing/excess keys"""

    __slots__ = ["dictionary", "missing_keys", "excess_keys", "msg"]

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
        self.msg = (
            f"Invalid dictionary {self.dictionary} "
            f"with forbidden keys ({', '.join(self.excess_keys)})"
            f" and missing keys ({', '.join(self.missing_keys)})."
        )

    def __str__(self) -> str:
        return self.msg


# Regression analysis exception hierarchy
class GenericRegressionExceptionBase(Exception):
    """Base class for all regression specific exception

    All specific exceptions should be derived from the base
    - this allows to catch all regression exceptions in one clause

    """

    __slots__ = ["msg"]

    def __init__(self, msg: str) -> None:
        """Base constructor with exception message"""
        super().__init__("")
        self.msg = msg


class InvalidPointsException(GenericRegressionExceptionBase):
    """Raised when regression data points count is too low or
    the x and y coordinates count is different"""

    __slots__ = ["x_len", "y_len", "threshold", "too_few", "msg"]

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

    __slots__ = ["parts", "ratio", "msg"]

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

    __slots__ = ["model", "msg"]

    def __init__(self, model: str) -> None:
        super().__init__("")
        self.model = model
        self.msg = f"Invalid or unsupported regression model: {self.model}."

    def __str__(self) -> str:
        return self.msg


class InvalidTransformationException(GenericRegressionExceptionBase):
    """Raised when invalid or unknown model transformation is requested"""

    __slots__ = ["model", "transformation", "msg"]

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

    __slots__ = ["binary", "msg"]

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

    __slots__ = ["logfile", "code"]

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

    __slots__ = ["logfile"]

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

    __slots__ = ["resource", "pid"]

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

    __slots__ = ["dependency"]

    def __init__(self, dependency: str) -> None:
        super().__init__()
        self.dependency = dependency

    def __str__(self) -> str:
        return f"Missing dependency command '{self.dependency}'"


class UnexpectedPrototypeSyntaxError(Exception):
    """Raised when the function prototype syntax is somehow different from expected"""

    __slots__ = ["prototype_name", "cause"]

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

    __slots__ = ["signum", "frame"]

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


class SuppressedExceptions:
    """Context manager class for code blocks that need to suppress / ignore some exceptions
    and simply continue in the execution if those exceptions are encountered.

    :ivar list exc: the list of exception classes that should be ignored
    """

    def __init__(self, *exception_list: type[Exception]) -> None:
        """
        :param exception_list: the exception classes to ignore
        """
        self.exc = exception_list

    def __enter__(self) -> "SuppressedExceptions":
        """Context manager entry sentinel, no set up needed

        :return object: the context manager class instance, shouldn't be needed
        """
        return self

    def __exit__(self, exc_type: str, exc_val: Exception, exc_tb: traceback.StackSummary) -> bool:
        """Context manager exit sentinel, check if the code raised an exception and if the
        exception belongs to the list of suppressed exceptions.

        :param type exc_type: the type of the exception
        :param exception exc_val: the value of the exception
        :param traceback exc_tb: the traceback of the exception
        :return bool: True if the encountered exception should be ignored, False otherwise or if
                      no exception was raised
        """
        return isinstance(exc_val, tuple(self.exc))
