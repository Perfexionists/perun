"""List of helper and globally used structures and named tuples"""

from __future__ import annotations

# Standard Imports
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Any, TYPE_CHECKING, cast, Callable, Protocol
import enum
import shlex
import signal

# Third-Party Imports

# Perun Imports
from perun.utils.common import common_kit
from perun.utils.common.common_kit import ColorChoiceType, PROFILE_TRACKED, PROFILE_UNTRACKED
from perun.utils.exceptions import SignalReceivedException, SuppressedExceptions

if TYPE_CHECKING:
    import types
    import traceback

    import numpy.typing as npt
    import numpy

# TODO: think about breaking this into more modules and/or renaming it to something better


class SignalCallback(Protocol):
    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...


@dataclass
class GeneratorSpec:
    __slots__ = ["constructor", "params"]

    constructor: Callable[..., Any]
    params: dict[str, Any]


class PerformanceChange(Enum):
    Unknown = -6
    NotInBaseline = -5
    TotalDegradation = -4
    SevereDegradation = -3
    Degradation = -2
    MaybeDegradation = -1
    NoChange = 0
    MaybeOptimization = 1
    Optimization = 2
    SevereOptimization = 3
    TotalOptimization = 4
    NotInTarget = 5


CHANGE_STRINGS: dict[PerformanceChange, str] = {
    PerformanceChange.NotInBaseline: "Not in Baseline",
    PerformanceChange.TotalDegradation: "Total Degradation",
    PerformanceChange.SevereDegradation: "Severe Degradation",
    PerformanceChange.Degradation: "Degradation",
    PerformanceChange.MaybeDegradation: "Maybe Degradation",
    PerformanceChange.NoChange: "No Change",
    PerformanceChange.Unknown: "Unknown",
    PerformanceChange.MaybeOptimization: "Maybe Optimization",
    PerformanceChange.Optimization: "Optimization",
    PerformanceChange.SevereOptimization: "Severe Optimization",
    PerformanceChange.TotalOptimization: "Total Optimization",
    PerformanceChange.NotInTarget: "Not in Target",
}
CHANGE_COLOURS: dict[PerformanceChange, ColorChoiceType] = {
    PerformanceChange.NotInBaseline: "blue",
    PerformanceChange.TotalDegradation: "red",
    PerformanceChange.SevereDegradation: "red",
    PerformanceChange.Degradation: "red",
    PerformanceChange.MaybeDegradation: "yellow",
    PerformanceChange.NoChange: "white",
    PerformanceChange.Unknown: "grey",
    PerformanceChange.MaybeOptimization: "cyan",
    PerformanceChange.Optimization: "green",
    PerformanceChange.SevereOptimization: "green",
    PerformanceChange.TotalOptimization: "green",
    PerformanceChange.NotInTarget: "blue",
}


class CollectStatus(Enum):
    """Simple enumeration for statuses of the collectors"""

    OK = 0
    ERROR = 1


class PostprocessStatus(Enum):
    """Simple enumeration for statuses of the postprocessors"""

    OK = 0
    ERROR = 1


