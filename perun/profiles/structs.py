"""Helper structures for parsing, postprocessing, or describing profiles."""

from __future__ import annotations

# Standard Imports
import dataclasses
import re
from typing import Any, Optional, Union

# Third-Party Imports

# Perun Imports
from perun.logic import config
from perun.utils.common import common_kit
from perun.utils.structs.view_structs import DEFAULT_SQUASH_RE


class PostprocessParameters:
    """Profile postprocessing parameters.

    :ivar hide_generics: hide type generics in function names.
    :ivar squash_recursion: squash recursive calls into a single function record.
    :ivar squash_pattern: a regex pattern to filter functions to squash.
    :ivar agg_func: the aggregation function.
    """

    __slots__ = (
        "hide_generics",
        "squash_recursion",
        "squash_pattern",
        "agg_func",
    )

    def __init__(
        self, hide_generics: bool, squash: bool, squash_regex: str = DEFAULT_SQUASH_RE, **_: Any
    ) -> None:
        """
        :param hide_generics: a flag indicating whether to hide type generics in function names.
        :param squash: squash recursive calls into a single function record.
        :param squash_regex: a regex pattern to filter functions to squash.
        """
        self.hide_generics: bool = hide_generics
        self.squash_recursion: bool = squash
        self.squash_pattern: Optional[re.Pattern[str]] = None
        # Pre-compile non-default squash patterns. The default squash pattern matches everything
        # so there is no need to do regex matching at all.
        if squash and squash_regex != DEFAULT_SQUASH_RE:
            self.squash_pattern = re.compile(squash_regex)
        self.agg_func: common_kit.Aggregations = common_kit.Aggregations.from_string(
            config.lookup_key_recursively(
                "profile.aggregation", default=common_kit.Aggregations.default_name()
            )
        )


class FilterParameters:
    """Performance data filtering parameters.

    Large profiles contain too much data to efficiently process and visualize. We thus allow the
    users to exclude data based on several thresholds and limits. The assumption is that if certain
    functions and traces take very little total resources (time, samples, etc.), then they are
    likely not the culprit of possible performance degradations.

    :ivar function_threshold: exclude functions that consumed less than the threshold ratio of the
          total resources in *both* baseline and target.
    :ivar traces_threshold: exclude traces that consumed less than the threshold ratio of the
          total resources in *both* baseline and target.
    :ivar max_function_traces: limit the number of most expensive traces stored per function.
    :ivar top_diffs: limit the number of overall most expensive traces and function diffs.
    """

    __slots__ = "function_threshold", "traces_threshold", "max_function_traces", "top_diffs"

    def __init__(
        self,
        function_threshold: float,
        traces_threshold: float,
        max_function_traces: int,
        top_diffs: int,
        **_: Any,
    ) -> None:
        """
        :param function_threshold: the % threshold for function total resource consumption.
        :param traces_threshold: the % threshold for trace resource consumption.
        :param max_function_traces: the maximum number of most expensive traces to keep per
               function.
        :param top_diffs: the number of overall most expensive traces and function diffs.
        """
        # The thresholds are given as percentages, adjust to [0, 1] ratio.
        self.function_threshold: float = function_threshold * 0.01
        self.traces_threshold: float = traces_threshold * 0.01
        self.max_function_traces: int = max_function_traces
        self.top_diffs: int = top_diffs


class ProfileFeatures:
    """A collection of profile features.

    :ivar total_resources: the total number of consumed resources.
    :ivar max_trace_len: the longest seen trace.
    :ivar measured_traces_count: the number of unique traces that have been measured; this does not
          include traces that have no measured resource consumption, e.g., sub-traces of recorded
          traces.
    :ivar measured_functions_count: the number of unique functions that have been measured in any
          calling context; this does not include functions that have no measured resource
          consumption, e.g., functions seen in traces but with no measured consumption.
    :ivar seen_traces_count: the number of all traces seen in a profile, including those that have
          no recorded exclusive resource consumption.
    :ivar seen_functions_count: the number of all functions seen in a profile, including those that
          have no recorded exclusive resource consumption.
    """

    __slots__ = (
        "total_resources",
        "max_trace_len",
        "measured_traces_count",
        "measured_functions_count",
        "seen_traces_count",
        "seen_functions_count",
    )

    def __init__(self) -> None:
        self.total_resources: int = 0
        self.max_trace_len: int = 0
        self.measured_traces_count: int = 0
        self.measured_functions_count: int = 0
        self.seen_traces_count: int = 0
        self.seen_functions_count: int = 0


# A tuple representation of the ProfileMetadataEntry object
ProfileHeaderTuple = tuple[str, Union[str, float], str, dict[str, Union[str, float]]]


@dataclasses.dataclass
class ProfileMetadataEntry:
    """A representation of a single profile header entry.

    :ivar name: the name (key) of the header entry.
    :ivar value: the value of the header entry.
    :ivar description: detailed description of the header entry.
    :ivar details: nested key: value data.
    """

    name: str
    value: str | float
    description: str = ""
    details: dict[str, str | float] = dataclasses.field(default_factory=dict)

    @classmethod
    def from_string(cls, header: str) -> ProfileMetadataEntry:
        """Constructs a `ProfileHeaderRecord` object from a string representation.

        :param header: the string representation of a header entry.

        :return: the constructed ProfileHeaderRecord object.
        """
        split = header.split("|")
        name = split[0]
        value = common_kit.try_convert(split[1] if len(split) > 1 else "[empty]", [float, str])
        desc = split[2] if len(split) > 2 else ProfileMetadataEntry.description
        details: dict[str, str | float] = {}
        for detail in split[4:]:
            detail_key, detail_value = detail.split(maxsplit=1)
            details[detail_key] = common_kit.try_convert(detail_value, [float, str])
        return cls(name, value, desc, details)

    @classmethod
    def from_profile(cls, header: dict[str, Any]) -> ProfileMetadataEntry:
        """Constructs a ProfileMetadataEntry object from native Profile header.

        :param header: the dictionary representation of a header entry.

        :return: the constructed ProfileMetadataEntry object.
        """
        return cls(**header)

    def as_tuple(self) -> ProfileHeaderTuple:
        """Converts the header object into a tuple.

        :return: the tuple representation of a header entry.
        """
        return self.name, self.value, self.description, self.details
