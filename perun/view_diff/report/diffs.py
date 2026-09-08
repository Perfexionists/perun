"""A module that computes top differences in baseline-target profiles."""

from __future__ import annotations

# Standard Imports
import dataclasses
from typing import Iterator

# Third-Party Imports
import polars as pl

# Perun Imports


@dataclasses.dataclass
class KeyDiffs:
    """A collection of the most significant differences of a key within a partitioned profile.

    The class stores the top increases and decreases of a key (metric) for baseline-only,
    target-only, and common partitions of a merged profile.

    The individual DataFrames contain only two columns: "symbol" and "diff".
     - "symbol" identifies either a trace or a function by their IDs, and
     - "diff" is the value of the diff metric.

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


def find_top_diffs(
    data_lf: pl.LazyFrame, count: int, symbol_key: str, diff_key: str, *, top: bool = True
) -> pl.LazyFrame:
    """Find and format the top or bottom diffs w.r.t. the diff_key metric.

    The resulting frame will contain up to <count> records maximal (resp. minimal) w.r.t. the
    <diff_key>. The schema of the resulting frame will have only two columns: "symbol" and "diff"
    corresponding to the <symbol_key> and <diff_key>.

    :param data_lf: the data where to search for the maximal/minimal records.
    :param count: the upper limit on the number of top records to search for.
    :param symbol_key: the name of the column with symbols (e.g., "trace")
    :param diff_key: the name of the column containing the diff metric
    :param top: specifies whether to search for the maximal or minimal records.

    :return: a lazy frame containing the maximal/minimal records.
    """
    search_func = pl.LazyFrame.top_k if top else pl.LazyFrame.bottom_k

    return (
        search_func(data_lf, count, by=diff_key)
        .select([symbol_key, diff_key])
        .rename({symbol_key: "symbol", diff_key: "diff"})
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
    base_only_lf = merged_profile.join(common_symbols, on=symbol_key, how="anti").filter(
        pl.col("inclusive_target") == 0
    )
    target_only_lf = merged_profile.join(common_symbols, on=symbol_key, how="anti").filter(
        pl.col("inclusive") == 0
    )
    # We use the collect_all method to optimize the computation: all top_k and bottom_k calls
    # share the same lazy frames and collect_all is able to optimize across all those computations.
    dfs = pl.collect_all(
        [
            # Inclusive diff metric.
            find_top_diffs(base_only_lf, records_num, symbol_key, inclusive_diff_key),
            find_top_diffs(base_only_lf, records_num, symbol_key, inclusive_diff_key, top=False),
            find_top_diffs(target_only_lf, records_num, symbol_key, inclusive_diff_key),
            find_top_diffs(target_only_lf, records_num, symbol_key, inclusive_diff_key, top=False),
            find_top_diffs(common_lf, records_num, symbol_key, inclusive_diff_key),
            find_top_diffs(common_lf, records_num, symbol_key, inclusive_diff_key, top=False),
            # Exclusive diff metric.
            find_top_diffs(base_only_lf, records_num, symbol_key, exclusive_diff_key),
            find_top_diffs(base_only_lf, records_num, symbol_key, exclusive_diff_key, top=False),
            find_top_diffs(target_only_lf, records_num, symbol_key, exclusive_diff_key),
            find_top_diffs(target_only_lf, records_num, symbol_key, exclusive_diff_key, top=False),
            find_top_diffs(common_lf, records_num, symbol_key, exclusive_diff_key),
            find_top_diffs(common_lf, records_num, symbol_key, exclusive_diff_key, top=False),
        ]
    )
    return KeyDiffs(*dfs[:6]), KeyDiffs(*dfs[6:])


def iterate_top_diffs(top_diff: KeyDiffs) -> list[Iterator[tuple[str, float]]]:
    """Iterates over the top difference data frames and generates records for the report overview.

    :param top_diff: the top difference data frames

    :return: a generator of the overview table records
    """
    diff_iterators: list[Iterator[tuple[str, float]]] = []
    for diff_data in [
        top_diff.baseline_top_dec,
        top_diff.target_top_inc,
        top_diff.common_top_inc,
        top_diff.common_top_dec,
    ]:
        diff_iterators.append(
            ((symbol, diff_metric) for symbol, diff_metric in diff_data.iter_rows())
        )
    return diff_iterators