class RunnerReport:
    """Collection of results reported during the running of the unit

    :ivar status: overall status of the whole run of the unit, one of the CollectStatus or
        PostprocessStatus enum
    :ivar runner: module of the collector or postprocessor
    :ivar runner_type: string name of the runner type, either collector or postprocessor
    :ivar stat_code: sub status returned by the unit, 0 if nothing happened
    :ivar phase: name of the last executed phase (before, collect/postprocess, after)
    :ivar exception: exception (if it was raised) during the run otherwise None
    :ivar message: string message describing the result of run
    :ivar kwargs: kwargs of the process (should include "profile")
    """

    ok_statuses: dict[str, CollectStatus | PostprocessStatus] = {
        "collector": CollectStatus.OK,
        "postprocessor": PostprocessStatus.OK,
    }
    error_statues: dict[str, CollectStatus | PostprocessStatus] = {
        "collector": CollectStatus.ERROR,
        "postprocessor": PostprocessStatus.ERROR,
    }
    __slots__ = [
        "ok_status",
        "error_status",
        "runner",
        "runner_type",
        "status",
        "stat_code",
        "phase",
        "exception",
        "message",
        "kwargs",
    ]

    def __init__(self, runner: types.ModuleType, runner_type: str, kwargs: Any) -> None:
        """
        :param runner: module of the runner
        :param runner_type: type of the runner (either 'collector' or 'postprocessor'
        :param kwargs: initial keyword arguments
        """
        self.ok_status = RunnerReport.ok_statuses[runner_type]
        self.error_status = RunnerReport.error_statues[runner_type]

        self.runner: types.ModuleType = runner
        self.runner_type: str = runner_type
        self.status: CollectStatus | PostprocessStatus = self.ok_status
        self.stat_code: int | Enum = 0
        self.phase: str = "init"
        self.exception: Optional[BaseException] = None
        self.message: str = "OK"
        self.kwargs: dict[str, Any] = kwargs

    def update_from(self, stat_code: int | enum.Enum, message: str, params: dict[str, Any]) -> None:
        """Updates the report according to the successful results of one of the phases

        :param stat_code: returned code of the run
        :param message: additional message about the run process
        :param params: updated params
        :return:
        """
        self.stat_code = stat_code
        self.kwargs.update(params or {})

        is_enum = hasattr(self.stat_code, "value")
        if not (self.stat_code == 0 or (is_enum and cast(Enum, self.stat_code).value == 0)):
            self.status = self.error_status

        # Update the message; delete the assumed OK if error occurred
        if not self.is_ok() and self.message == "OK":
            self.message = ""
        self.message += message

    def is_ok(self) -> bool:
        """Checks if the status of the collection or postprocessing is so far ok

        :return: true if the status is OK
        """
        return self.status == self.ok_status


class Executable:
    """Represents executable command with arguments and workload

    :ivar cmd: command to be executed (i.e. script, binary, etc.); including arguments
    :ivar workload: optional workloads (or inputs) of the command (i.e. files, whatever)
    :ivar original_workload: workload that was used as an origin (stated from the configuration),
        note that this is to differentiate between actually generated workloads from generators and
        names of the generators.
    """

    __slots__ = ["cmd", "workload", "origin_workload"]

    def __init__(self, cmd: str, workload: str = "") -> None:
        """Initializes the executable

        :param cmd: command to be executed
        :param workload: optional workloads of the command
        """
        self.cmd: str = cmd
        self.workload: str = workload
        self.origin_workload: str = workload

    def __str__(self) -> str:
        """Returns nonescaped, nonlexed string representation of the executable

        :return: string representation of executable
        """
        executable = self.cmd
        executable += " " + self.workload if self.workload else ""
        return executable

    def to_escaped_string(self) -> str:
        """Returns escaped string representation of executable

        :return: escaped string representation of executable
        """
        executable = shlex.quote(self.cmd)
        executable += " " + self.workload if self.workload else ""
        return executable


