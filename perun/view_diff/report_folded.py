"""A comprehensive difference report of baseline-target external folded profiles.

The report calculates a number of difference metrics for both inclusive and exclusive resource
consumption:

    - proportional diff (prop_diff): reports the difference between the relative resource
      consumption proportionally to the total baseline and target consumption change. For example,
      if the baseline and target consumed 2M and 1M CPU cycles in total, respectively, and a
      function 'foo' consumed 100K cycles in both cases, the proportional difference is +5% as 'foo'
      now consumes 10% total resources up from 5%.
    - absolute diff (abs_diff): reports the difference of Target - Baseline resource consumption.
      For example, if the baseline and target consumed 2M and 1M CPU cycles in total, respectively,
      and a function 'foo' consumed 100K and 75K cycles in baseline, resp. target, the absolute
      difference is -25K.
    - relative diff (rel_diff): reports the difference of Target - Baseline resource consumption in
      relative terms. For example, if the baseline and target consumed 2M and 1M CPU cycles in
      total, respectively, and a function 'foo' consumed 100K and 80K cycles in baseline, resp.
      target, the relative difference is -25%.

"""

from __future__ import annotations

# Standard Imports
from collections import defaultdict
from collections.abc import Mapping, KeysView, Iterator, Sequence
import contextlib
import dataclasses
from datetime import datetime
import os
from pathlib import Path
import re
from subprocess import PIPE, TimeoutExpired
import tempfile
from types import TracebackType
from typing import (
    Any,
    Protocol,
    TextIO,
    Literal,
    Optional,
    ClassVar,
    TYPE_CHECKING,
    Type,
)

# Third-Party Imports
import polars as pl

# Perun Imports
import perun
from perun import profile  # TODO: restructure so that we do not fetch pandas, numpy, etc.
from perun.logic import config
from perun.profile import imports
from perun.templates import factory as templates
from perun.utils import log, streams
from perun.utils.common import common_kit, diff_kit, script_kit
from perun.utils.external import processes, commands
from perun.utils.structs import diff_structs
from perun.utils.structs.common_structs import WebColorPalette
from perun.view_diff import flamegraph, report_native

if TYPE_CHECKING:
    from subprocess import Popen

    # The tempfile.NamedTemporaryFile context manager does not have a public type hint.
    # Hence, we use the private tempfile object and alias it so that we avoid multiple warnings.
    TempTextIO = tempfile._TemporaryFileWrapper[str]


class PolarsAggregate(Protocol):
    """Polars aggregation callable type."""

    def __call__(self, *args: str) -> pl.Expr: ...


def func_to_polars_callable(agg_func: str) -> PolarsAggregate:
    """Maps aggregation function name to a polars callable.

    If the function name does not have a valid mapping, the median function is returned.

    :param agg_func: aggregation function name
    :return: a polars callable
    """
    try:
        return {
            "sum": pl.sum,
            "avg": pl.mean,
            "mean": pl.mean,
            "med": pl.median,
            "median": pl.median,
            "min": pl.min,
            "max": pl.max,
        }[agg_func]
    except KeyError:
        log.warn(
            f"Unsupported aggregation function '{agg_func}'. Using the default function 'median'."
        )
        return pl.median


class ParseParameters:
    """Profile parsing parameters.

    :ivar hide_generics: hide type generics in function names
    :ivar squash_recursion: squash recursive calls into a single function record
    :ivar squash_pattern: a regex pattern to filter functions to squash
    :ivar aggregation_func: the aggregation method for multiple baseline or target profiles
    """

    __slots__ = "hide_generics", "squash_recursion", "squash_pattern", "aggregation_func"

    def __init__(self, hide_generics: bool, squash: bool, squash_regex: str, **_: Any) -> None:
        """
        :param hide_generics: a flag indicating whether to hide type generics in function names
        :param squash: squash recursive calls into a single function record
        :param squash_regex: a regex pattern to filter functions to squash
        """
        self.hide_generics: bool = hide_generics
        self.squash_recursion: bool = squash
        self.squash_pattern: Optional[re.Pattern[str]] = None
        # Pre-compile non-default squash patterns. The default squash pattern matches everything
        # so there is no need to do regex matching at all.
        if squash and squash_regex != diff_structs.DEFAULT_SQUASH_RE:
            self.squash_pattern = re.compile(squash_regex)
        self.aggregation_func: PolarsAggregate = func_to_polars_callable(
            config.lookup_key_recursively(
                "profile.aggregation", default=diff_structs.DEFAULT_AGGREGATE_FUNC
            )
        )


class FilterParameters:
    """Performance data filtering parameters.

    Large profiles contain too much data to efficiently process and visualize. We thus allow the
    users to exclude data based on several thresholds and limits. The assumption is that if certain
    functions and traces take very little total resources (time, samples, etc.), then they are
    likely not the culprit of possible performance degradations.

    :ivar function_threshold: exclude functions that consumed less than the threshold ratio of the
          total resources in *both* baseline and target
    :ivar traces_threshold: exclude traces that consumed less than the threshold ratio of the
          total resources in *both* baseline and target
    :ivar max_function_traces: limit the number of most expensive traces stored per function
    :ivar top_diffs: limit the number of overall most expensive traces and function diffs
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
        :param function_threshold: the % threshold for function total resource consumption
        :param traces_threshold: the % threshold for trace resource consumption
        :param max_function_traces: the maximum number of most expensive traces to keep per function
        :param top_diffs: the number of overall most expensive traces and function diffs
        """
        # The thresholds are given as percentages, adjust to [0, 1] ratio.
        self.function_threshold: float = function_threshold * 0.01
        self.traces_threshold: float = traces_threshold * 0.01
        self.max_function_traces: int = max_function_traces
        self.top_diffs: int = top_diffs


class FunctionMaps:
    """A collection of mappings between function names and IDs created during parsing of profiles.

    The mappings are used to map function names to their IDs and back, which optimizes both memory
    and time of profile representation and manipulation.

    The maps may be reused when parsing multiple profiles (e.g., multiple baseline and target
    profiles), which leads to faster and easier matching when merging the profiles.

    :ivar func_id_map: a mapping of function name -> function ID
    :ivar func_id_reverse_map: a mapping of function ID -> function name; sorted by function ID
    :ivar squashed_id_map: a mapping of squashed function ID -> function ID; squashed functions
          refer to artificial function names representing merged recursive calls, e.g. 'func{x5}'
    """

    __slots__ = "func_id_map", "func_id_reverse_map", "squashed_id_map"

    def __init__(self) -> None:
        self.func_id_map: defaultdict[str, int] = defaultdict(lambda: len(self.func_id_map))
        self.func_id_reverse_map: dict[int, str] = {}
        self.squashed_id_map: dict[int, int] = {}

    def finalize(self) -> None:
        """Construct the reverse map.

        The reverse map is sorted in ascending order according to the function IDs, i.e., the keys.

        The finalization should be done after all profiles are parsed.
        """
        # The func_id_map is sorted by values, i.e., the function IDs (see the defaultdict factory
        # lambda). Hence, the reverse map will be sorted as well as long as it is constructed by
        # iterating over the func_id_map.
        self.func_id_reverse_map = {f_id: f_name for f_name, f_id in self.func_id_map.items()}


