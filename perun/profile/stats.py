"""Profile Stats are additional metrics or statistics associated with a Profile.

Profile stats are identified by a name and include additional information about the metrics unit,
description and value(s). When the stat value is a collection, the values may be aggregated into
a single representative value and a collection of other descriptive values or statistics.

For example, if a stat contains a collection of float values, the aggregation creates a statistical
description of the values (i.e., min, max, mean, median, first and last decile, and first and third
quartile) and selects a representative value out of these using the aggregate-by key. A collection
of strings is aggregated into a histogram, where each value is a bin.

When comparing the representative value, the stat value comparison type defines the type of
comparison operator to use (e.g., lower than, higher than, equal, etc.) on the representative value.
Note that using equality for float values will not work properly. The AUTO comparison type
automatically selects a sane default comparison operator based on the aggregation type.
"""

from __future__ import annotations

# Standard Imports
from collections import Counter
import dataclasses
import enum
import math
import statistics
from typing import Any, Protocol, Iterable, ClassVar, Union, cast

# Third-Party Imports

# Perun Imports
from perun.utils import log as perun_log


class ProfileStatComparison(str, enum.Enum):
    """The profile stat comparison types.

    The auto comparison type selects a sane default comparison operator based on the aggregation
    type.

    Note: the enum derives from str so that ProfileStat serialization using asdict() works properly.
    """

    AUTO = "auto"
    HIGHER = "higher_is_better"
    LOWER = "lower_is_better"
    EQUALITY = "equality"

    @staticmethod
    def supported() -> set[str]:
        """Provides the set of supported comparison tupes.

        :return: The set of supported comparison types.
        """
        return {comparison.value for comparison in ProfileStatComparison}

    @staticmethod
    def default() -> ProfileStatComparison:
        """Provides the default comparison type.

        :return: The default comparison type.
        """
        return ProfileStatComparison.AUTO

    @classmethod
    def str_to_comparison(cls, comparison: str) -> ProfileStatComparison:
        """Convert a comparison type string into a ProfileStatComparison enum value.

        If an invalid comparison type is provided, the default type will be used.

        :param comparison: The comparison type as a string.

        :return: The comparison type as an enum value.
        """
        if not comparison:
            return cls.default()
        try:
            return cls(comparison.strip())
        except ValueError:
            # Invalid stat comparison, warn
            perun_log.warn(
                f"Unknown stat comparison: {comparison}. Using the default stat comparison value "
                f"instead. Please choose one of ({', '.join(cls.supported())})."
            )
            return cls.default()


class StatComparisonResult(enum.Enum):
    """The result of stat representative value comparison.

    Since the comparison is determined by the comparison operator and the type of the representative
    key, there is a number of valid comparison results that need to be represented.
    """

    EQUAL = 1
    UNEQUAL = 2
    BASELINE_BETTER = 3
    TARGET_BETTER = 4
    INVALID = 5


class StatComparableType(enum.Enum):
    """Specifies the type of the aggregated stats in terms of the stored values that are compared.

    When aggregated stats belong to the same comparable-type, it is possible to compare them
    despite them being different aggregation, e.g., SingleValue (with numeric value) and
    StatisticalSummary.
    """

    STRING = 1
    NUMERIC = 2


