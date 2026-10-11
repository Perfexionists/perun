"""Functions for converting folded profiles into Polars profiles."""

from __future__ import annotations

# Standard Imports
from collections.abc import Sequence
import pathlib
from typing import Protocol

# Third-Party Imports
import polars as pl

# Perun Imports
from perun.profiles.folded import parser
from perun.profiles.polars import parser as pl_parser, structs
from perun.profiles.structs import PostprocessParameters, ProfileFeatures
from perun.utils import log, streams
from perun.utils.common.common_kit import Aggregations


class PolarsAggregate(Protocol):
    """Polars aggregation callable type."""

    def __call__(self, *args: str) -> pl.Expr: ...


def folded_profiles_to_polars_lf(
    folded_profiles: Sequence[pathlib.Path],
    postprocess_params: PostprocessParameters,
    maps: structs.FunctionMaps,
) -> tuple[pl.LazyFrame, ProfileFeatures]:
    """Load folded profile(s) into a Polars LazyFrame according to the parse parameters.

    If multiple folded profiles are given, we aggregate them into a single LazyFrame according to
    the aggregation function specified in the parse parameters.

    Note that the returned profile features contain only those features that can be computed
    cheaply during the parsing.

    :param folded_profiles: possibly a collection of folded profile paths
    :param postprocess_params: parsing parameters and configuration
    :param maps: function maps

    :return: a (possibly aggregated) LazyFrame and incomplete profile features
    """
    features: ProfileFeatures = ProfileFeatures()
    # Check whether we should squash recursion and select the parse function accordingly.
    parse_func = (
        pl_parser.parse_polars_squash
        if postprocess_params.squash_recursion
        else pl_parser.parse_polars_no_squash
    )
    parsed_traces: list[pl.LazyFrame] = []
    for profile_path in folded_profiles:
        with streams.open_folded_profile(profile_path) as folded_handle:
            parsed_traces.append(
                parse_func(
                    parser.parse_events_from_stream(folded_handle),
                    maps,
                    postprocess_params,
                    features,
                )
            )
            log.minor_success(log.path_style(str(profile_path)), "parsed")

    if len(parsed_traces) == 1:
        # No need to aggregate data for a single input profile.
        return parsed_traces[0], features
    # We have parsed multiple profiles. Hence, each trace might have more than 1 value that we
    # need to aggregate. We do that by concatenating the profiles, grouping the same traces and
    # then aggregating the values.
    agg_callable = _get_aggregation_polars_callable(postprocess_params.agg_func)
    return (
        pl.concat(parsed_traces)
        .group_by("func", "trace")
        .agg([agg_callable("inclusive").cast(pl.Int64), agg_callable("exclusive").cast(pl.Int64)]),
        features,
    )


def _get_aggregation_polars_callable(agg_func: Aggregations) -> PolarsAggregate:
    """Maps an aggregation function to a polars callables.

    If the function name does not have a valid mapping, the default function callable is used.

    :param agg_func: aggregation function
    :return: a polars callable
    """
    callable_map: dict[Aggregations, PolarsAggregate] = {
        Aggregations.SUM: pl.sum,
        Aggregations.MIN: pl.min,
        Aggregations.MAX: pl.max,
        Aggregations.COUNT: pl.count,
        Aggregations.NUNIQUE: pl.n_unique,
        Aggregations.MEAN: pl.mean,
        Aggregations.MEDIAN: pl.median,
    }
    try:
        return callable_map[agg_func]
    except KeyError:
        return callable_map[Aggregations.default()]