class Unit:
    """Specification of the unit that is part of run process

    :ivar name: name of the unit
    :ivar params: parameters for the unit
    """

    __slots__ = ["name", "params"]

    def __init__(self, name: str, params: dict[str, Any]) -> None:
        """Constructs the unit, with name being sanitized

        :param name: name of the unit
        :param params: parameters for the unit
        """
        self.name: str = Unit.sanitize_unit_name(name)
        self.params: dict[str, Any] = params

    @classmethod
    def desanitize_unit_name(cls, unit_name: str) -> str:
        """Replace the underscores in the unit name in order for it to be CLI compatible.

        In Click 7.0 all subcommands have automatically replaced underscores (_) with dashes (-).
        We have to sanitize/desanitize the unit name through the Perun.

        :param unit_name: name of the unit that is desanitized
        :return:
        """
        return unit_name.replace("_", "-")

    @classmethod
    def sanitize_unit_name(cls, unit_name: str) -> str:
        """Sanitizes module name in order for it to be usable and uniform in the perun.

        As of Click 7.0 in all subcommands underscores (_) are automatically replaced by dashes (-).
        While this is surely nice feature, Perun works with the Python function names that actually
        DO have underscores. So we basically support both formats, and in CLI we use only -, but use
        this fecking function to make sure the CLI names are replaced back to underscores. Rant
        over.

        :param unit_name: module name that we are sanitizing
        :return: sanitized module name usable inside the Perun (with underscores instead of dashes)
        """
        return unit_name.replace("-", "_")


@dataclass
class DetectionChangeResult:
    """

    :ivar result: result of the performance change,
        either can be optimization, degradation, no change, or certain type of unknown
    :ivar relative_rate: relative rate of the degradation
    :ivar partial_intervals: finer specification of the change, i.e. in which intervals it occured
    """

    __slots__ = ["result", "relative_rate", "partial_intervals"]

    def __init__(
        self,
        res: PerformanceChange,
        rdr: float,
        pi: Optional[list[tuple[PerformanceChange, float, float, float]]] = None,
    ):
        self.result: PerformanceChange = res
        self.relative_rate: float = rdr
        self.partial_intervals: Optional[list[tuple[PerformanceChange, float, float, float]]] = (
            pi if pi is not None else []
        )


class DegradationInfo:
    """The returned results for performance check methods

    :ivar result: result of the performance change, either can be optimization,
        degradation, no change, or certain type of unknown
    :ivar type: string representing the type of the degradation, e.g. "order" degradation
    :ivar location: location, where the degradation has happened
    :ivar from_baseline: value or model representing the baseline, i.e. from which the new
        version was optimized or degraded
    :ivar to_target: value or model representing the target, i.e. to which the new version was
        optimized or degraded
    :ivar confidence_type: type of the confidence we have in the detected degradation, e.g. r^2
    :ivar confidence_rate: value of the confidence we have in the detected degradation
    :ivar rate_degradation_relative: relative rate of the degradation
    """

    __slots__ = [
        "result",
        "type",
        "location",
        "from_baseline",
        "to_target",
        "rate_degradation",
        "confidence_type",
        "confidence_rate",
        "partial_intervals",
        "rate_degradation_relative",
    ]

    def __init__(
        self,
        res: PerformanceChange,
        loc: str,
        fb: str,
        tt: str,
        t: str = "-",
        rd: float = 0,
        ct: str = "no",
        cr: float = 0,
        pi: Optional[list[tuple[PerformanceChange, float, float, float]]] = None,
        rdr: float = 0.0,
    ) -> None:
        """Each degradation consists of its results, the location, where the change has happened
        (this is e.g. the unique id of the resource, like function or concrete line), then the pair
        of best models for baseline and target, and the information about confidence.

        E.g. for models we can use coefficient of determination as some kind of confidence, e.g. the
        higher the confidence the more likely we predicted successfully the degradation or
        optimization.

        :param res: result of the performance change, either can be optimization,
            degradation, no change, or certain type of unknown
        :param t: string representing the type of the degradation, e.g. "order" degradation
        :param loc: location, where the degradation has happened
        :param fb: value or model representing the baseline, i.e. from which the new version was
            optimized or degraded
        :param tt: value or model representing the target, i.e. to which the new version was
            optimized or degraded
        :param rd: quantified rate of the degradation, i.e. how much exactly it degrades
        :param ct: type of the confidence we have in the detected degradation, e.g. r^2
        :param cr: value of the confidence we have in the detected degradation
        :param rdr: relative rate of the degradation (i.e. to the entire program run)
        """
        self.result: PerformanceChange = res
        self.type: str = t
        self.location: str = loc
        self.from_baseline: str = fb
        self.to_target: str = tt
        self.rate_degradation: float = rd
        self.confidence_type: str = ct
        self.confidence_rate: float = cr
        self.partial_intervals: list[tuple[PerformanceChange, float, float, float]] = (
            pi if pi is not None else []
        )
        self.rate_degradation_relative: float = rdr

    def to_storage_record(self) -> str:
        """Transforms the degradation info to a storage_record

        :return: string representation of the degradation as a stored record in the file
        """
        return "{} {} {} {} {} {} {} {} {}".format(
            self.location,
            self.result,
            self.type,
            self.from_baseline,
            self.to_target,
            self.rate_degradation,
            self.confidence_type,
            self.confidence_rate,
            self.rate_degradation_relative,
        )


