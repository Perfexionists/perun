"""List of helper and globally used structures and named tuples"""

import collections
import shlex

from enum import Enum

__author__ = 'Tomas Fiedor'

GeneratorSpec = collections.namedtuple('GeneratorSpec', 'constructor params')

PerformanceChange = Enum(
    'PerformanceChange',
    'Degradation MaybeDegradation Unknown NoChange MaybeOptimization Optimization'
)


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
    ok_statuses = {
        'collector': CollectStatus.OK,
        'postprocessor': PostprocessStatus.OK
    }
    error_statues = {
        'collector': CollectStatus.ERROR,
        'postprocessor': PostprocessStatus.ERROR
    }
    def __init__(self, runner, runner_type, kwargs):
        """
        :param module runner: module of the runner
        :param str runner_type: type of the runner (either 'collector' or 'postprocessor'
        :param dict kwargs: initial keyword arguments
        """
        self.ok_status = RunnerReport.ok_statuses[runner_type]
        self.error_status = RunnerReport.error_statues[runner_type]

        self.runner = runner
        self.runner_type = runner_type
        self.status = self.ok_status
        self.stat_code = 0
        self.phase = "init"
        self.exception = None
        self.message = "OK"
        self.kwargs = kwargs

    def update_from(self, stat_code, message, params):
        """Updates the report according to the successful results of one of the phases

        :param int stat_code: returned code of the run
        :param str message: additional message about the run process
        :param dict params: updated params
        :return:
        """
        self.stat_code = stat_code
        self.message += message
        self.kwargs.update(params or {})

        is_enum = hasattr(self.stat_code, 'value')
        if not (self.stat_code == 0 or (is_enum and self.stat_code.value == 0)):
            self.status = self.error_status

    def is_ok(self):
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
    def __init__(self, cmd, args="", workload=""):
        """Initializes the executable

        :param str cmd: command to be executed
        :param str args: optional arguments of the command
        :param str workload: optional workloads of the command
        """
        self.cmd = str(cmd)
        self.args = str(args)
        self.workload = str(workload)
        self.origin_workload = str(workload)

    def __str__(self):
        """Returns nonescaped, nonlexed string representation of the executable

        :return: string representation of executable
        """
        executable = self.cmd
        executable += " " + self.args if self.args else ""
        executable += " " + self.workload if self.workload else ""
        return executable

    def to_escaped_string(self):
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
    def __init__(self, name, params):
        """Constructs the unit, with name being sanitized

        :param str name: name of the unit
        :param dict params: parameters for the unit
        """
        self.name = Unit.sanitize_unit_name(name)
        self.params = params


    @classmethod
    def desanitize_unit_name(cls, unit_name):
        """Replace the underscors in the unit name so it is CLI compatible.

        In Click 7.0 all subcommands have automatically replaced underscores (_) with dashes (-).
        We have to sanitize/desanitize the unit name through the Perun.

        :param str unit_name: name of the unit that is desanitized
        :return:
        """
        return unit_name.replace('_', '-')

    @classmethod
    def sanitize_unit_name(cls, unit_name):
        """Sanitizes module name so it is usable and uniform in the perun.

        As of Click 7.0 in all subcommands underscores (_) are automatically replaced by dashes (-).
        While this is surely nice feature, Perun works with the Python function names that actually
        DO have underscores. So we basically support both formats, and in CLI we use only -, but use
        this fecking function to make sure the CLI names are replaced back to underscores. Rant
        over.

        :param str unit_name: module name that we are sanitizing
        :return: sanitized module name usable inside the Perun (with underscores instead of dashes)
        """
        return unit_name.replace('-', '_')


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
    """

    def __init__(self, res, loc, fb, tt, t="-", rd=0, ct=0, cr=0, pi=None):
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
        """
        self.result = res
        self.type = t
        self.location = loc
        self.from_baseline = fb
        self.to_target = tt
        self.rate_degradation = float(rd)
        self.confidence_type = ct
        self.confidence_rate = float(cr)
        self.partial_intervals = pi

    def to_storage_record(self):
        """Transforms the degradation info to a storage_record

        :return: string representation of the degradation as a stored record in the file
        """
        return "{} {} {} {} {} {} {} {}".format(
            self.location,
            self.result,
            self.type,
            self.from_baseline,
            self.to_target,
            self.rate_degradation,
            self.confidence_type,
            self.confidence_rate
        )


class Job:
    """Represents one profiling task in the Perun

    :ivar Unit collector: collection unit used to collect the SUP
    :ivar list postprocessors: list of postprocessing units applied after the collection
    :ivar Executable executable: System Under Profiling (SUP)
    """
    def __init__(self, collector, postprocessors, executable):
        """
        :param Unit collector: collection unit used to collect the SUP
        :param list postprocessors: list of postprocessing units applied after the collection
        :param Executable executable: System Under Profiling (SUP)
        """
        self.collector = collector
        self.postprocessors = postprocessors
        self.executable = executable

    def _asdict(self):
        """
        :return: representation as dictionary
        """
        return {
            'collector': self.collector,
            'postprocessors': self.postprocessors,
            'executable': self.executable
        }