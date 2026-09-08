"""A collection of Polars profile representations and helper structures."""

from __future__ import annotations

# Standard Imports
from collections import defaultdict
import dataclasses

# Third-Party Imports
import polars as pl

# Perun Imports
from perun.profiles import structs


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
    features: structs.ProfileFeatures
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
    function w.r.t. the 'prop_diff_incl' and 'prop_diff_excl' metric. Note that the traces are
    deduplicated; for example, if `max_traces_per_func` = 10 and some function has a total of 15
    traces, but only 13 of them appear in both top selections, the resulting table will keep only
    the 13 traces instead of 20 (7 of which would be duplicated).

    *Sorted*: Both profiles are sorted by the function IDs in the ascending order.

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