@dataclasses.dataclass
class ProfileStat:
    """An internal representation of a profile stat.

    :ivar name: The name of the stat.
    :ivar cmp: The comparison type of the stat values.
    :ivar unit: The unit of the stat value(s).
    :ivar aggregate_by: The aggregation (representative value) key.
    :ivar description: A detailed description of the stat.
    :ivar value: The value(s) of the stat.
    """

    name: str
    cmp: ProfileStatComparison = ProfileStatComparison.default()
    unit: str = "#"
    aggregate_by: str = ""
    description: str = ""
    value: list[str | float] = dataclasses.field(default_factory=list)

    @classmethod
    def from_string(
        cls,
        name: str = "",
        cmp: str = "",
        unit: str = "#",
        aggregate_by: str = "",
        description: str = "",
        *_: Any,
    ) -> ProfileStat:
        """Constructs a ProfileStat object from a string describing a stat header.

        The value of the stat is ignored when parsing from a string, as string representation is
        used solely for specifying the stat header.

        :param name: The name of the stat.
        :param cmp: The comparison type of the stat values.
        :param unit: The unit of the stat value(s).
        :param aggregate_by: The aggregation (representative value) key.
        :param description: A detailed description of the stat.

        :return: A constructed ProfileStat object.
        """
        if not name:
            # Invalid stat specification, warn
            perun_log.warn("Empty profile stat specification. Creating a dummy '[empty]' stat.")
            name = "[empty]"
        comparison_enum = ProfileStatComparison.str_to_comparison(cmp)
        return cls(name, comparison_enum, unit, aggregate_by, description)

    @classmethod
    def from_profile(cls, stat: dict[str, Any]) -> ProfileStat:
        """Constructs a ProfileStat object from a Perun profile.

        :param stat: The stat dictionary from a Perun profile.

        :return: A constructed ProfileStat object.
        """
        stat["cmp"] = ProfileStatComparison.str_to_comparison(stat.get("cmp", ""))
        return cls(**stat)

    def merge_with(self, other: ProfileStat) -> ProfileStat:
        """Merges value(s) from another ProfileStat object to this one.

        In case of mismatching headers, this ProfileStat header is used over the other one.

        :param other: The other ProfileStat object to merge with.

        :return: This ProfileStat object with merged values.
        """
        if self.get_header() != other.get_header():
            perun_log.warn(
                f"Merged ProfileStats '{self.name}' have mismatching headers, using the current "
                f"header {self.get_header()}"
            )
        self.value += other.value
        return self

    def get_header(self) -> tuple[str, str, str, str, str]:
        """Obtains the ProfileStat header, i.e., all attributes except the values.

        :return: the ProfileStat header.
        """
        return self.name, self.cmp, self.unit, self.aggregate_by, self.description


class ProfileStatAggregation(Protocol):
    """A protocol for profile stat aggregation objects.

    Since individual aggregation types may differ in a lot of ways (e.g., the supported
    representative/aggregation keys, table representation, auto comparison type, ...), we provide
    an abstract protocol for all aggregation objects.
    """

    _SUPPORTED_KEYS: ClassVar[set[str]] = set()
    _DEFAULT_KEY: ClassVar[str] = ""

    def normalize_aggregate_key(self, key: str = _DEFAULT_KEY) -> str:
        """Check and normalize the aggregation/representative key.

        If no key is provided, or the key is invalid or unsupported by the aggregation type, the
        default key is used instead.

        :param key: The key to check.

        :return: The checked (and possibly normalized) key.
        """
        if key not in self._SUPPORTED_KEYS:
            if key:
                # A key was provided, but it is an invalid one
                perun_log.warn(
                    f"{self.__class__.__name__}: Invalid aggregate key '{key}'. "
                    f"Using the default key '{self._DEFAULT_KEY}' instead."
                )
            key = self._DEFAULT_KEY
        return key

    def get_value(self, key: str = _DEFAULT_KEY) -> Any:
        """Obtain a value associated with the key from the aggregation / statistic description.

        If no key is provided, or the key is invalid, the value associated with the default key is
        returned.

        :param key: The key of the value to obtain.

        :return: The value associated with the key.
        """
        return getattr(self, self.normalize_aggregate_key(key))

    def infer_auto_comparison(self, comparison: ProfileStatComparison) -> ProfileStatComparison:
        """Selects the correct auto comparison type for the aggregation type.

        :param comparison: May be auto or any other valid comparison type. For the auto comparison
               type, another non-auto comparison type is returned. For the other comparison types,
               the method works as an identity function.

        :return: A non-auto comparison type.
        """

    def as_table(
        self, key: str = _DEFAULT_KEY
    ) -> tuple[str | float | tuple[str, int], dict[str, Any]]:
        """Transforms the aggregation object into the representative value and a table of the
        aggregation / statistic description values.

        :param key: The key of the aggregation / statistic description.

        :return: The representative value and a table representation of the aggregation.
        """

    def get_comparable_type(self) -> StatComparableType:
        """Provide the comparable-type of the aggregated stats.

        :return: The comparable-type of the aggregated stats object.
        """


