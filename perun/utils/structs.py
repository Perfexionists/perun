"""List of helper and globally used structures and named tuples"""
from __future__ import annotations

import collections
import enum
import shlex
import types
from dataclasses import dataclass

from enum import Enum
from typing import Optional, Any, TYPE_CHECKING, cast

if TYPE_CHECKING:
    import numpy.typing as npt
    import numpy


GeneratorSpec = collections.namedtuple("GeneratorSpec", "constructor params")


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

    :ivar object status: overall status of the whole run of the unit, one of the CollectStatus or
        PostprocessStatus enum
    :ivar module runner: module of the collector or postprocessor
    :ivar str runner_type: string name of the runner type, either collector or postprocessor
    :ivar int stat_code: sub status returned by the unit, 0 if nothing happened
    :ivar str phase: name of the last executed phase (before, collect/postprocess, after)
    :ivar Exception exception: exception (if it was raised) during the run otherwise None
    :ivar str message: string message describing the result of run
    :ivar dict kwargs: kwargs of the process (should include "profile")
    """

    ok_statuses: dict[str, CollectStatus | PostprocessStatus] = {
        "collector": CollectStatus.OK,
        "postprocessor": PostprocessStatus.OK,
    }
    error_statues: dict[str, CollectStatus | PostprocessStatus] = {
        "collector": CollectStatus.ERROR,
        "postprocessor": PostprocessStatus.ERROR,
    }

    def __init__(self, runner: types.ModuleType, runner_type: str, kwargs: Any) -> None:
        """
        :param module runner: module of the runner
        :param str runner_type: type of the runner (either 'collector' or 'postprocessor'
        :param dict kwargs: initial keyword arguments
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

        :param int stat_code: returned code of the run
        :param str message: additional message about the run process
        :param dict params: updated params
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

    :ivar str cmd: command to be executed (i.e. script, binary, etc.)
    :ivar str args: optional arguments of the command (such as -q, --pretty=no, etc.)
    :ivar str workload: optional workloads (or inputs) of the command (i.e. files, whatever)
    :ivar str original_workload: workload that was used as an origin (stated from the configration,
        note that this is to differentiate between actually generated workloads from generators and
        names of the generators.
    """

    def __init__(self, cmd: str, args: str = "", workload: str = "") -> None:
        """Initializes the executable

        :param str cmd: command to be executed
        :param str args: optional arguments of the command
        :param str workload: optional workloads of the command
        """
        self.cmd = cmd
        self.args = args
        self.workload = workload
        self.origin_workload = workload

    def __str__(self) -> str:
        """Returns nonescaped, nonlexed string representation of the executable

        :return: string representation of executable
        """
        executable = self.cmd
        executable += " " + self.args if self.args else ""
        executable += " " + self.workload if self.workload else ""
        return executable

    def to_escaped_string(self) -> str:
        """Returns escaped string representation of executable

        :return: escaped string representation of executable
        """
        executable = shlex.quote(self.cmd)
        executable += " " + self.args if self.args else ""
        executable += " " + self.workload if self.workload else ""
        return executable


class Unit:
    """Specification of the unit that is part of run process

    :ivar str name: name of the unit
    :ivar dict params: parameters for the unit
    """

    def __init__(self, name: str, params: dict[str, Any]) -> None:
        """Constructs the unit, with name being sanitized

        :param str name: name of the unit
        :param dict params: parameters for the unit
        """
        self.name = Unit.sanitize_unit_name(name)
        self.params = params

    @classmethod
    def desanitize_unit_name(cls, unit_name: str) -> str:
        """Replace the underscors in the unit name so it is CLI compatible.

        In Click 7.0 all subcommands have automatically replaced underscores (_) with dashes (-).
        We have to sanitize/desanitize the unit name through the Perun.

        :param str unit_name: name of the unit that is desanitized
        :return:
        """
        return unit_name.replace("_", "-")

    @classmethod
    def sanitize_unit_name(cls, unit_name: str) -> str:
        """Sanitizes module name so it is usable and uniform in the perun.

        As of Click 7.0 in all subcommands underscores (_) are automatically replaced by dashes (-).
        While this is surely nice feature, Perun works with the Python function names that actually
        DO have underscores. So we basically support both formats, and in CLI we use only -, but use
        this fecking function to make sure the CLI names are replaced back to underscores. Rant
        over.

        :param str unit_name: module name that we are sanitizing
        :return: sanitized module name usable inside the Perun (with underscores instead of dashes)
        """
        return unit_name.replace("-", "_")


class DegradationInfo:
    """The returned results for performance check methods

    :ivar PerformanceChange result: result of the performance change, either can be optimization,
        degradation, no change, or certain type of unknown
    :ivar str type: string representing the type of the degradation, e.g. "order" degradation
    :ivar str location: location, where the degradation has happened
    :ivar str from_baseline: value or model representing the baseline, i.e. from which the new
        version was optimized or degraded
    :ivar str to_target: value or model representing the target, i.e. to which the new version was
        optimized or degraded
    :ivar str confidence_type: type of the confidence we have in the detected degradation, e.g. r^2
    :ivar float confidence_rate: value of the confidence we have in the detected degradation
    :ivar float rate_degradation_relative: relative rate of the degradation
    """

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

        :param PerformanceChange res: result of the performance change, either can be optimization,
            degradation, no change, or certain type of unknown
        :param str t: string representing the type of the degradation, e.g. "order" degradation
        :param str loc: location, where the degradation has happened
        :param str fb: value or model representing the baseline, i.e. from which the new version was
            optimized or degraded
        :param str tt: value or model representing the target, i.e. to which the new version was
            optimized or degraded
        :param float rd: quantified rate of the degradation, i.e. how much exactly it degrades
        :param str ct: type of the confidence we have in the detected degradation, e.g. r^2
        :param float cr: value of the confidence we have in the detected degradation
        :param float rdr: relative rate of the degradation (i.e. to the entire program run)
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


class Job:
    """Represents one profiling task in the Perun

    :ivar Unit collector: collection unit used to collect the SUP
    :ivar list postprocessors: list of postprocessing units applied after the collection
    :ivar Executable executable: System Under Profiling (SUP)
    """

    def __init__(self, collector: Unit, postprocessors: list[Unit], executable: Executable) -> None:
        """
        :param Unit collector: collection unit used to collect the SUP
        :param list postprocessors: list of postprocessing units applied after the collection
        :param Executable executable: System Under Profiling (SUP)
        """
        self.collector = collector
        self.postprocessors = postprocessors
        self.executable = executable

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
    """An ordered enumeration structure that ranks the elements so that they can be compared in
    regards of their order. Taken from:
        https://stackoverflow.com/questions/42369749/use-definition-order-of-enum-as-natural-order

    :ivar int order: the order of the new element
    """

    def __init__(self, *args: Any) -> None:
        """Create the new enumeration element and compute its order.

        :param args: additional element arguments
        """
        try:
            # attempt to initialize other parents in the hierarchy
            super().__init__(*args)
        except TypeError:
            # ignore -- there are no other parents
            pass
        ordered = len(self.__class__.__members__) + 1
        self.order = ordered

    def __ge__(self, other: object) -> bool:
        """Comparison operator >=.

        :param OrderedEnum other: the other enumeration element
        :return bool: the comparison result
        """
        if isinstance(other, self.__class__):
            return self.order >= other.order
        return NotImplemented

    def __gt__(self, other: object) -> bool:
        """Comparison operator >.

        :param OrderedEnum other: the other enumeration element
        :return bool: the comparison result
        """
        if isinstance(other, self.__class__):
            return self.order > other.order
        return NotImplemented

    def __le__(self, other: object) -> bool:
        """Comparison operator <=.

        :param OrderedEnum other: the other enumeration element
        :return bool: the comparison result
        """
        if isinstance(other, self.__class__):
            return self.order <= other.order
        return NotImplemented

    def __lt__(self, other: object) -> bool:
        """Comparison operator <.

        :param OrderedEnum other: the other enumeration element
        :return bool: the comparison result
        """
        if isinstance(other, self.__class__):
            return self.order < other.order
        return NotImplemented


class ProfileListConfig:
    """
    :ivar str colour: colour of the printed list
    :ivar str ending: ending for summary of the number of profiles
    :ivar int list_len: length of the profile list
    :ivar str id_char: character that represents either pending (p) or indexed (i) profiles
    :ivar int id_width: number of characters needed for the left column that counts the index of
        the profile in the list
    :ivar int header_width: overall width of the profile list
    """

    def __init__(self, list_type: str, short: bool, profile_list: list[Any]) -> None:
        """Initializes the configuration for the profile list.

        :param str list_type: type of the profile list (either untracked or untracked)
        :param bool short: true if the list should be short
        :param list profile_list: list of profiles
        """
        self.colour = "white" if list_type == "tracked" else "red"
        self.ending = ":\n\n" if not short else "\n"
        self.list_len = len(profile_list)
        self.id_char = "i" if list_type == "tracked" else "p"
        self.id_width = len(str(self.list_len))
        # The magic 3 corresponds to the fixed string @p or @i
        self.header_width = self.id_width + 3


@dataclass()
class MinorVersion:
    """Single MinorVersion (commit) from the Version Control System

    :ivar str data: date when the minor version was commited
    :ivar str author: author of the minor version
    :ivar str email: email of the author of the minor version
    :ivar str checksum: sha checksum of the minor version
    :ivar str desc: description of the changes commited in the minor version
    :ivar list parents: list of parents of the minor version (empty if root)
    """

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

    :ivar str name: name of the major version
    :ivar str head: sha checksum of the corresponding head minor version
    """

    name: str
    head: str


@dataclass()
class ModelRecord:
    """
    Helper class for holding the model parts

    :ivar str type: type of the model (i.e. its class)
    :ivar float r_square: R^2 value of the model
    :ivar float b0: constant coefficient of the model
    :ivar float b1: slope coefficient of the model
    :ivar float b2: quadratic coefficient of the model
    :ivar int x_start: start of the interval, where the model holds
    :ivar int x_end: end of the interval, where the model holds
    """

    type: str
    r_square: float
    b0: float | npt.NDArray[numpy.float64]
    b1: float
    b2: float
    x_start: float
    x_end: float

    def coeff_size(self) -> int:
        """Counts the number of coefficients in the model

        :return: lenght of the bins if the model is bin-like, else number of non-zero coefficients
        """
        return len(self.b0) if hasattr(self.b0, "__len__") else 1 + self.b1 != 0.0 + self.b2 != 0.0