@dataclass
class Job:
    """Represents one profiling task in the Perun

    :ivar collector: collection unit used to collect the SUP
    :ivar postprocessors: list of postprocessing units applied after the collection
    :ivar executable: System Under Profiling (SUP)
    """

    __slots__ = ["collector", "postprocessors", "executable"]

    collector: Unit
    postprocessors: list[Unit]
    executable: Executable

    def _asdict(self) -> dict[str, Any]:
        """
        :return: representation as dictionary
        """
        return {
            "collector": self.collector,
            "postprocessors": self.postprocessors,
            "executable": self.executable,
        }


class OrderedEnum(Enum):
    """An ordered enumeration structure that ranks the elements so that they can be compared
    wrt their order. Taken from:
        https://stackoverflow.com/questions/42369749/use-definition-order-of-enum-as-natural-order

    :ivar order: the order of the new element
    """

    def __init__(self, *args: Any) -> None:
        """Create the new enumeration element and compute its order.

        :param args: additional element arguments
        """
        with SuppressedExceptions(TypeError):
            # attempt to initialize other parents in the hierarchy
            super().__init__(*args)
        ordered = len(self.__class__.__members__) + 1
        self.order: int = ordered

    def __ge__(self, other: object) -> bool:
        """Comparison operator >=.

        :param other: the other enumeration element
        :return: the comparison result
        """
        if isinstance(other, self.__class__):
            return self.order >= other.order
        return NotImplemented

    def __gt__(self, other: object) -> bool:
        """Comparison operator >.

        :param other: the other enumeration element
        :return: the comparison result
        """
        if isinstance(other, self.__class__):
            return self.order > other.order
        return NotImplemented

    def __le__(self, other: object) -> bool:
        """Comparison operator <=.

        :param other: the other enumeration element
        :return: the comparison result
        """
        if isinstance(other, self.__class__):
            return self.order <= other.order
        return NotImplemented

    def __lt__(self, other: object) -> bool:
        """Comparison operator <.

        :param other: the other enumeration element
        :return: the comparison result
        """
        if isinstance(other, self.__class__):
            return self.order < other.order
        return NotImplemented


class ProfileListConfig:
    """
    :ivar colour: colour of the printed list
    :ivar ending: ending for summary of the number of profiles
    :ivar list_len: length of the profile list
    :ivar id_char: character that represents either pending (p) or indexed (i) profiles
    :ivar id_width: number of characters needed for the left column that counts the index of
        the profile in the list
    :ivar header_width: overall width of the profile list
    """

    __slots__ = ["colour", "ending", "list_len", "id_char", "id_width", "header_width"]

    def __init__(self, list_type: str, short: bool, profile_list: list[Any]) -> None:
        """Initializes the configuration for the profile list.

        :param list_type: type of the profile list (either untracked or untracked)
        :param short: true if the list should be short
        :param profile_list: list of profiles
        """
        self.colour: ColorChoiceType = (
            PROFILE_UNTRACKED if list_type != "tracked" else PROFILE_TRACKED
        )
        self.ending: str = ":\n\n" if not short else "\n"
        self.list_len: int = len(profile_list)
        self.id_char: str = "i" if list_type == "tracked" else "p"
        self.id_width: int = len(str(self.list_len))
        # The magic 3 corresponds to the fixed string @p or @i
        self.header_width: int = self.id_width + 3


