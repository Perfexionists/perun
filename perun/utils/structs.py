"""List of helper and globally used structures and named tuples"""

from enum import Enum

__author__ = 'Tomas Fiedor'

PerformanceChange = Enum(
    'PerformanceChange', 'Degradation MaybeDegradation ' +
                         'Unknown NoChange MaybeOptimization Optimization'
)


class DegradationInfo(object):
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

    def __init__(self, res, t, loc, fb, tt, ct="no", cr=0.0):
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
        :param str ct: type of the confidence we have in the detected degradation, e.g. r^2
        :param float cr: value of the confidence we have in the detected degradation
        """
        self.result = res
        self.type = t
        self.location = loc
        self.from_baseline = fb
        self.to_target = tt
        self.confidence_type = ct
        self.confidence_rate = cr

    def to_storage_record(self):
        """Transforms the degradation info to a storage_record

        :return: string representation of the degradation as a stored record in the file
        """
        return "{} {} {} {} {} {} {}".format(
            self.location,
            self.result,
            self.type,
            self.from_baseline,
            self.to_target,
            self.confidence_type,
            self.confidence_rate
        )