@dataclasses.dataclass
class SingleValue(ProfileStatAggregation):
    """A single value "aggregation".

    Used for single value profile stats that need to adhere to the same interface as the "proper"
    aggregations.

    :ivar value: The value of the stat.
    """

    _SUPPORTED_KEYS: ClassVar[set[str]] = {"value"}
    _DEFAULT_KEY = "value"

    value: str | float = "[missing]"

    def infer_auto_comparison(self, comparison: ProfileStatComparison) -> ProfileStatComparison:
        if comparison != ProfileStatComparison.AUTO:
            return comparison
        if isinstance(self.value, str):
            return ProfileStatComparison.EQUALITY
        return ProfileStatComparison.HIGHER

    def as_table(self, _: str = "") -> tuple[str | float, dict[str, str | float]]:
        # There are no details of a single value to generate into a table
        return self.value, {}

    def get_comparable_type(self) -> StatComparableType:
        if isinstance(self.value, str):
            return StatComparableType.STRING
        return StatComparableType.NUMERIC


@dataclasses.dataclass
class StatisticalSummary(ProfileStatAggregation):
    """A statistical description / summary aggregation type.

    Used for collections of floats.

    :ivar min: The minimum value in the collection.
    :ivar p10: The first decile value.
    :ivar p25: The first quartile value.
    :ivar median: The median value of the entire collection.
    :ivar p75: The third quartile value.
    :ivar p90: The last decile value.
    :ivar max: The maximum value in the collection.
    :ivar mean: The mean value of the entire collection.
    """

    _SUPPORTED_KEYS: ClassVar[set[str]] = {
        "min",
        "p10",
        "p25",
        "median",
        "p75",
        "p90",
        "max",
        "mean",
    }
    _DEFAULT_KEY: ClassVar[str] = "median"

    min: float = 0.0
    p10: float = 0.0
    p25: float = 0.0
    median: float = 0.0
    p75: float = 0.0
    p90: float = 0.0
    max: float = 0.0
    mean: float = 0.0

    @classmethod
    def from_values(cls, values: Iterable[float]) -> StatisticalSummary:
        """Constructs a StatisticalSummary object from a collection of values.

        :param values: The collection of values to construct from.

        :return: The constructed StatisticalSummary object.
        """
        # We assume there aren't too many values so that multiple passes of the list don't matter
        # too much. If this becomes a bottleneck, we can use pandas describe() instead.
        values = list(val for val in values if not math.isnan(val))
        try:
            quantiles = statistics.quantiles(values, n=20, method="inclusive")
            return cls(
                float(min(values)),
                quantiles[2],  # p10
                quantiles[5],  # p25
                quantiles[10],  # p50
                quantiles[15],  # p75
                quantiles[18],  # p90
                float(max(values)),
                statistics.mean(values),
            )
        except statistics.StatisticsError:
            if values:
                # There is not enough points to generate the statistics, use the single value.
                value = values[0]
            else:
                # There are no valid data points, use nan.
                value = math.nan
            return cls(value, value, value, value, value, value, value, value)

    def infer_auto_comparison(self, comparison: ProfileStatComparison) -> ProfileStatComparison:
        if comparison != ProfileStatComparison.AUTO:
            return comparison
        return ProfileStatComparison.HIGHER

    def as_table(self, key: str = _DEFAULT_KEY) -> tuple[float, dict[str, float]]:
        return self.get_value(key), dataclasses.asdict(self)

    def get_comparable_type(self) -> StatComparableType:
        return StatComparableType.NUMERIC