class ProfileFeatures:
    """A collection of profile features.

    The features are computed before any filtering of performance data takes place.

    :ivar total_resources: the total number of consumed resources
    :ivar max_trace_len: the longest seen trace
    :ivar measured_traces_count: the number of unique traces that have been measured; this does not
          include traces that have no measured resource consumption, e.g., sub-traces of recorded
          traces
    :ivar measured_functions_count: the number of unique functions that have been measured in any
          calling context; this does not include functions that have no measured resource
          consumption, e.g., functions seen in traces but with no measured consumption
    :ivar seen_traces_count: the number of all traces seen in a profile, including those that have
          no recorded exclusive resource consumption
    :ivar seen_functions_count: the number of all functions seen in a profile, including those that
          have no recorded exclusive resource consumption
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


@dataclasses.dataclass
class PolarsTraceProfile:
    """A Polars DataFrame representation of a single profile containing traces (e.g., perf folded).

    The profile DataFrame has the following columns: 'func', 'trace', 'inclusive', 'exclusive'
    where 'func' is the ID of the last function the trace, 'trace' is a semicolon-delimited string
    of function IDs representing the trace, and 'inclusive' and 'exclusive' store the resource
    consumption of the trace.

    For example, the profile DataFrame might look like this:

    ```
    shape: (369_033, 4)
    ┌──────┬─────────────────────────────────┬───────────┬───────────┐
    │ func ┆ trace                           ┆ inclusive ┆ exclusive │
    │ ---  ┆ ---                             ┆ ---       ┆ ---       │
    │ u32  ┆ str                             ┆ i64       ┆ i64       │
    ╞══════╪═════════════════════════════════╪═══════════╪═══════════╡
    │ 8    ┆ 0;3;2;4;5;6;7;8                 ┆ 657306    ┆ 657306    │
    │ 15   ┆ 0;9;2;4;5;6;10;11;12;13;14;15   ┆ 475601    ┆ 475601    │
    │ 27   ┆ 0;17;16;4;5;18;19;20;21;22;23;… ┆ 683530    ┆ 683530    │
    │ …    ┆ …                               ┆ …         ┆ …         │
    │ 6201 ┆ 6202;657;658;6186;6187;6200;62… ┆ 1360700   ┆ 1360700   │
    │ 453  ┆ 6202;657;658;6186;6187;6203;29… ┆ 78594     ┆ 78594     │
    │ 106  ┆ 6202;657;658;6186;6187;6203;29… ┆ 271800    ┆ 271800    │
    └──────┴─────────────────────────────────┴───────────┴───────────┘
    ```

    :ivar profile: a DataFrame representation of a trace profile
    :ivar features: a set of features describing and summarizing the profile
    :ivar maps: function maps created during the parsing of the profile
    """

    __slots__ = "profile", "features", "maps"

    profile: pl.DataFrame
    features: ProfileFeatures
    maps: FunctionMaps


@dataclasses.dataclass
class PolarsTraceProfilePair:
    """A Polars representation of a pair of baseline and target trace profiles.

    This representation should be preferred when working with a pair of profiles that are expected
    to be compared and analyzed, as it also stores sets of functions and traces that appear in both
    profiles. These sets take into account all functions and traces that appeared in both profiles,
    even if they have no measured exclusive resource consumption (and as such are omitted from the
    PolarsTraceProfile). Currently, only functions and traces that are exact match are considered
    to be common to both profiles.

    :ivar baseline: the baseline trace profile
    :ivar target: the target trace profile
    :ivar common_traces: a DataFrame containing only one column 'trace' with traces that appear in
          both profiles
    :ivar common_funcs: a DataFrame containing only one column 'func' with function IDs that appear
          in both profiles
    """

    __slots__ = "baseline", "target", "common_traces", "common_funcs"

    baseline: PolarsTraceProfile
    target: PolarsTraceProfile
    common_traces: pl.DataFrame
    common_funcs: pl.DataFrame


@dataclasses.dataclass
class PolarsMergedTraceProfiles:
    """A Polars representation of merged baseline-target trace and function profiles.

    This representation stores both per-trace and per-function profiles that contain merged rows
    for some baseline and target profiles.

    *Structure*: Both DataFrames contain the 'func', 'inclusive', 'exclusive', 'inclusive_target',
    'exclusive_target', 'prop_diff_incl', and 'prop_diff_excl' columns. The merged traces profile
    additionally contains the 'trace' column. See the module docstring for description of the
    difference metrics.

    The merged function profile contains aggregated resource consumption (aggregated separately for
    baseline and target profiles) across all traces associated with a function. Furthermore, it
    omits functions that have 0 exclusive cost and do not meet filtering thresholds
    (see FilterParameters).

    The merged trace profile omits all traces that belong to filtered functions, and all traces that
    have 0 exclusive cost and do not meet filtering thresholds (see FilterParameters).

    For example, the merged traces and merged function DataFrames might look like this:

    ```
    shape: (32_342, 8)
    ┌──────┬───────────┬───────────┬───┬──────────────────┬────────────────┬────────────────┐
    │ func ┆ trace     ┆ inclusive ┆ … ┆ exclusive_target ┆ prop_diff_incl ┆ prop_diff_excl │
    │ ---  ┆ ---       ┆ ---       ┆ … ┆ ---              ┆ ---            ┆ ---            │
    │ u32  ┆ str       ┆ i64       ┆ … ┆ i64              ┆ f32            ┆ f32            │
    ╞══════╪═══════════╪═══════════╪═══╪══════════════════╪════════════════╪════════════════╡
    │ 4    ┆ 971;4     ┆ 808775194 ┆ … ┆ 0                ┆ -0.010969      ┆ -0.000006      │
    │ 5    ┆ 971;4;5   ┆ 808331377 ┆ … ┆ 0                ┆ -0.010963      ┆ -0.000009      │
    │ 238  ┆ 971;4;5;… ┆ 246640065 ┆ … ┆ 0                ┆ -0.003345      ┆ -0.000063      │
    │ …    ┆ …         ┆ …         ┆ … ┆ …                ┆ …              ┆ …              │
    │ 135  ┆ 1554;155… ┆ 0         ┆ … ┆ 24230903         ┆ 0.001149       ┆ 0.001077       │
    │ 6235 ┆ 4;5;6235  ┆ 0         ┆ … ┆ 2683915          ┆ 0.014867       ┆ 0.000119       │
    │ 185  ┆ 3471;29…  ┆ 0         ┆ … ┆ 81537127         ┆ 0.003625       ┆ 0.003625       │
    └──────┴───────────┴───────────┴───┴──────────────────┴────────────────┴────────────────┘

    shape: (482, 7)
    ┌──────┬──────────────┬──────────────┬───┬──────────────────┬────────────────┬────────────────┐
    │ func ┆ inclusive    ┆ exclusive    ┆ … ┆ exclusive_target ┆ prop_diff_incl ┆ prop_diff_excl │
    │ ---  ┆ ---          ┆ ---          ┆ … ┆ ---              ┆ ---            ┆ ---            │
    │ u32  ┆ i64          ┆ i64          ┆ … ┆ i64              ┆ f32            ┆ f32            │
    ╞══════╪══════════════╪══════════════╪═══╪══════════════════╪════════════════╪════════════════╡
    │ 545  ┆ 905453006855 ┆ 203226689    ┆ … ┆ 162086637        ┆ 34.676102      ┆ 0.004449       │
    │ 1200 ┆ 4591717786   ┆ 486459792    ┆ … ┆ 243767256        ┆ 0.304794       ┆ 0.004239       │
    │ 3823 ┆ 108197824030 ┆ 104876145383 ┆ … ┆ 23210060569      ┆ -0.403142      ┆ -0.390618      │
    │ …    ┆ …            ┆ …            ┆ … ┆ …                ┆ …              ┆ …              │
    │ 1569 ┆ 49300568157  ┆ 208229571    ┆ … ┆ 54313042         ┆ -0.368518      ┆ -0.00041       │
    │ 6931 ┆ 0            ┆ 0            ┆ … ┆ 79892101         ┆ 0.184407       ┆ 0.003551       │
    │ 777  ┆ 25804957237  ┆ 12916984718  ┆ … ┆ 1312987872       ┆ -0.24692       ┆ -0.116819      │
    └──────┴──────────────┴──────────────┴───┴──────────────────┴────────────────┴────────────────┘
    ```

    Note that if a function or trace shows 0 resource consumption in target or baseline, it does not
    mean that such function or trace is baseline-only or target-only, respectively, since the
    baseline and target profiles have already omitted functions and traces that exist in the profile
    but have no exclusive resource consumption (see PolarsTraceProfile for more details). Use the
    'common_traces' and 'common_funcs' to determine whether a 0 resource consumption indicates
    baseline-only or target-only records.

    :ivar traces: a merged trace profile
    :ivar funcs: a merged per-function profile
    """

    __slots__ = "traces", "funcs"

    traces: pl.DataFrame
    funcs: pl.DataFrame


@dataclasses.dataclass
class PolarsTabularTraceProfiles:
    """A Polars representation of baseline-target trace and function tabular profiles.

    The tabular trace and function profiles are similar to the merged profiles but contain fewer
    records, additional difference metrics, and are sorted such that they can be easily iterated in
    a lockstep to generate tabular records for diff reports.

    *Structure*: Both DataFrames contain the 'func', 'inclusive', 'exclusive', 'inclusive_target',
    'exclusive_target', 'prop_diff_incl', 'prop_diff_excl', 'abs_diff_incl', 'abs_diff_excl',
    'rel_diff_incl', and 'rel_diff_excl' columns. The traces profile additionally contains the
    'trace' column. See the module docstring for description of the difference metrics.

    *Filtered*: The trace profile will have only up to top 'max_traces_per_func' traces per each
    function w.r.t. the 'prop_diff_incl' metric.

    *Sorted*: Both profiles are sorted by the function IDs in the ascending order. Additionally,
    the trace profile also contains traces within each function sorted w.r.t. the 'prop_diff_incl'
    metric in the descending order.

    For example, the tabular traces and function DataFrames might look like this:

    ```
    shape: (3_447, 12)
    ┌──────┬─────────────┬───────────────┬───┬───────────────┬───────────────┬───────────────┐
    │ func ┆ trace       ┆ inclusive     ┆ … ┆ abs_diff_excl ┆ rel_diff_incl ┆ rel_diff_excl │
    │ ---  ┆ ---         ┆ ---           ┆   ┆ ---           ┆ ---           ┆ ---           │
    │ u32  ┆ str         ┆ i64           ┆   ┆ i64           ┆ f32           ┆ f32           │
    ╞══════╪═════════════╪═══════════════╪═══╪═══════════════╪═══════════════╪═══════════════╡
    │ 4    ┆ 1;268;4     ┆ 1246557813681 ┆ … ┆ -39682724     ┆ -1.382918     ┆ -68.930069    │
    │ 4    ┆ 1;124;4     ┆ 0             ┆ … ┆ 1900490       ┆ 100.0         ┆ 100.0         │
    │ 4    ┆ 1;1174;4    ┆ 0             ┆ … ┆ 260703        ┆ 100.0         ┆ 100.0         │
    │ …    ┆ …           ┆ …             ┆ … ┆ …             ┆ …             ┆ …             │
    │ 7483 ┆ 5284;5304;… ┆ 0             ┆ … ┆ 14016473      ┆ 100.0         ┆ 100.0         │
    │ 7483 ┆ 5284;5290;… ┆ 0             ┆ … ┆ 8070493       ┆ 100.0         ┆ 100.0         │
    │ 7483 ┆ 5284;5290;… ┆ 0             ┆ … ┆ 8065807       ┆ 100.0         ┆ 100.0         │
    └──────┴─────────────┴───────────────┴───┴───────────────┴───────────────┴───────────────┘

    shape: (482, 11)
    ┌──────┬───────────────┬───┬────────────────┬───────────────┬───────────────┬───────────────┐
    │ func ┆ inclusive     ┆ … ┆ abs_diff_incl  ┆ abs_diff_excl ┆ rel_diff_incl ┆ rel_diff_excl │
    │ ---  ┆ ---           ┆   ┆ ---            ┆ ---           ┆ ---           ┆ ---           │
    │ u32  ┆ i64           ┆   ┆ i64            ┆ i64           ┆ f32           ┆ f32           │
    ╞══════╪═══════════════╪═══╪════════════════╪═══════════════╪═══════════════╪═══════════════╡
    │ 4    ┆ 4238716948387 ┆ … ┆ -2653980496373 ┆ -52677630     ┆ -62.612827    ┆ -42.958553    │
    │ 5    ┆ 4247354710131 ┆ … ┆ -2658348948953 ┆ -97869614     ┆ -62.588345    ┆ -20.323265    │
    │ 11   ┆ 196590265531  ┆ … ┆ -196590265531  ┆ -1199560386   ┆ -100.0        ┆ -100.0        │
    │ …    ┆ …             ┆ … ┆ …              ┆ …             ┆ …             ┆ …             │
    │ 6941 ┆ 0             ┆ … ┆ 24743188735    ┆ 95707629      ┆ 100.0         ┆ 100.0         │
    │ 6942 ┆ 0             ┆ … ┆ 24044566859    ┆ 225687075     ┆ 100.0         ┆ 100.0         │
    │ 7483 ┆ 0             ┆ … ┆ 3459034839     ┆ 71846967      ┆ 100.0         ┆ 100.0         │
    └──────┴───────────────┴───┴────────────────┴───────────────┴───────────────┴───────────────┘
    ```

    Note that if a function or trace shows 0 resource consumption in target or baseline, it does not
    mean that such function or trace is baseline-only or target-only, respectively, since the
    baseline and target profiles have already omitted functions and traces that exist in the profile
    but have no exclusive resource consumption (see PolarsTraceProfile for more details). Use the
    'common_traces' and 'common_funcs' to determine whether a 0 resource consumption indicates
    baseline-only or target-only records.

    :ivar traces: a merged trace profile
    :ivar funcs: a merged per-function profile
    """

    __slots__ = "traces", "funcs"

    traces: pl.DataFrame
    funcs: pl.DataFrame


@dataclasses.dataclass
class KeyDiffs:
    """A collection of the most significant differences of a key within a partitioned profile.

    The class stores the top increases and decreases of a key (metric) for baseline-only,
    target-only, and common partitions of a merged profile.

    :ivar baseline_top_inc: the largest increases in baseline-only records
    :ivar baseline_top_dec: the largest decreases in baseline-only records
    :ivar target_top_inc: the largest increases in target-only records
    :ivar target_top_dec: the largest decreases in target-only records
    :ivar common_top_inc: the largest increases in common records
    :ivar common_top_dec: the largest decreases in common records
    """

    __slots__ = (
        "baseline_top_inc",
        "baseline_top_dec",
        "target_top_inc",
        "target_top_dec",
        "common_top_inc",
        "common_top_dec",
    )

    baseline_top_inc: pl.DataFrame
    baseline_top_dec: pl.DataFrame
    target_top_inc: pl.DataFrame
    target_top_dec: pl.DataFrame
    common_top_inc: pl.DataFrame
    common_top_dec: pl.DataFrame


class FlameGraphSettings:
    """A collection of flamegraph parameters and settings to be used when rendering flamegraphs.

    :ivar width: the width of the flamegraph image
    :ivar height: the height of each function frame in the flamegraph
    :ivar min_width: the minimum width of a function frame, either pixels or percentage of time
    :ivar maxtrace: the longest trace in the flamegraph, should account for the min_width filtering
    :ivar fonttype: the font type
    :ivar fontsize: the font size
    :ivar countname: the resource type used in the profile, e.g., samples or CPU cycles
    :ivar colors: the color palette to use for frames
    :ivar bgcolors: the image background color
    :ivar inverted: whether an icicle graph should be rendered instead
    :ivar rootnode: the root node name
    :ivar total: the total amount of consumed resources
    :ivar fg_script_path: the path to the flamegraph script
    :ivar difffolded_path: the path to the difffolded script
    :ivar parallelize: parallelize the creation of flamegraph grids
    """

    __slots__ = (
        "width",
        "height",
        "min_width",
        "maxtrace",
        "fonttype",
        "fontsize",
        "countname",
        "colors",
        "bgcolors",
        "inverted",
        "rootnode",
        "total",
        "fg_script_path",
        "difffolded_path",
        "parallelize",
    )

    # Default flamegraph parameters reconstructed from the flamegraph.pl script.
    DefaultImageWidth: ClassVar[int] = 1200
    DefaultFrameHeight: ClassVar[int] = 16
    DefaultMinWidth: ClassVar[str] = "0.1"
    DefaultMaxTrace: ClassVar[int] = 0
    DefaultFontType: ClassVar[str] = "Verdana"
    DefaultFontSize: ClassVar[int] = 12
    DefaultCountName: ClassVar[str] = "samples"
    DefaultColors: ClassVar[str] = "hot"
    DefaultBgColors: ClassVar[str] = ""
    DefaultInverted: ClassVar[bool] = False
    DefaultRootNode: ClassVar[str] = "all"
    DefaultTotal: ClassVar[int] = 0

    # The map links the attribute names and their default values for easier iteration over the
    # keyword parameters. This map ignores the flags, e.g., 'inverted'.
    KwAttributeMap: ClassVar[dict[str, int | str]] = {
        "width": DefaultImageWidth,
        "height": DefaultFrameHeight,
        "min_width": DefaultMinWidth,
        "maxtrace": DefaultMaxTrace,
        "fonttype": DefaultFontType,
        "fontsize": DefaultFontSize,
        "countname": DefaultCountName,
        "colors": DefaultColors,
        "bgcolors": DefaultBgColors,
        "rootnode": DefaultRootNode,
        "total": DefaultTotal,
    }

    def __init__(
        self,
        width: int = DefaultImageWidth,
        height: int = DefaultFrameHeight,
        min_width: str = DefaultMinWidth,
        maxtrace: int = DefaultMaxTrace,
        fonttype: str = DefaultFontType,
        fontsize: int = DefaultFontSize,
        countname: str = DefaultCountName,
        colors: str = DefaultColors,
        bgcolors: str = DefaultBgColors,
        inverted: bool = DefaultInverted,
        rootnode: str = DefaultRootNode,
        total: int = DefaultTotal,
        parallelize: bool = True,
        **_: Any,
    ) -> None:
        """
        :param width: the width of the flamegraph image
        :param height: the height of each function frame in the flamegraph
        :param min_width: the minimum width of a function frame, either pixels or percentage of time
        :param maxtrace: the longest trace in the flamegraph after the min_width filtering
        :param fonttype: the font type
        :param fontsize: the font size
        :param countname: the resource type used in the profile, e.g., samples or CPU cycles
        :param colors: the color palette to use for frames
        :param bgcolors: the image background color
        :param inverted: whether an icicle graph should be rendered instead
        :param rootnode: the root node name
        :param total: the total amount of consumed resources
        :param parallelize: parallelize the creation of flamegraph grids
        """
        # We call the type conversion functions since the parameters may be supplied from CLI
        # where the types do not necessarily have to match.
        self.width: int = int(width)
        self.height: int = int(height)
        self.min_width: str = str(min_width)
        self.maxtrace: int = int(maxtrace)
        self.fonttype: str = str(fonttype)
        self.fontsize: int = int(fontsize)
        self.countname: str = str(countname)
        self.colors: str = str(colors)
        self.bgcolors: str = str(bgcolors)
        self.inverted: bool = bool(inverted)
        self.rootnode: str = str(rootnode)
        self.total: int = int(total)

        self.fg_script_path: Path = Path(script_kit.get_script("flamegraph.pl"))
        self.difffolded_path: Path = Path(script_kit.get_script("difffolded.pl"))
        self.parallelize: bool = parallelize

    @classmethod
    def from_cli(cls, **cli_kwargs: Any) -> FlameGraphSettings:
        """Initialize the flamegraph settings from CLI and init parameters.

        The parameters supplied through CLI will have a 'flamegraph_' prefix. Parameters supplied
        additionally by the caller (e.g., to overwrite certain CLI parameters) do not have to use
        the prefix. However, the order of specification matters: in order to overwrite CLI
        parameters, the additional parameters need to be specified after the CLI parameters.

        :param cli_kwargs: the CLI parameters
        :return: an initialized FlameGraphSettings instance
        """
        return cls(
            **{
                arg_name.replace("flamegraph_", ""): arg_value
                for arg_name, arg_value in cli_kwargs.items()
                if arg_value is not None
            }
        )

    def get_nondefault_kw_attributes(self) -> dict[str, str | int]:
        """Construct a collection of keyword attributes that have non-default values.

        :return: a dictionary of all keyword attributes with non-default values
        """
        params: dict[str, str | int] = {}
        for attr_name, attr_default_value in self.KwAttributeMap.items():
            if (value := getattr(self, attr_name)) != attr_default_value:
                params[attr_name] = value
        return params

    def compute_minwidth_threshold(self) -> float:
        """Compute the minimum width threshold for flamegraph blocks to be displayed.

        The threshold is needed to correctly compute the maxtrace value so that flamegraphs in
        a grid are correctly aligned and have the appropriate height.

        Reconstructed from the flamegraph.pl script.

        :return: the minimum width threshold
        """
        try:
            # The minimum width was provided as a percentage
            if self.min_width.endswith("%"):
                return self.total * float(self.min_width[:-1]) / 100
            # The minimum width is set in pixels
            x_padding: int = 10
            width_per_time: float = (self.width - 2 * x_padding) / self.total
            return float(self.min_width) / width_per_time
        except ZeroDivisionError:
            # No total provided, we set the threshold so that it does not filter anything.
            return 0.0


@dataclasses.dataclass
class FlameGraphGrid:
    """A collection of flamegraphs that form a 2x2 grid of baseline, target and their diffs.

    The stored flamegraphs are already properly escaped and as such may be directly embedded into
    an HTML report.

    :ivar baseline: the baseline flamegraph
    :ivar target: the target flamegraph
    :ivar baseline_target_diff: the baseline-target difference flamegraph
    :ivar target_baseline_diff: the target-baseline difference flamegraph
    """

    __slots__ = "baseline", "target", "baseline_target_diff", "target_baseline_diff"

    # The default flamegraph titles used when generating the flamegraphs.
    DefaultTitles: ClassVar[tuple[str, str, str, str]] = (
        "Baseline Flamegraph",
        "Target Flamegraph",
        "Baseline-Target Diff Flamegraph",
        "Target-Baseline Diff Flamegraph",
    )
    # The tags used for escaping flamegraphs in the grid.
    EscapeTags: ClassVar[tuple[str, str, str, str]] = ("lhs_0", "rhs_0", "lhs_diff_0", "rhs_diff_0")

    def __init__(
        self,
        baseline: str = "",
        target: str = "",
        baseline_target_diff: str = "",
        target_baseline_diff: str = "",
    ) -> None:
        """
        :param baseline: the baseline flamegraph
        :param target: the target flamegraph
        :param baseline_target_diff: the baseline-target difference flamegraph
        :param target_baseline_diff: the target-baseline difference flamegraph
        """
        self.baseline: str = baseline
        self.target: str = target
        self.baseline_target_diff: str = baseline_target_diff
        self.target_baseline_diff: str = target_baseline_diff

    def __setitem__(self, index: int, flame_graph: str) -> None:
        """Set a new flamegraph according to the index.

        A helper method for access to individual flamegraphs, e.g., in a loop. Supported indices
        are [0, 3] and correspond to the baseline, target, baseline_target_diff, and
        target_baseline_diff flamegraphs.

        :param index: the index of the flamegraph; must be within the [0, 3] range
        :param flame_graph: the new flamegraph
        """
        setattr(self, self.__slots__[index], flame_graph)

    def __getitem__(self, index: int) -> str:
        """Get the flamegraph currently stored at an index.

        A helper method for access to individual flamegraphs, e.g., in a loop. Supported indices
        are [0, 3] and correspond to the baseline, target, baseline_target_diff, and
        target_baseline_diff flamegraphs.

        :param index: the index of the flamegraph to retrieve; must be within the [0, 3] range

        :return: the flamegraph currently stored at the index
        """
        return getattr(self, self.__slots__[index])

    def copy_from(self, grid: FlameGraphGrid) -> None:
        """Copies flamegraphs from another grid into this grid.

        :param grid: the other grid to copy the flamegraphs from
        """
        self.baseline = grid.baseline
        self.target = grid.target
        self.baseline_target_diff = grid.baseline_target_diff
        self.target_baseline_diff = grid.target_baseline_diff


@dataclasses.dataclass
class FlameGraphGridCommands:
    """A collection of commands for generating a flamegraph grid.

    :ivar baseline: the command to generate the baseline flamegraph
    :ivar target: the command to generate the target flamegraph
    :ivar baseline_target_difffolded: the command to diff baseline and target folded profiles
    :ivar baseline_target_fg_diff: the command to generate baseline-target difference flamegraph
    :ivar target_baseline_difffolded: the command to diff target and baseline folded profiles
    :ivar target_baseline_fg_diff: the command to generate target-baseline difference flamegraph
    """

    __slots__ = (
        "baseline",
        "target",
        "baseline_target_difffolded",
        "baseline_target_fg_diff",
        "target_baseline_difffolded",
        "target_baseline_fg_diff",
    )

    baseline: str
    target: str
    baseline_target_difffolded: str
    baseline_target_fg_diff: str
    target_baseline_difffolded: str
    target_baseline_fg_diff: str


class FlameGraphGridBuilder(Protocol):
    """A context manager interface for flamegraph grid creation.

    This context manager interface serves as a wrapper to simplify and unify the code for both
    serial and parallel creation of flamegraph grids. Although a flamegraph grid can be built
    serially without the need for a context manager, building the grid in parallel background
    processes needs a context manager that properly terminates and cleans-up the processes and
    other resources when needed.
    """

    def __enter__(self): ...

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> Optional[bool]: ...


class FlameGraphGridSerialBuilder:
    """A context manager wrapper over serial flamegraph grid creation.

    The flamegraph grid creation begins when the class is instantiated. When the context manager
    is entered, the flamegraph grid is already available.

    See FlameGraphGridBuilder for more details.
    """

    def __init__(
        self,
        grid: FlameGraphGrid,
        grid_commands: FlameGraphGridCommands,
    ) -> None:
        """
        :param grid: [out] a reference to the grid object for the generated flamegraphs; context
               managers cannot explicitly return values, hence we use an output parameter
        :param grid_commands: the commands for generating a flamegraph grid
        """
        # We cannot simply assign the grids as it would not propagate outside the object.
        grid.copy_from(build_flamegraph_grid_serially(grid_commands))

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> Optional[bool]:
        return None


class FlameGraphGridParallelBuilder(contextlib.ExitStack):
    """A context manager for parallel background flamegraph grid creation.

    Each flamegraph in the grid is created using a separate process that runs in the background.
    The processes are spawned when the class is instantiated and terminated (waited for) when the
    context manager scope is about to be exited. Only the __exit__ method is blocking, meaning the
    code within the context manager scope is executed in parallel to the flamegraph processes
    running in the background.

    This class inherits from the ExitStack since it internally creates a lot of other context
    managers that must be properly managed and exited even if an error occurs.

    :ivar fg_handles: handles to temporary output files for the created flamegraphs; pipes have
          limited buffer sizes and we do not want to periodically scan for output or use blocking
          methods for reading the output
    :ivar diff_processes: handles of difffolded.pl processes that generate data for diff flamegraphs
    :ivar fg_processes: handles of flamegraph.pl processes
    :ivar grid: a reference to the grid object for the generated flamegraphs; context managers
          cannot explicitly return values, hence we use an output parameter
    """

    __slots__ = "fg_handles", "diff_processes", "fg_processes", "grid"

    def __init__(
        self,
        grid: FlameGraphGrid,
        grid_commands: FlameGraphGridCommands,
    ) -> None:
        """
        :param grid: [out] a grid object which will contain the generated flamegraphs
        :param grid_commands: the commands for generating a flamegraph grid
        """
        super().__init__()
        self.fg_handles: list[TempTextIO] = []
        self.diff_processes: list[Popen[bytes]] = []
        self.fg_processes: list[Popen[bytes]] = []
        self.grid: FlameGraphGrid = grid

        log.major_info("Creating Flame Graph Grid (In Parallel)")

        # Here we start populating the ExitStack with context managers.
        # Spawn 4 temporary files that will store the generated flamegraphs.
        self.fg_handles = [
            self.enter_context(tempfile.NamedTemporaryFile(mode="w+")) for _ in range(4)
        ]
        # Spawn two difffolded processes: one for each diff flamegraph.
        # Note: PyCharm incorrectly shows typing errors related to the context manager return types.
        #  However, everything is typed correctly according to mypy.
        self.diff_processes = [
            self.enter_context(
                processes.nonblocking_subprocess(
                    grid_commands.baseline_target_difffolded, {"stdout": PIPE}
                )
            ),
            self.enter_context(
                processes.nonblocking_subprocess(
                    grid_commands.target_baseline_difffolded, {"stdout": PIPE}
                )
            ),
        ]
        # Spawn four flamegraph.pl processes: one for each flamegraph in the grid.
        self.fg_processes = [
            self.enter_context(
                processes.nonblocking_subprocess(
                    grid_commands.baseline, {"stdout": self.fg_handles[0]}
                )
            ),
            self.enter_context(
                processes.nonblocking_subprocess(
                    grid_commands.target, {"stdout": self.fg_handles[1]}
                )
            ),
            self.enter_context(
                processes.nonblocking_subprocess(
                    grid_commands.baseline_target_fg_diff,
                    {"stdin": self.diff_processes[0].stdout, "stdout": self.fg_handles[2]},
                )
            ),
            self.enter_context(
                processes.nonblocking_subprocess(
                    grid_commands.target_baseline_fg_diff,
                    {"stdin": self.diff_processes[1].stdout, "stdout": self.fg_handles[3]},
                )
            ),
        ]
        log.minor_success("Spawning flamegraph background processes")

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> Optional[bool]:
        """Context manager exit method that gathers the flamegraphs unless an error occurred.

        If an error occurred either somewhere in the context manager scope or within this method,
        the ExitStack exits all stored context managers and the error is propagated outside.
        In such case, the flamegraph grid is not guaranteed to be fully created depending on where
        the error happened.

        If no error occurred, this method waits for all flamegraph processes to finish and populates
        the output grid object.

        Note that this is a blocking method.

        :param exc_type: the type of the exception that occurred, if any
        :param exc_val: the actual exception object, if any
        :param exc_tb: the traceback of the error, if any
        """
        try:
            # Only wait for and gather the flamegraphs if no error occurred yet.
            if exc_type is None:
                # We do not want to modify the list of handles directly. Instead, we keep a list of
                # handle indices corresponding to processes that have not finished yet.
                running_fg_processes: list[int] = list(range(len(self.fg_processes)))
                while running_fg_processes:
                    for list_idx, proc_idx in enumerate(running_fg_processes):
                        try:
                            self.fg_processes[proc_idx].wait(timeout=0.1)
                            # This process has finished, store the generated flamegraph in the grid.
                            self.fg_handles[proc_idx].seek(0)
                            self.grid[proc_idx] = self.fg_handles[proc_idx].read()
                            log.minor_success(FlameGraphGrid.DefaultTitles[proc_idx], "generated")
                            running_fg_processes.pop(list_idx)
                            break
                        except TimeoutExpired:
                            # This process is still running, check the next one.
                            pass
                # The flamegraphs stored in the grid are not escaped yet. The escaping is not
                # concurrency-safe, hence we must escape the flamegraphs only after all of them are
                # created.
                for idx, tag in enumerate(FlameGraphGrid.EscapeTags):
                    self.grid[idx] = flamegraph.escape_content(tag, self.grid[idx])

                # Cleanup the difffolded processes properly. If the diff flamegraph processes
                # finished correctly, the difffolded processes must have finished as well.
                for diff_process in self.diff_processes:
                    diff_process.wait()
                log.minor_success("Flamegraph grid", "completed")
        except:
            # We use the catch-all except clause deliberately, as the resources should be cleaned
            # no matter what errors happened.
            super().__exit__(exc_type, exc_val, exc_tb)
            raise
        # The flamegraph grid is complete, cleanup all the context managers and resources.
        return super().__exit__(exc_type, exc_val, exc_tb)


def generate_report_from_folded(
    baseline_profiles: str, target_profiles: str, **cli_kwargs: Any
) -> None:
    """Generate an interactive report from external folded profiles.

    :param baseline_profiles: the specification of baseline profiles from CLI; either a CSV file
           path, or a profile path with possibly an exit code and stat values
    :param target_profiles: the specification of target profiles from CLI; either a CSV file path,
           or a profile path with possibly an exit code and stat values
    :param cli_kwargs: additional parameters from the CLI
    """
    # Parse the profile specifications.
    base_dir = Path(cli_kwargs.get("baseline_dir", os.getcwd()))
    tar_dir = Path(cli_kwargs.get("target_dir", os.getcwd()))
    base_profiles, base_stats = imports.parse_perf_import_entries(
        [baseline_profiles], base_dir, cli_kwargs.get("baseline_stats_headers", None)
    )
    tar_profiles, tar_stats = imports.parse_perf_import_entries(
        [target_profiles], tar_dir, cli_kwargs.get("target_stats_headers", None)
    )
    if not base_profiles:
        log.error("No valid baseline profiles specified. Terminating.")
    elif not tar_profiles:
        log.error("No valid target profiles specified. Terminating.")

    # Transform some of the CLI kwargs into proper structures.
    # TODO: create another structure for profile specifications, e.g., headers, metadata, etc.
    parse_params: ParseParameters = ParseParameters(**cli_kwargs)
    filter_params: FilterParameters = FilterParameters(**cli_kwargs)
    fg_settings: FlameGraphSettings = FlameGraphSettings.from_cli(
        **cli_kwargs,
        countname=cli_kwargs["profiled_resource"],
        rootnode="Maximum (Baseline, Target)",
    )

    # Parse the input profiles and create their Polars representation.
    log.major_info("Parsing Input Folded Profiles")
    pair_profile: PolarsTraceProfilePair = folded_profiles_to_polars_pair_profile(
        [prof.path for prof in base_profiles], [prof.path for prof in tar_profiles], parse_params
    )
    log.minor_success("Parsing input folded profiles")

    fg_settings.total = max(
        pair_profile.baseline.features.total_resources, pair_profile.target.features.total_resources
    )
    minwidth_threshold = fg_settings.compute_minwidth_threshold()

    # Dump the parsed and post-processed profiles back into a folded format for flamegraph scripts.
    grid: FlameGraphGrid = FlameGraphGrid()
    log.minor_info("Saving post-processed profiles in temporary files.")
    with (
        tempfile.NamedTemporaryFile(mode="w") as baseline_folded,
        tempfile.NamedTemporaryFile(mode="w") as target_folded,
    ):
        base_maxtrace = polars_traces_to_folded_profile(
            pair_profile.baseline, baseline_folded, minwidth_threshold
        )
        tar_maxtrace = polars_traces_to_folded_profile(
            pair_profile.target, target_folded, minwidth_threshold
        )
        fg_settings.maxtrace = max(base_maxtrace, tar_maxtrace)
        log.minor_success("Saving post-processed profiles in temporary files")

        # Build the flamegraph grid. The grid may be built serially or in parallel background
        # processes.
        grid_commands = build_flamegraph_grid_commands(
            Path(baseline_folded.name), Path(target_folded.name), fg_settings
        )
        with build_flamegraph_grid(grid, grid_commands, fg_settings.parallelize):
            # If we build the flamegraphs in the background, we can analyze and further postprocess
            # the profiles in the meantime.
            log.minor_info("Analyzing and comparing profiles.")

            # Merge the baseline and target profiles and obtain the top differences in traces and
            # functions between the two profiles.
            merged = merge_and_filter_polars_profiles(
                pair_profile.baseline, pair_profile.target, filter_params
            )
            trace_top_diffs = compute_top_diffs(
                merged.traces.lazy(),
                pair_profile.common_traces.lazy(),
                "trace",
                "prop_diff_incl",
                "prop_diff_excl",
                filter_params.top_diffs,
            )
            func_top_diffs = compute_top_diffs(
                merged.funcs.lazy(),
                pair_profile.common_funcs.lazy(),
                "func",
                "prop_diff_incl",
                "prop_diff_excl",
                filter_params.top_diffs,
            )

            # Extend the profiles with new difference metrics and transform them such that they
            # are suitable for building the traces table.
            tabular_profile = polars_merged_to_tabular_profiles(
                merged, filter_params.max_function_traces
            )

            # Generate diffs of headers, stats, metadata, vulnerabilities, etc.
            base_metadata = imports.parse_metadata(
                cli_kwargs.get("baseline_metadata", tuple()), base_dir
            )
            tar_metadata = imports.parse_metadata(
                cli_kwargs.get("target_metadata", tuple()), tar_dir
            )
            base_machine_info = imports.get_machine_info(
                cli_kwargs.get("baseline_machine_info", ""), base_dir
            )
            tar_machine_info = imports.get_machine_info(
                cli_kwargs.get("target_machine_info", ""), tar_dir
            )

            lhs_header, rhs_header = diff_kit.generate_diff_of_headers(
                generate_specification(
                    base_machine_info,
                    [prof.exit_code for prof in base_profiles],
                    cli_kwargs["baseline_collector_cmd"],
                    cli_kwargs["baseline_cmd"],
                    cli_kwargs["baseline_label"],
                ),
                generate_specification(
                    tar_machine_info,
                    [prof.exit_code for prof in tar_profiles],
                    cli_kwargs["target_collector_cmd"],
                    cli_kwargs["target_cmd"],
                    cli_kwargs["target_label"],
                ),
            )
            lhs_vulnerabilities, rhs_vulnerabilities = diff_kit.generate_diff_of_headers(
                generate_vulnerabilities(base_machine_info.get("cpu_vulnerabilities", {})),
                generate_vulnerabilities(tar_machine_info.get("cpu_vulnerabilities", {})),
            )
            lhs_diff_stats, rhs_diff_stats = diff_kit.generate_diff_of_stats(base_stats, tar_stats)
            lhs_fg_diff_stats, rhs_fg_diff_stats = diff_kit.generate_diff_of_stats(
                features_to_stats(pair_profile.baseline.features, fg_settings.countname),
                features_to_stats(pair_profile.target.features, fg_settings.countname),
            )
            lhs_meta, rhs_meta = diff_kit.generate_diff_of_headers(base_metadata, tar_metadata)

            log.minor_success("Analyzing and comparing profiles")

            # Process user-defined chatbot prompt context, if provided.
            prompt_ctx = ""
            if cli_kwargs["chatbot_url"] is not None:
                prompt_ctx_sources: Optional[tuple[str, ...]] = cli_kwargs.get(
                    "chatbot_prompt_context", None
                )
                if prompt_ctx_sources is not None:
                    log.minor_info("Processing chatbot prompt context")
                    prompt_ctx = report_native.compose_chatbot_contexts(prompt_ctx_sources)

            template = templates.get_template("diff_views/report.html.jinja2")

            utc_time_now = datetime.utcnow()
            report_time = utc_time_now.strftime("%d %b %Y, %H:%M:%S") + " UTC"
            is_report_offline = config.lookup_key_recursively("showdiff.offline", False)
            report_links = list(cli_kwargs.get("link", []))
    # Transform the flamegraph grid into the format expected by the report template.
    flamegraphs = [
        (
            f"Inclusive {fg_settings.countname} [#]",
            grid.baseline,
            grid.target,
            grid.baseline_target_diff,
            grid.target_baseline_diff,
        )
    ]

    log.major_info("Rendering HTML Report")

    content = template.render(
        title="Perun Report - Profiles Comparison",
        perun_version=perun.__version__,
        timestamp=report_time,
        chatbot=cli_kwargs["chatbot_url"],
        chatbot_prompt_context=prompt_ctx,
        lhs_tag="Baseline",
        lhs_header=lhs_header,
        lhs_vulnerabilities=lhs_vulnerabilities,
        lhs_user_stats=lhs_diff_stats,
        lhs_fg_stats=lhs_fg_diff_stats,
        lhs_metadata=lhs_meta,
        rhs_tag="Target",
        rhs_header=rhs_header,
        rhs_vulnerabilities=rhs_vulnerabilities,
        rhs_user_stats=rhs_diff_stats,
        rhs_fg_stats=rhs_fg_diff_stats,
        rhs_metadata=rhs_meta,
        palette=WebColorPalette,
        stat_list=[flamegraphs[0][0]],
        units=[fg_settings.countname],
        nodes=iter(pair_profile.baseline.maps.func_id_reverse_map.values()),
        flamegraphs=flamegraphs,
        selection_table=iterate_polars_tabular(
            tabular_profile,
            pair_profile.common_funcs,
            pair_profile.baseline.maps.func_id_reverse_map,
            fg_settings.countname,
        ),
        offline=is_report_offline,
        notes_enabled=True,
        links=report_links,
        default_theme=cli_kwargs.get("default_theme", "light"),
        # FIXME: the top diffs will be used in the future.
        top_trace_diffs=trace_top_diffs,
        top_func_diffs=func_top_diffs,
    )
    log.minor_success("HTML report", "rendered")

    # FIXME: we do not have Perun profile objects that are necessary to automatically generate
    #  report names. Instead, we generate names with hopefully unique timestamps that should avoid
    #  overwriting other existing reports.
    output_filename: Optional[str] = cli_kwargs.get("output_path")
    if output_filename is None:
        # Get the report time with millisecond precision so that we do not risk overwriting reports.
        file_timestamp = utc_time_now.isoformat(sep="-", timespec="milliseconds").replace(":", "-")
        output_filename = f"report-folded_{file_timestamp}" + ".html"
    if not output_filename.endswith("html"):
        output_filename += ".html"

    with open(output_filename, "w", encoding="utf-8") as template_out:
        template_out.write(content)

    log.minor_status("Report saved", log.path_style(output_filename))


@contextlib.contextmanager
def open_folded_profile(filepath: Path) -> Iterator[TextIO]:
    """Open a (possibly gzipped) folded profile for reading.

     Regardless if the file is compressed or not, the file is opened in a text mode and can be read
     line by line in a streaming manner.

    :param filepath: a path to the folded profile
    :return: the file handle
    """
    open_func = (
        streams.safely_open_and_log_gz
        if filepath.suffix.lower() == ".gz"
        else streams.safely_open_and_log
    )

    # DO NOT simplify the mode to "r": the gzip library interprets "r" as a binary mode.
    with open_func(filepath, "rt", fatal_fail=True, encoding="utf-8") as folded_handle:
        yield folded_handle


def folded_profiles_to_polars_pair_profile(
    baseline_folded_profiles: Sequence[Path],
    target_folded_profiles: Sequence[Path],
    parse_params: ParseParameters,
) -> PolarsTraceProfilePair:
    """Parse baseline and target folded profiles into the polars pair profile.

    Prefer this function to constructing the pair profile directly: this function makes sure that
    all auxiliary data, e.g., profile features, function maps, or the common traces and functions,
    are computed correctly.

    :param baseline_folded_profiles: a collection of baseline profiles to aggregate into a single
           baseline trace profile
    :param target_folded_profiles: a collection of target profiles to aggregate into a single
           target trace profile
    :param parse_params: the parsing configuration and parameters

    :return: a polars trace profile pair
    """
    # Parse the folded profiles into aggregated baseline and target LazyFrames.
    func_maps = FunctionMaps()
    baseline_lf, baseline_features = _load_folded_profiles_to_polars_lf(
        baseline_folded_profiles, parse_params, func_maps
    )
    target_lf, target_features = _load_folded_profiles_to_polars_lf(
        target_folded_profiles, parse_params, func_maps
    )
    func_maps.finalize()
    # Note that only some of the baseline and target features are computed yet, as computing them
    # eagerly during the parsing is too expensive. Instead, we can compute them more efficiently
    # later on.

    # We need to reuse the parsed profiles in a lot of computations, hence we use the collect_all
    # to avoid repeated materialization of the same LazyFrames, and to optimize and parallelize the
    # computations as much as possible.
    baseline_df, target_df, common_traces, common_funcs, *features = pl.collect_all(
        [
            # Materialize the baseline trace profile.
            baseline_lf,
            # Materialize the target trace profile.
            target_lf,
            # Find traces that appear in both profiles; this includes traces with 0 exclusive costs.
            baseline_lf.select("trace").join(target_lf.select("trace"), on="trace", how="inner"),
            # Find functions that appear in both profiles; this includes functions with 0 exclusive
            # costs.
            baseline_lf.select("func")
            .unique()
            .join(target_lf.select("func").unique(), on="func", how="inner"),
            # Compute the number of unique traces seen in the baseline profile.
            baseline_lf.select("trace").count(),
            # Compute the number of unique functions seen in the baseline profile.
            baseline_lf.select("func").unique().count(),
            # Compute the number of unique baseline traces that have non-zero exclusive cost.
            baseline_lf.filter(pl.col("exclusive") != 0).select("trace").count(),
            # Compute the number of unique baseline functions that have non-zero exclusive cost.
            baseline_lf.filter(pl.col("exclusive") != 0).select("func").unique().count(),
            # Compute the number of unique traces seen in the target profile.
            target_lf.select("trace").count(),
            # Compute the number of unique functions seen in the target profile.
            target_lf.select("func").unique().count(),
            # Compute the number of unique target traces that have non-zero exclusive cost.
            target_lf.filter(pl.col("exclusive") != 0).select("trace").count(),
            # Compute the number of unique target functions that have non-zero exclusive cost.
            target_lf.filter(pl.col("exclusive") != 0).select("func").unique().count(),
        ]
    )
    if baseline_df.height == 0:
        log.error("Baseline profile is empty. Terminating.")
    elif target_df.height == 0:
        log.error("Target profile is empty. Terminating.")

    # Update the remaining profile features now that it is cheap.
    _update_profile_features(
        baseline_features,
        baseline_df,
        len(baseline_folded_profiles),
        parse_params.aggregation_func,
        *features[:4],
    )
    _update_profile_features(
        target_features,
        target_df,
        len(target_folded_profiles),
        parse_params.aggregation_func,
        *features[4:],
    )
    return PolarsTraceProfilePair(
        PolarsTraceProfile(baseline_df, baseline_features, func_maps),
        PolarsTraceProfile(target_df, target_features, func_maps),
        common_traces,
        common_funcs,
    )


def polars_traces_to_folded_profile(
    trace_profile: PolarsTraceProfile,
    folded_file: TextIO | TempTextIO,
    min_width_threshold: float = 0.0,
) -> int:
    """Store a Polars trace profile into a folded profile.

    As a by-product, we also compute the maximum length of traces that will be rendered in
    flamegraphs of this profile given the input width threshold.

    :param trace_profile: a Polars trace profile
    :param folded_file: a handle to the output file
    :param min_width_threshold: the rendering threshold for flamegraphs

    :return: the maximum trace length w.r.t. the filtering threshold
    """
    # Optimize dot operator access
    str_split = str.split
    str_join = str.join
    func_id_reverse_map = trace_profile.maps.func_id_reverse_map

    max_filtered_len: int = 0

    # Only keep the relevant columns
    for trace_str, exclusive, inclusive in trace_profile.profile.select(
        ["trace", "exclusive", "inclusive"]
    ).iter_rows():
        trace_parts = str_split(trace_str, ";")
        if exclusive:
            # Translate compact trace format to the verbose one, e.g., "1;2;10" -> "main;foo;bar"
            translated = str_join(
                ";", (func_id_reverse_map[int(func_id)] for func_id in trace_parts)
            )
            folded_file.write(f"{translated} {exclusive}\n")
        # Update the maximum trace length
        if inclusive >= min_width_threshold:
            max_filtered_len = max(max_filtered_len, len(trace_parts))
    return max_filtered_len


def merge_and_filter_polars_profiles(
    baseline: PolarsTraceProfile, target: PolarsTraceProfile, filter_params: FilterParameters
) -> PolarsMergedTraceProfiles:
    """Merge two Polars trace profiles into per-trace and per-function Polars merged profiles.

    During the merge process, we also filter out functions and traces that have 0 exclusive cost
    and do not meet thresholds for inclusive resource consumption specified in the filtering
    parameters.

    :param baseline: the baseline trace profile
    :param target: the target trace profile
    :param filter_params: filtering parameters

    :return: merged per-trace and per-function Polars profiles
    """
    baseline_total = baseline.features.total_resources
    target_total = target.features.total_resources
    # Compute the function and trace thresholds
    base_traces_threshold = filter_params.traces_threshold * baseline_total
    tar_traces_threshold = filter_params.traces_threshold * target_total
    base_func_threshold = filter_params.function_threshold * baseline_total
    tar_func_threshold = filter_params.function_threshold * target_total

    # Merge the baseline and target DataFrames such that each unique trace has exactly one row.
    merged_traces: pl.LazyFrame = (
        baseline.profile.lazy()
        .filter(pl.col("exclusive") != 0)
        .join(
            target.profile.lazy().filter(pl.col("exclusive") != 0),
            on=("func", "trace"),
            how="full",
            coalesce=True,
            suffix="_target",
        )
        # Traces that were measured only in baseline or target will have 0 exclusive and inclusive
        # resource consumption
        .fill_null(0)
    )

    # Polars expressions for computing the proportional inclusive and exclusive diffs.
    proportional_diff_expressions: tuple[pl.Expr, pl.Expr] = (
        ((pl.col("inclusive_target") / target_total - pl.col("inclusive") / baseline_total) * 100)
        .cast(pl.Float32)
        .alias("prop_diff_incl"),
        ((pl.col("exclusive_target") / target_total - pl.col("exclusive") / baseline_total) * 100)
        .cast(pl.Float32)
        .alias("prop_diff_excl"),
    )

    # Create the per-trace merged profile.
    filtered_merged_funcs: pl.LazyFrame = (
        merged_traces.select(pl.exclude("trace"))
        .group_by("func")
        .sum()
        # Remove functions that consume too few resources and are likely uninteresting.
        .filter(
            (pl.col("inclusive") >= base_func_threshold)
            | (pl.col("inclusive_target") >= tar_func_threshold)
        )
        # Compute the proportional diffs.
        .with_columns(*proportional_diff_expressions)
    )

    filtered_merged_traces: pl.LazyFrame = (
        # Keep only traces of functions that made it to the per-function merged profile after
        # filtering out the cheap functions.
        merged_traces.join(filtered_merged_funcs, on="func", how="semi")
        # Additionally remove traces that consume too few resources and are likely uninteresting.
        .filter(
            (pl.col("inclusive") >= base_traces_threshold)
            | (pl.col("inclusive_target") >= tar_traces_threshold)
        )
        # Compute the proportional diffs.
        .with_columns(*proportional_diff_expressions)
    )

    return PolarsMergedTraceProfiles(
        *pl.collect_all([filtered_merged_traces, filtered_merged_funcs])
    )


def compute_top_diffs(
    merged_profile: pl.LazyFrame,
    common_symbols: pl.LazyFrame,
    symbol_key: str,
    inclusive_diff_key: str,
    exclusive_diff_key: str,
    records_num: int,
) -> tuple[KeyDiffs, KeyDiffs]:
    """Compute the most significant inclusive and exclusive differences within a profile.

    The differences are computed for both inclusive and exclusive consumption metrics of a merged
    profile.

    For example, we might want to compute top 10 baseline-only, target-only, and common traces
    (or functions) that show the highest increase or decrease in the 'prop_diff_incl' and
    'prop_diff_excl' columns.

    :param merged_profile: a merged profile; it must contain the <symbol_key>,
           <inclusive_diff_key>, and <exclusive_diff_key> columns
    :param common_symbols: a column of symbols (e.g., functions or traces) that appear in both the
           baseline and target profiles
    :param symbol_key: the name of the column to use for partitioning the profile into
           baseline-only, target-only, and common parts
    :param inclusive_diff_key: the name of the column containing inclusive consumption metric
    :param exclusive_diff_key: the name of the column containing exclusive consumption metric
    :param records_num: the number of top difference records to compute

    :return: a pair of inclusive and exclusive top differences
    """
    # Partition the merged profile into baseline-only, target-only, and common parts based on
    # the symbol_key and the set of common symbols.
    common_lf = merged_profile.join(common_symbols, on=symbol_key, how="semi")
    baseline_only_lf = merged_profile.join(common_symbols, on=symbol_key, how="anti").filter(
        pl.col("inclusive_target") == 0
    )
    target_only_lf = merged_profile.join(common_symbols, on=symbol_key, how="anti").filter(
        pl.col("inclusive") == 0
    )
    # We use the collect_all method to optimize the computation: all top_k and bottom_k calls
    # share the same lazy frames and collect_all is able to optimize across all those computations.
    dfs = pl.collect_all(
        [
            baseline_only_lf.top_k(records_num, by=inclusive_diff_key),
            baseline_only_lf.bottom_k(records_num, by=inclusive_diff_key),
            target_only_lf.top_k(records_num, by=inclusive_diff_key),
            target_only_lf.bottom_k(records_num, by=inclusive_diff_key),
            common_lf.top_k(records_num, by=inclusive_diff_key),
            common_lf.bottom_k(records_num, by=inclusive_diff_key),
            baseline_only_lf.top_k(records_num, by=exclusive_diff_key),
            baseline_only_lf.bottom_k(records_num, by=exclusive_diff_key),
            target_only_lf.top_k(records_num, by=exclusive_diff_key),
            target_only_lf.bottom_k(records_num, by=exclusive_diff_key),
            common_lf.top_k(records_num, by=exclusive_diff_key),
            common_lf.bottom_k(records_num, by=exclusive_diff_key),
        ]
    )
    return KeyDiffs(*dfs[:6]), KeyDiffs(*dfs[6:])


def polars_merged_to_tabular_profiles(
    merged: PolarsMergedTraceProfiles, max_traces_per_func: int
) -> PolarsTabularTraceProfiles:
    """Transform Polars merged profiles to a format suitable for trace table.

    The trace table profile will have only up to top 'max_traces_per_func' traces per each function
    w.r.t. the inclusive proportional diff metric. Furthermore, both profiles will be sorted by the
    function IDs in the ascending order.

    Both DataFrames will contain the 'func', 'inclusive', 'exclusive', 'inclusive_target',
    'exclusive_target', 'prop_diff_incl', 'prop_diff_excl', 'abs_diff_incl', 'abs_diff_excl',
    'rel_diff_incl', and 'rel_diff_excl' columns. The traces profile will additionally contain the
    'trace' column. See the module docstring for description of the difference metrics.

    Both function and trace table profiles will have additional 'abs_diff_incl', 'abs_diff_excl',
    'rel_diff_incl', and 'rel_diff_excl' diff columns

    :param merged: the Polars merged profiles to transform
    :param max_traces_per_func: the maximum number of top traces to keep per function

    :return: a pair of trace and function table profiles
    """
    # Polars expressions for computing the absolute and relative diffs for both inclusive and
    # exclusive consumption.
    abs_rel_diff_expressions: tuple[pl.Expr, pl.Expr, pl.Expr, pl.Expr] = (
        # Absolute inclusive diff.
        (pl.col("inclusive_target") - pl.col("inclusive")).alias("abs_diff_incl").cast(pl.Int64),
        # Absolute exclusive diff.
        (pl.col("exclusive_target") - pl.col("exclusive")).alias("abs_diff_excl").cast(pl.Int64),
        # Relative inclusive diff.
        (
            (pl.col("inclusive_target") - pl.col("inclusive"))
            / pl.max_horizontal("inclusive", "inclusive_target")
            * 100
        )
        .cast(pl.Float32)
        .alias("rel_diff_incl"),
        # Relative inclusive diff.
        (
            (pl.col("exclusive_target") - pl.col("exclusive"))
            / pl.max_horizontal("exclusive", "exclusive_target")
            * 100
        )
        .cast(pl.Float32)
        .alias("rel_diff_excl"),
    )

    # Build merged func profile with additional absolute and relative diff metrics, and sort the
    # DataFrame rows from the lowest function IDs to the highest ones.
    table_funcs_lf = (
        merged.funcs.lazy().with_columns(*abs_rel_diff_expressions).sort("func", descending=False)
    )

    # Build merged trace profile with additional absolute and relative diff metrics, where each
    # function keeps only up to top 'max_traces_per_func' traces w.r.t. the inclusive proportional
    # diff metric.
    # TODO: Eventually, we will want to keep top 'max_traces_per_func' for more than one difference
    #  metric. However, we first need to update the report table such that it allows the user to
    #  switch between the per-metric sets of top traces.
    table_traces_lf = (
        merged.traces.lazy()
        # This sorts the DataFrame rows first by function IDs, and then the traces for each
        # individual function by the diff value in descending order.
        .sort(["func", "prop_diff_incl"], descending=[False, True])
        .group_by("func", maintain_order=True)
        # We keep only up to 'max_traces_per_func' top number of traces per each function.
        .head(max_traces_per_func)
        .with_columns(*abs_rel_diff_expressions)
    )

    return PolarsTabularTraceProfiles(*pl.collect_all([table_traces_lf, table_funcs_lf]))


def iterate_polars_tabular(
    tabular_profile: PolarsTabularTraceProfiles,
    common_functions: pl.DataFrame,
    func_id_reverse_map: Mapping[int, str],
    resource_type: str,
) -> Iterator[report_native.SelectionRow]:
    """Iterates over the tabular profiles and generates records for the report table.

    :param tabular_profile: the polars tabular profiles
    :param common_functions: the set of function IDs common to both baseline and target profiles
    :param func_id_reverse_map: a function ID -> function name mapping
    :param resource_type: the resource type of the profiles; this should contain both the resource
           name, e.g., 'CPU Cycles' and the unit, e.g., '[#]'

    :return: a generator of the report table records
    """
    # Optimize dot operator access where it matters
    str_split = str.split
    str_rsplit = str.rsplit
    str_count = str.count
    tabular_funcs = tabular_profile.funcs
    df_row = pl.DataFrame.row
    df_iter_rows = pl.DataFrame.iter_rows
    SelectRow = report_native.SelectionRow

    common_funcs: set[int] = set(common_functions["func"].to_list())

    # TODO: We want to support both inclusive and exclusive traces later on.
    inclusive_resource_type = f"Inclusive {resource_type}"
    # FIXME: Temporary hack so that we can use the SelectionRow class.
    report_native.Stats.SortedStats = [inclusive_resource_type]
    group_df: pl.DataFrame
    # Iterate over groups of traces belonging to individual functions from the lowest to the
    # highest function IDs.
    for idx, (_, group_df) in enumerate(
        tabular_profile.traces.group_by("func", maintain_order=True)
    ):
        # Obtain a row corresponding to the function from the function profile. We can access it
        # using an index thanks to the profile being sorted.
        row = df_row(tabular_funcs, idx)
        # Determine the state of the function. If it is not in the set of common functions, then we
        # look at the 'inclusive' and 'inclusive_target' values to determine wheter it is
        # a baseline-only or target-only function.
        state: Literal["not in baseline", "not in target", "in both"] = "in both"
        # row[0]: Function ID
        if row[0] not in common_funcs:
            # row[1]: inclusive
            if row[1] == 0:
                state = "not in baseline"
            # row[3]: inclusive_target
            elif row[3] == 0:
                state = "not in target"

        # Format the top traces according to the SelectionRow requirements.
        top_traces = [
            (
                # Short trace: 'firstID;lastID'
                f"{str_split(r[1], ';', maxsplit=1)[0]};{str_rsplit(r[1], ';', maxsplit=1)[-1]}",
                # Resource type
                inclusive_resource_type,
                # inclusive
                r[2],
                # inclusive_target
                r[4],
                # prop_diff_incl
                r[6],
                # abs_diff_incl
                r[8],
                # rel_diff_incl
                r[10],
                # Full trace: 'firstID;...;lastID#base1;...;baseN#target1;...;targetN'
                # FIXME: the part of the trace after the first '#' is not used, but the report
                #  still expects it. We will remove it later.
                f'{r[1]}#0{";0" * str_count(r[1], ";")}#0{";0" * str_count(r[1], ";")}',
            )
            for r in df_iter_rows(group_df)
        ]
        # Build the SelectionRow record.
        yield SelectRow(
            # Function name
            func_id_reverse_map[row[0]],
            # Function ID
            row[0],
            state,
            # Function stats: resource type index, inclusive, inclusive_target, prop_diff_incl,
            #  abs_diff_incl, rel_diff_incl
            [(0, row[1], row[3], row[5], row[7], row[9])],
            top_traces,
        )


def build_flamegraph_command(
    input_path: Optional[Path],
    settings: FlameGraphSettings,
    title: str,
    *new_flags: str,
    **override_kwargs: Any,
) -> str:
    """Create a flamegraph.pl command to generate a flame graph.

    :param input_path: a path to the file with folded flame graph data; may be omitted in which case
           the input data should be supplied to the flamegraph.pl process via stdin
    :param settings: flamegraph configuration parameters and flags
    :param title: the title of the flame graph
    :param new_flags: additional flags that should be passed to the flamegraph.pl script
    :param override_kwargs: additional parameters that should extend or override the parameter
           values stored in the settings object

    :return: the command for generating a flame graph
    """
    cmd = [
        str(settings.fg_script_path),
        str(input_path) if input_path is not None else "",
        "--title",
        f"'{title}'",
    ]
    # Extend the command with flags.
    flags: set[str] = set(new_flags)
    if settings.inverted and "inverted" not in new_flags:
        flags.add("inverted")
    cmd.extend(f"--{flag}" for flag in flags)

    # Extend the command with flamegraph parameters that have non-default values.
    # Although we could supply the parameters with default values as well, it would needlessly
    # clutter the resulting command.
    kw_params: dict[str, str | int] = settings.get_nondefault_kw_attributes()
    # The parameters may be overridden and extended by the caller.
    kw_params.update(override_kwargs)
    for key, val in kw_params.items():
        if val is not None:
            cmd.append(f"--{key}")
            cmd.append(f"'{val}'")
    return " ".join(cmd)


def build_differential_flamegraph_commands(
    baseline: Path,
    target: Path,
    settings: FlameGraphSettings,
    title: str,
    *new_flags: str,
    **override_kwargs: Any,
) -> tuple[str, str]:
    """Create difffolded.pl and flamegraph.pl commands to generate a differential flame graph.

    :param baseline: a path to the file with baseline folded flame graph data
    :param target: a path to the file with target folded flame graph data
    :param settings: flamegraph configuration parameters and flags
    :param title: the title of the flame graph
    :param new_flags: additional flags that should be passed to the flamegraph.pl script
    :param override_kwargs: additional parameters that should extend or override the parameter
           values stored in the settings object

    :return: the difffolded.pl and flamegraph.pl commands for generating a differential flame graph
    """
    diff_cmd = f"{settings.difffolded_path} -n {baseline} {target}"
    fg_cmd = build_flamegraph_command(None, settings, title, *new_flags, **override_kwargs)
    return diff_cmd, fg_cmd


def build_flamegraph_grid_commands(
    baseline: Path,
    target: Path,
    settings: FlameGraphSettings,
    *new_flags: str,
    titles: tuple[str, str, str, str] = FlameGraphGrid.DefaultTitles,
    **override_kwargs: Any,
) -> FlameGraphGridCommands:
    """Create a collection of commands for generating a flamegraph grid.

    :param baseline: a path to the file with baseline folded flame graph data
    :param target: a path to the file with target folded flame graph data
    :param settings: flamegraph configuration parameters and flags
    :param new_flags: additional flags that should be passed to the flamegraph.pl script
    :param titles: the titles of the respective flamegraphs
    :param override_kwargs: additional parameters that should extend or override the parameter
           values stored in the settings object

    :return: the flamegraph commands for generating a flamegraph grid
    """
    return FlameGraphGridCommands(
        build_flamegraph_command(baseline, settings, titles[0], *new_flags, **override_kwargs),
        build_flamegraph_command(target, settings, titles[1], *new_flags, **override_kwargs),
        *build_differential_flamegraph_commands(
            baseline, target, settings, titles[2], *new_flags, **override_kwargs
        ),
        *build_differential_flamegraph_commands(
            target, baseline, settings, titles[3], "negate", *new_flags, **override_kwargs
        ),
    )


def build_flamegraph_grid_serially(grid_commands: FlameGraphGridCommands) -> FlameGraphGrid:
    """Create a flamegraph grid serially in this process.

    :param grid_commands: the commands for generating a flamegraph grid

    :return: the generated flamegraph grid
    """
    log.major_info("Creating Flame Graph Grid (Serially)")

    # Transform the commands into a tuple that we can index in a loop.
    cmds: tuple[str, str, str, str] = (
        grid_commands.baseline,
        grid_commands.target,
        f"{grid_commands.baseline_target_difffolded} | {grid_commands.baseline_target_fg_diff}",
        f"{grid_commands.target_baseline_difffolded} | {grid_commands.target_baseline_fg_diff}",
    )

    grid: FlameGraphGrid = FlameGraphGrid()
    for idx, (fg_cmd, tag) in enumerate(zip(cmds, FlameGraphGrid.EscapeTags)):
        # Execute the command and escape the resulting flamegraph.
        grid[idx] = flamegraph.escape_content(
            tag, commands.run_safely_external_command(fg_cmd)[0].decode("utf-8")
        )
        log.minor_success(FlameGraphGrid.DefaultTitles[idx], "generated")

    log.minor_success("Flamegraph grid", "completed")
    return grid


@contextlib.contextmanager
def build_flamegraph_grid(
    grid: FlameGraphGrid,
    grid_commands: FlameGraphGridCommands,
    parallelize: bool,
) -> Iterator[FlameGraphGridBuilder]:
    """Create a context manager for flamegraph grid serial or parallel builder.

    The context manager hides the specifics of building a flamegraph grid serially in a single
    process or in several parallel background processes.

    :param grid: [out] a reference to the grid object for the generated flamegraphs; context
               managers cannot explicitly return values, hence we use an output parameter
    :param grid_commands: the commands for generating a flamegraph grid
    :param parallelize: determines whether to build the grid serially or in parallel

    :return: the context manager wrapping the grid builder
    """
    creator = FlameGraphGridParallelBuilder if parallelize else FlameGraphGridSerialBuilder
    with creator(grid, grid_commands) as builder:
        yield builder


def generate_specification(
    machine_info: dict[str, Any],
    exitcodes: str | list[str] | list[int],
    collector_command: str,
    command: str,
    label: str,
) -> list[profile.ProfileHeaderEntry]:
    """Generate profile header specification.

    :param machine_info: the machine specification
    :param exitcodes: possibly a collection of exit codes of profiling processes for each input
           profile
    :param collector_command: the name of the profiler that collected the profiles
    :param command: the profiled command and its input parameters
    :param label: a user-defined profile label

    :return: a collection of profile header entries corresponding to the profile specification
    """
    return [
        profile.ProfileHeaderEntry(
            "profile label",
            label if label else "?",
            "A label associated with this profile, if any.",
        ),
        profile.ProfileHeaderEntry(
            "command",
            command if command else "?",
            "The profiled command and its input parameters.",
        ),
        profile.ProfileHeaderEntry(
            "exitcode",
            diff_kit.format_exit_codes(exitcodes),
            "The exit code(s) that were returned by the profiling processes of each input profile.",
        ),
        profile.ProfileHeaderEntry(
            "collector command",
            collector_command,
            "The collector / profiler, which collected the data.",
        ),
        profile.ProfileHeaderEntry(
            "kernel",
            machine_info.get("release", "?"),
            "The underlying kernel version, where the results were measured.",
        ),
        profile.ProfileHeaderEntry(
            "boot info",
            machine_info.get("boot_info", "?"),
            "The contents of `/proc/cmdline` containing boot information about kernel",
        ),
        profile.ProfileHeaderEntry(
            "host", machine_info["host"], "The hostname, where the results were measured."
        ),
        profile.ProfileHeaderEntry(
            "cpu (total)",
            machine_info.get("cpu", {"total": "?"}).get("total", "?"),
            "The total number (physical and virtual) of CPUs available on the host.",
        ),
        profile.ProfileHeaderEntry(
            "memory (total)",
            machine_info.get("memory", {"total_ram": "?"}).get("total_ram", "?"),
            "The total number of RAM available on the host.",
        ),
    ]


def generate_vulnerabilities(
    vulnerabilities: dict[str, str | float],
) -> list[profile.ProfileHeaderEntry]:
    """Generate vulnerabilities profile header from the machine info sub-dictionary.

    :param vulnerabilities: the machine info sub-dictionary containing CPU vulnerabilities
           specification

    :return: CPU vulnerabilities as a profile header entry
    """
    return [
        profile.ProfileHeaderEntry(
            "vulnerabilities",
            "?" if not vulnerabilities else "",
            "CPU vulnerabilities summary.",
            vulnerabilities,
        )
    ]


def features_to_stats(features: ProfileFeatures, resource_name: str) -> list[profile.ProfileStat]:
    """Transform profile features into profile stats.

    :param features: profile features
    :param resource_name: profile resource name

    :return: a collection of profile stats derived from the features
    """
    return [
        profile.ProfileStat(
            f"Total {resource_name}",
            profile.ProfileStatComparison.LOWER,
            "#",
            description=f"The total amount of {resource_name} accounted for in the profile.",
            value=[features.total_resources],
        ),
        profile.ProfileStat(
            "Unique Functions",
            profile.ProfileStatComparison.LOWER,
            "#",
            description="The number of unique function symbols seen in the profile. This includes "
            "functions that have no measured exclusive resource consumption but were "
            "seen in traces.",
            value=[features.seen_functions_count],
        ),
        profile.ProfileStat(
            "Unique Traces",
            profile.ProfileStatComparison.LOWER,
            "#",
            description="The number of unique traces seen in the profile. This includes traces "
            "that have no measured exclusive resource consumption but were seen in the "
            "profile.",
            value=[features.seen_traces_count],
        ),
        profile.ProfileStat(
            "Measured Functions",
            profile.ProfileStatComparison.LOWER,
            "#",
            description="The number of unique function symbols that have exclusive resource "
            "consumption recorded in the profile.",
            value=[features.measured_functions_count],
        ),
        profile.ProfileStat(
            "Measured Traces",
            profile.ProfileStatComparison.LOWER,
            "#",
            description="The number of unique traces that have exclusive resource consumption "
            "recorded in the profile.",
            value=[features.measured_traces_count],
        ),
        profile.ProfileStat(
            "Longest Profile Trace",
            profile.ProfileStatComparison.LOWER,
            "#",
            description="The longest trace recorded in the profile.",
            value=[features.max_trace_len],
        ),
    ]


def _load_folded_profiles_to_polars_lf(
    folded_profiles: Sequence[Path], parse_params: ParseParameters, maps: FunctionMaps
) -> tuple[pl.LazyFrame, ProfileFeatures]:
    """Load folded profile(s) into a Polars LazyFrame according to the parse parameters.

    If multiple folded profiles are given, we aggregate them into a single LazyFrame according to
    the aggregation function specified in the parse parameters.

    Note that the returned profile features contain only those features that can be computed
    cheaply during the parsing.

    :param folded_profiles: possibly a collection of folded profile paths
    :param parse_params: parsing parameters and configuration
    :param maps: function maps

    :return: a (possibly aggregated) LazyFrame and incomplete profile features
    """
    features: ProfileFeatures = ProfileFeatures()
    # Check whether we should squash recursion and select the parse function accordingly.
    parse_func = _parse_folded_squash if parse_params.squash_recursion else _parse_folded_no_squash
    parsed_traces: list[pl.LazyFrame] = [
        parse_func(profile_path, maps, parse_params, features) for profile_path in folded_profiles
    ]

    if len(parsed_traces) == 1:
        # No need to aggregate data for a single input profile.
        return parsed_traces[0], features
    # We have parsed multiple profiles. Hence, each trace might have more than 1 value that we
    # need to aggregate. We do that by concatenating the profiles, grouping the same traces and
    # then aggregating the values.
    return (
        pl.concat(parsed_traces)
        .group_by("func", "trace")
        .agg(
            [
                parse_params.aggregation_func("inclusive").cast(pl.Int64),
                parse_params.aggregation_func("exclusive").cast(pl.Int64),
            ]
        ),
        features,
    )


def _parse_folded_no_squash(
    filepath: Path, maps: FunctionMaps, params: ParseParameters, profile_features: ProfileFeatures
) -> pl.LazyFrame:
    """Parse a folded profile into a polars frame without squashing recursive calls.

    We implement two separate parsing functions for squash/no-squash variants. The no-squash
    variant is simpler, and we want to keep it as fast as possible.

    :param filepath: a path to the folded profile
    :param maps: function name and ID maps
    :param params: parsing parameters
    :param profile_features: profile features that describe the parsed profile

    :return: a parsed profile lazyframe with 'func', 'trace', 'inclusive', and 'exclusive' columns
    """
    # trace -> inclusive resource consumption.
    inclusive: defaultdict[str, int] = defaultdict(int)
    # trace -> exclusive resource consumption.
    exclusive: defaultdict[str, int] = defaultdict(int)
    max_trace_len = 0
    total = 0

    # Optimize dot operator access.
    str_split = str.split
    str_rsplit = str.rsplit
    hide_generics_func = common_kit.hide_generics
    func_id_map = maps.func_id_map
    hide_generics = params.hide_generics

    with open_folded_profile(filepath) as folded_handle:
        for record in folded_handle:
            # Parse the line, obtain the performance metric and the trace as individual frames.
            frames: list[str] = str_split(record, ";")
            frames[-1], data = str_rsplit(frames[-1], " ", maxsplit=1)
            max_trace_len = max(max_trace_len, len(frames))
            data_int = int(data)
            total += data_int

            # Process the first frame of the trace.
            trace = str(func_id_map[frames[0]])
            inclusive[trace] += data_int
            # Process the rest of the trace.
            for frame in frames[1:]:
                if hide_generics:
                    frame = hide_generics_func(frame)
                trace += f";{func_id_map[frame]}"
                inclusive[trace] += data_int
            exclusive[trace] += data_int
    log.minor_success(log.path_style(str(filepath)), "parsed")
    # Update the profile features.
    profile_features.total_resources += total
    profile_features.max_trace_len = max(max_trace_len, profile_features.max_trace_len)
    return _build_trace_profile(inclusive, exclusive, None)


def _parse_folded_squash(
    filepath: Path, maps: FunctionMaps, params: ParseParameters, profile_features: ProfileFeatures
) -> pl.LazyFrame:
    """Parse a folded profile into a polars frame while squashing recursive calls.

    We implement two separate parsing functions for squash/no-squash variants. The squash variant
    is more complicated and expensive, so we keep it separately to not slow down the no-squash
    implementation.

    :param filepath: a path to the folded profile
    :param maps: a collection of parsing maps
    :param params: parsing parameters
    :param profile_features: profile features that describe the parsed profile

    :return: a parsed profile lazyframe with 'func', 'trace', 'inclusive', and 'exclusive' columns
    """
    # trace -> inclusive resource consumption.
    inclusive: defaultdict[str, int] = defaultdict(int)
    # trace -> exclusive resource consumption.
    exclusive: defaultdict[str, int] = defaultdict(int)
    max_trace_len = 0
    total = 0

    # Optimize dot operator access.
    re_search = re.search
    str_split = str.split
    str_rsplit = str.rsplit
    hide_generics_func = common_kit.hide_generics
    func_id_map = maps.func_id_map
    squashed_id_map = maps.squashed_id_map
    squash_pattern = params.squash_pattern
    hide_generics = params.hide_generics

    with open_folded_profile(filepath) as folded_handle:
        for record in folded_handle:
            # Parse the line, obtain the performance metric and the trace as individual frames.
            frames: list[str] = str_split(record, ";")
            frames[-1], data = str_rsplit(frames[-1], " ", maxsplit=1)
            max_trace_len = max(max_trace_len, len(frames))
            data_int = int(data)
            total += data_int

            # The algorithm does not immediately write the processed frame into the compact trace
            # string. Instead, it remembers the last processed frame and either writes it in the
            # next step, or merges it with the successor if squash conditions are satisfied.
            last_frame = func_id_map[frames[0]]
            trace: str = ""
            recursive_count = 1
            for idx, frame in enumerate(frames[1:]):
                if hide_generics:
                    frame = hide_generics_func(frame)
                func_id = func_id_map[frame]

                # We want to merge the frames if they represent the same function, and they match
                # the squash pattern. Regex matching is done only once for each sequence of
                # identical frames, and only for non-default patterns (default pattern matches
                # everything).
                if func_id == last_frame and (
                    squash_pattern is None
                    or (recursive_count > 1 or re_search(squash_pattern, frame))
                ):
                    # This frame is part of a recursive call chain.
                    recursive_count += 1
                elif recursive_count == 1:
                    # The previous frame was not part of a recursive call chain; write it.
                    if trace:
                        trace += f";{last_frame}"
                    else:
                        trace = str(last_frame)
                    inclusive[trace] += data_int
                    last_frame = func_id
                else:
                    # A recursive call chain has ended. We create a new ID for the squashed
                    # function with the number of recursive calls.
                    squashed_id = func_id_map[f"{frames[idx]}{{x{recursive_count}}}"]
                    trace += f";{squashed_id}"
                    squashed_id_map[squashed_id] = last_frame
                    inclusive[trace] += data_int
                    last_frame = func_id
                    recursive_count = 1
            # We must still process the last frame.
            if recursive_count > 1:
                squashed_id = func_id_map[f"{frames[-1]}{{x{recursive_count}}}"]
                trace += f";{squashed_id}"
                squashed_id_map[squashed_id] = last_frame
            elif trace:
                trace += f";{last_frame}"
            else:
                trace = str(last_frame)
            inclusive[trace] += data_int
            exclusive[trace] += data_int
    log.minor_success(log.path_style(str(filepath)), "parsed")
    # Update the profile features.
    profile_features.total_resources += total
    profile_features.max_trace_len = max(max_trace_len, profile_features.max_trace_len)
    return _build_trace_profile(inclusive, exclusive, squashed_id_map)


def _build_trace_profile(
    inclusive: defaultdict[str, int],
    exclusive: defaultdict[str, int],
    squashed_id_map: Optional[Mapping[int, int]],
) -> pl.LazyFrame:
    """Build a per-trace profile from inclusive and exclusive resource consumption records.

    No filtering takes place at this point; although we could, e.g., filter records with no
    exclusive consumption, we would not be able to correctly compute some profile features or lose
    some precision when detecting common functions to baseline and target profiles.

    Both the <inclusive> and <exclusive> maps should have keys in the form of 'id1;id2;id3;...'
    which represent traces in a compact format where id1, id2, and id3 correspond to function IDs.

    If recursion squashing took place, a <squashed_id_map> should be provided as well.

    :param inclusive: a mapping of trace -> inclusive resource consumption
    :param exclusive: a mapping of trace -> inclusive resource consumption
    :param squashed_id_map: a mapping of squashed function ID -> function ID; if not provided,
           we assume no squashing was done

    :return: a per-trace profile with 'func', 'trace', 'inclusive', and 'exclusive' columns
    """
    return pl.LazyFrame(
        {
            "func": _generate_func_ids(inclusive.keys(), squashed_id_map),
            "trace": inclusive.keys(),
            "inclusive": inclusive.values(),
            # The .get() method avoids needlessly growing the defaultdict.
            "exclusive": (exclusive.get(t, 0) for t in inclusive),
        },
        schema={
            "func": pl.UInt32,
            "trace": pl.String,
            "inclusive": pl.Int64,
            "exclusive": pl.Int64,
        },
    )


def _generate_func_ids(
    traces: KeysView[str], squashed_id_map: Optional[Mapping[int, int]]
) -> Iterator[int]:
    """A helper function that extracts the ID of the last function from a possibly squashed trace.

    For squashed traces, the function returns the ID of the non-squashed function symbol. For
    example, if the ID of last function in a trace corresponds to the 'foo{x8}' symbol, the
    function will return the ID of the original 'foo' symbol.

    :param traces: a set of traces to extract the function ID from
    :param squashed_id_map: a mapping of squashed function ID -> function ID; if not provided,
           we assume no squashing was done

    :return: a generator over the extracted function IDs
    """
    # Optimize dot operator access.
    str_rsplit = str.rsplit

    if squashed_id_map is None:
        # No squashing was done, simply extract and return the last ID in the trace.
        for trace in traces:
            yield int(str_rsplit(trace, ";", maxsplit=1)[-1])
    else:
        # Some of the traces may have been squashed.
        for trace in traces:
            last_func_id = int(str_rsplit(trace, ";", maxsplit=1)[-1])
            # Check if the last ID corresponds to a squashed function that needs to be translated.
            try:
                yield squashed_id_map[last_func_id]
            except KeyError:
                yield last_func_id


def _update_profile_features(
    features: ProfileFeatures,
    prof: pl.DataFrame,
    profiles_count: int,
    aggregation_func: PolarsAggregate,
    seen_traces: pl.DataFrame,
    seen_functions: pl.DataFrame,
    measured_traces: pl.DataFrame,
    measured_functions: pl.DataFrame,
) -> None:
    """Update the incomplete profile features with the missing features.

    The features object is initialized only partially during the parsing. The missing features
    should be supplied after they are computed more cheaply after postprocessing the profiles a bit.

    :param features: an incomplete profile features object
    :param prof: a profile DataFrame without traces with 0 exclusive cost
    :param profiles_count: the number of input profiles that were parsed to create the DataFrame
    :param aggregation_func: the aggregation function used to aggregate multiple profiles
    :param seen_traces: a 1x1 DataFrame containing the number of all the unique traces that
           appeared in the profile
    :param seen_functions: a 1x1 DataFrame containing the number of all the unique functions that
           appeared in the profile
    :param measured_traces: a 1x1 DataFrame containing the number of the unique traces that have
           non-zero exclusive cost
    :param measured_functions: a 1x1 DataFrame containing the number of the unique functions that
           have non-zero exclusive cost
    """
    # Obtain the single value in the DataFrames as a scalar integer.
    features.seen_traces_count = seen_traces.item()
    features.seen_functions_count = seen_functions.item()
    # The number of unique traces with non-zero exclusive cost is determined by the height of the
    # profile DataFrame.
    features.measured_traces_count = measured_traces.item()
    features.measured_functions_count = measured_functions.item()
    # If we aggregated multiple folded profiles into one, and the values were not simply summed,
    # we need to recompute the total number of consumed resources.
    if profiles_count > 1 and aggregation_func != pl.sum:
        features.total_resources = int(prof["exclusive"].sum())