@dataclass()
class MinorVersion:
    """Single MinorVersion (commit) from the Version Control System

    :ivar data: date when the minor version was commited
    :ivar author: author of the minor version
    :ivar email: email of the author of the minor version
    :ivar checksum: sha checksum of the minor version
    :ivar desc: description of the changes commited in the minor version
    :ivar parents: list of parents of the minor version (empty if root)
    """

    __slots__ = ["date", "author", "email", "checksum", "desc", "parents"]

    date: str
    author: Optional[str]
    email: Optional[str]
    checksum: str
    desc: str
    parents: list[str]

    def to_short(self) -> MinorVersion:
        """Returns corresponding minor version with shorted one-liner description

        :return: minor version with one line description
        """
        return MinorVersion(
            self.date,
            self.author,
            self.email,
            self.checksum,
            self.desc.split("\n")[0],
            self.parents,
        )

    @staticmethod
    def valid_fields() -> list[str]:
        """
        :return: list of valid fields in the dataclass
        """
        return ["date", "author", "email", "checksum", "desc", "parents"]


@dataclass()
class MajorVersion:
    """Single Major Version (branch) of the Version Control System

    :ivar name: name of the major version
    :ivar head: sha checksum of the corresponding head minor version
    """

    __slots__ = ["name", "head"]

    name: str
    head: str


@dataclass()
class ModelRecord:
    """
    Helper class for holding the model parts

    :ivar type: type of the model (i.e. its class)
    :ivar r_square: R^2 value of the model
    :ivar b0: constant coefficient of the model
    :ivar b1: slope coefficient of the model
    :ivar b2: quadratic coefficient of the model
    :ivar x_start: start of the interval, where the model holds
    :ivar x_end: end of the interval, where the model holds
    """

    __slots__ = ["type", "r_square", "b0", "b1", "b2", "x_start", "x_end"]

    type: str
    r_square: float
    b0: float | npt.NDArray[numpy.float64]
    b1: float
    b2: float
    x_start: float
    x_end: float

    def coeff_size(self) -> int:
        """Counts the number of coefficients in the model

        :return: length of the bins if the model is bin-like, else number of non-zero coefficients
        """
        return len(self.b0) if hasattr(self.b0, "__len__") else 1 + self.b1 != 0.0 + self.b2 != 0.0


class ClassificationMethod(Enum):
    FastCheck = 1
    LinearRegression = 2
    PolynomialRegression = 3


