"""Conversion functions between various Polars representations."""

from __future__ import annotations

# Standard Imports

# Third-Party Imports
import polars as pl

# Perun Imports
from perun.profiles import structs
from perun.profiles.polars import structs as pl_structs
from perun.utils import log


def create_polars_pair_profile(
    baseline_profile: pl.LazyFrame,
    baseline_features: structs.ProfileFeatures,
    target_profile: pl.LazyFrame,
    target_features: structs.ProfileFeatures,
    function_maps: pl_structs.FunctionMaps,
) -> pl_structs.PolarsTraceProfilePair:
    """Transform simple baseline and target LazyFrame profiles into the polars pair profile.

    Prefer this function to constructing the pair profile directly: this function makes sure that
    all auxiliary data, e.g., profile features, function maps, or the common traces and functions,
    are computed correctly.

    :param baseline_profile: a collection of baseline profiles to aggregate into a single
           baseline trace profile.
    :param baseline_features: the incomplete baseline profile features object.
    :param target_profile: a collection of target profiles to aggregate into a single
           target trace profile.
    :param target_features: the incomplete target profile features object.
    :param function_maps: function name and ID maps.

    :return: a polars trace profile pair.
    """
    # We need to reuse the parsed profiles in a lot of computations, hence we use the collect_all
    # to avoid repeated materialization of the same LazyFrames, and to optimize and parallelize the
    # computations as much as possible.
    baseline_df, target_df, common_traces, common_funcs, *features = pl.collect_all(
        [
            # Materialize the baseline trace profile.
            baseline_profile,
            # Materialize the target trace profile.
            target_profile,
            # Find traces that appear in both profiles; this includes traces with 0 exclusive costs.
            baseline_profile.select("trace").join(
                target_profile.select("trace"), on="trace", how="inner"
            ),
            # Find functions that appear in both profiles; this includes functions with 0 exclusive
            # costs.
            baseline_profile.select("func")
            .unique()
            .join(target_profile.select("func").unique(), on="func", how="inner"),
            # Compute the number of unique traces seen in the baseline profile.
            baseline_profile.select("trace").count(),
            # Compute the number of unique functions seen in the baseline profile.
            baseline_profile.select("func").unique().count(),
            # Compute the number of unique baseline traces that have non-zero exclusive cost.
            baseline_profile.filter(pl.col("exclusive") != 0).select("trace").count(),
            # Compute the number of unique baseline functions that have non-zero exclusive cost.
            baseline_profile.filter(pl.col("exclusive") != 0).select("func").unique().count(),
            # Compute the number of unique traces seen in the target profile.
            target_profile.select("trace").count(),
            # Compute the number of unique functions seen in the target profile.
            target_profile.select("func").unique().count(),
            # Compute the number of unique target traces that have non-zero exclusive cost.
            target_profile.filter(pl.col("exclusive") != 0).select("trace").count(),
            # Compute the number of unique target functions that have non-zero exclusive cost.
            target_profile.filter(pl.col("exclusive") != 0).select("func").unique().count(),
        ]
    )
    if baseline_df.height == 0:
        log.error("Baseline profile is empty. Terminating.")
    elif target_df.height == 0:
        log.error("Target profile is empty. Terminating.")

    # So far, only some of the baseline and target features are computed as computing them eagerly
    # during the parsing is too expensive. Instead, we can compute them more efficiently now.
    _update_profile_features(
        baseline_features,
        baseline_df,
        *features[:4],
    )
    _update_profile_features(
        target_features,
        target_df,
        *features[4:],
    )
    return pl_structs.PolarsTraceProfilePair(
        pl_structs.PolarsTraceProfile(baseline_df, baseline_features, function_maps),
        pl_structs.PolarsTraceProfile(target_df, target_features, function_maps),
        common_traces,
        common_funcs,
    )


def _update_profile_features(
    features: structs.ProfileFeatures,
    prof: pl.DataFrame,
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
    features.total_resources = int(prof["exclusive"].sum())


def merge_and_filter_polars_profiles(
    baseline: pl_structs.PolarsTraceProfile,
    target: pl_structs.PolarsTraceProfile,
    filter_params: structs.FilterParameters,
) -> pl_structs.PolarsMergedTraceProfiles:
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

    return pl_structs.PolarsMergedTraceProfiles(
        *pl.collect_all([filtered_merged_traces, filtered_merged_funcs])
    )


def polars_merged_to_tabular_profiles(
    merged: pl_structs.PolarsMergedTraceProfiles, max_traces_per_func: int
) -> pl_structs.PolarsTabularTraceProfiles:
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
    # function keeps only up to top 'max_traces_per_func' traces w.r.t. both inclusive and
    # exclusive proportional diff metric.
    # TODO: calculate the top traces also for other metrics, e.g., absolute delta or relative
    #  delta. This will, however, require some hook on sort operation in our trace tables to
    #  always retrieve the correct set of functions.
    top_incl_traces = (
        # This groups traces on a per-function basis and then filters up to top N rows (traces)
        # for each function w.r.t. the inclusive proportional delta.
        merged.traces.lazy()
        .group_by("func")
        .agg(
            pl.struct(pl.exclude("func"))
            .top_k_by("prop_diff_incl", k=max_traces_per_func)
            .alias("rows")
        )
        .explode("rows")
        .unnest("rows")
    )

    top_excl_traces = (
        # Similar to the previous step, but filters based on th exclusive proportional delta.
        merged.traces.lazy()
        .group_by("func")
        .agg(
            pl.struct(pl.exclude("func"))
            .top_k_by("prop_diff_excl", k=max_traces_per_func)
            .alias("rows")
        )
        .explode("rows")
        .unnest("rows")
    )

    # Concatenate and deduplicate both tables. For example, if `max_traces_per_func` = 10 and some
    # function has a total of 15 traces, but only 13 of them appear in both top selections, the
    # resulting table will keep only the 13 traces instead of 20 (7 of which would be duplicated).
    table_traces_lf = (
        pl.concat([top_incl_traces, top_excl_traces])
        .unique(subset=["func", "trace"])
        .with_columns(*abs_rel_diff_expressions)
        .sort("func", descending=False)
    )

    return pl_structs.PolarsTabularTraceProfiles(*pl.collect_all([table_traces_lf, table_funcs_lf]))