@dataclasses.dataclass
class StringCollection(ProfileStatAggregation):
    """An aggregation type for a collection of strings.

    Supports numerous keys that attempt to aggregate and describe the string values. Also allows
    to compare the entire sequence of values for equality if needed.

    :ivar sequence: The sequence of strings.
    :ivar counts: A histogram where each string has a separate bin.
    """

    _SUPPORTED_KEYS: ClassVar[set[str]] = {
        "total",
        "unique",
        "min_count",
        "max_count",
        "counts",
        "sequence",
    }
    _DEFAULT_KEY: ClassVar[str] = "unique"

    sequence: list[str] = dataclasses.field(default_factory=list)
    counts: Counter[str] = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        """Computes the histogram from the sequence."""
        self.counts = Counter(self.sequence)

    @property
    def unique(self) -> int:
        """Get the number of unique strings in the collection.

        :return: The number of unique strings.
        """
        return len(self.counts)

    @property
    def total(self) -> int:
        """Get the total number of strings in the collection.

        :return: The total number of strings.
        """
        return len(self.sequence)

    @property
    def min_count(self) -> tuple[str, int]:
        """Get the string with the least number of occurrences in the collection.

        :return: The string with the least number of occurrences.
        """
        return self.counts.most_common()[-1]

    @property
    def max_count(self) -> tuple[str, int]:
        """Get the string with the most number of occurrences in the collection.

        :return: The string with the most number of occurrences.
        """
        return self.counts.most_common()[0]

    def infer_auto_comparison(self, comparison: ProfileStatComparison) -> ProfileStatComparison:
        if comparison != ProfileStatComparison.AUTO:
            return comparison
        return ProfileStatComparison.EQUALITY

    def as_table(
        self, key: str = _DEFAULT_KEY
    ) -> tuple[int | str | tuple[str, int], dict[str, int] | dict[str, str]]:
        representative_val: str | int | tuple[str, int]
        if key in ("counts", "sequence"):
            # The Counter and list objects are not suitable for direct printing in a table.
            representative_val = f"[{key}]"
        else:
            # A little type hinting help. The list and Counter types have already been covered.
            representative_val = cast(Union[str, int, tuple[str, int]], self.get_value(key))
        if key == "sequence":
            # The 'sequence' key table format is a bit different from the rest.
            return representative_val, {f"{idx}.": value for idx, value in enumerate(self.sequence)}
        return representative_val, self.counts

    def get_comparable_type(self) -> StatComparableType:
        return StatComparableType.STRING


def aggregate_stats(stat: ProfileStat) -> ProfileStatAggregation:
    """A factory that constructs the proper aggregation object based on the stat value(s) type.

    :param stat: The stat to create the aggregate object from.

    :return: The constructed aggregation object.
    """
    if len(stat.value) == 0:
        perun_log.warn(f"ProfileStat aggregation: Missing value of stat '{stat.name}'")
        return SingleValue()
    elif len(stat.value) == 1:
        return SingleValue(stat.value[0])
    elif all(isinstance(value, (int, float)) for value in stat.value):
        # All values are integers or floats
        return StatisticalSummary.from_values(map(float, stat.value))
    else:
        # Even heterogeneous lists will be aggregated as lists of strings
        return StringCollection(list(map(str, stat.value)))


def compare_stats(
    stat: ProfileStatAggregation,
    other_stat: ProfileStatAggregation,
    key: str,
    comparison: ProfileStatComparison,
) -> StatComparisonResult:
    """Compares two aggregated stats using the representative key and comparison type.

    :param stat: The first aggregate stat to compare.
    :param other_stat: The second aggregate stat to compare.
    :param key: The representative key from the aggregates to compare.
    :param comparison: The comparison type.

    :return: The comparison result.
    """
    value, other_value = stat.get_value(key), other_stat.get_value(key)
    # Handle auto comparison according to the aggregation type
    comparison = stat.infer_auto_comparison(comparison)
    if stat.get_comparable_type() != other_stat.get_comparable_type():
        # Invalid comparison attempt
        perun_log.warn(
            f"Invalid comparison of {stat.__class__.__name__} and {other_stat.__class__.__name__}."
        )
        return StatComparisonResult.INVALID
    if value == other_value:
        # The values are the same, the result is the same regardless of the comparison used
        return StatComparisonResult.EQUAL
    if comparison == ProfileStatComparison.EQUALITY:
        # The values are different and we compare for equality
        return StatComparisonResult.UNEQUAL
    elif value > other_value:
        return (
            StatComparisonResult.BASELINE_BETTER
            if comparison == ProfileStatComparison.HIGHER
            else StatComparisonResult.TARGET_BETTER
        )
    else:
        # value < other_value
        return (
            StatComparisonResult.BASELINE_BETTER
            if comparison == ProfileStatComparison.LOWER
            else StatComparisonResult.TARGET_BETTER
        )