class HandledSignals:
    """Context manager for code blocks that need to handle one or more signals during their
    execution.

    The CM offers a default signal handler and a default handler exception. In this scenario, the
    code execution is interrupted when the registered signals are encountered and - if provided -
    a callback function is invoked.

    After the callback, previous signal handlers are re-registered and the CM ends. If an exception
    not related to the signal handling was encountered, it is re-raised after resetting the signal
    handlers and (if set) invoking the callback function.

    The callback function prototype is flexible, and the required arguments can be supplied by
    the callback_args parameter. However, it should always accept the **kwargs arguments because
    of the exc_type, exc_val and exc_tb arguments provided by the __exit__ function. This allows
    the programmer to decide e.g. if certain parts of the callback code should be executed, based
    on the raised exception - or the lack of an exception, that is.

    A custom signal handler function can be supplied. In this case, the prototype should oblige
    the rules of signal handling functions: func_name(signal_number, frame). If the custom signal
    handling function uses a different exception then the default, it should be supplied to the CM
    as well.

    :ivar signals: the list of signals that are being handled by the CM
    :ivar handler: the function used to handle the registered signals
    :ivar handler_exc: the exception type related to the signal handler
    :ivar callback: the function that is always invoked during the CM exit
    :ivar callback_args: arguments for the callback function
    :ivar old_handlers: the list of previous signal handlers
    """

    __slots__ = ["signals", "handler", "handler_exc", "callback", "callback_args", "old_handlers"]

    def __init__(self, *signals: int, **kwargs: Any) -> None:
        """
        :param signals: the identification of the handled signal, 'signal.SIG_' is recommended
        :param kwargs: additional properties of the context manager
        """
        self.signals: tuple[int, ...] = signals
        self.handler: Callable[[int, types.FrameType | None], None] = kwargs.get(
            "handler", common_kit.default_signal_handler
        )
        self.handler_exc: type[Exception | BaseException] = kwargs.get(
            "handler_exception", SignalReceivedException
        )
        self.callback: SignalCallback | None = kwargs.get("callback")
        self.callback_args: list[Any] = kwargs.get("callback_args", [])
        self.old_handlers: list[Callable[[int, types.FrameType | None], Any] | int | None] = []

    def __enter__(self) -> HandledSignals:
        """The CM entry sentinel, register the new signal handlers and store the previous ones.

        :return: the CM instance
        """
        for sig in self.signals:
            self.old_handlers.append(signal.signal(sig, self.handler))
        return self

    def __exit__(self, exc_type: str, exc_val: Exception, exc_tb: traceback.StackSummary) -> bool:
        """The CM exit sentinel, perform the callback and reset the signal handlers.

        :param exc_type: the type of the exception
        :param exc_val: the value of the exception
        :param exc_tb: the traceback of the exception
        :return: True if the encountered exception should be ignored, False otherwise or if
                      no exception was raised
        """
        # Ignore all the handled signals temporarily
        for sig in self.signals:
            signal.signal(sig, signal.SIG_IGN)
        # Perform the callback
        if self.callback:
            self.callback(*self.callback_args, exc_type=exc_type, exc_val=exc_val, exc_tb=exc_tb)
        # Reset the signal handlers
        for sig, sig_handler in zip(self.signals, self.old_handlers):
            signal.signal(sig, sig_handler)
        # Re-raise exceptions not related to signal handling done by the CM (e.g., SignalReceivedE.)
        return isinstance(exc_val, self.handler_exc)


class SortOrder(Enum):
    """Enumeration representing sorting order in a more descriptive way compared to the library."""

    Ascending = "asc"
    Descending = "desc"

    @staticmethod
    def supported() -> list[str]:
        """Obtain the collection of supported sort orders.

        :return: the collection of valid sort orders
        """
        return [order.value for order in SortOrder]

    @staticmethod
    def default() -> str:
        """Provide the default sort order.

        :return: the default sort order
        """
        return SortOrder.Ascending.value

    def as_sort_flag(self) -> bool:
        """Translates the sort order into the library bool representation.

        :return: False if the sort order is ascending, True otherwise
        """
        return self.value == SortOrder.Descending.value


class WebColorPalette:
    """Colour palette for HTML/JS visualizations.

    In case of using var(...) one should look
    inside perun/templates/style/general_setup.css
    where all variables are defined.
    """

    Baseline: str = "var(--color-baseline)"
    Target: str = "var(--color-target)"
    Increase: str = "rgba(255, 0, 0, 0.7)"
    Decrease: str = "rgba(0, 255, 0, 0.7)"
    Equal: str = "var(--color-common)"
    DarkTarget: str = "rgba(255, 201, 74, 1)"
    DarkBaseline: str = "rgba(49, 48, 77, 1)"
    DarkIncrease: str = "var(--color-wrong)"
    DarkDecrease: str = "var(--color-correct)"
    DarkEqual: str = "#27aeef"
    Highlight: str = "rgba(0, 0, 0, 0.7)"
    NoHighlight: str = "rgba(0, 0, 0, 0.2)"
