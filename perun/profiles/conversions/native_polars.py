"""Functions for converting native profiles to Polars representations."""

from __future__ import annotations

# Standard Imports
from typing import TYPE_CHECKING

# Third-Party Imports
import polars as pl

# Perun Imports
from perun.profiles import structs
from perun.profiles.conversions import native_folded
from perun.profiles.polars import parser, structs as pl_structs

if TYPE_CHECKING:
    from perun.profiles.native import Profile


def native_to_polars_lf(
    native_profile: Profile,
    postprocess_params: structs.PostprocessParameters,
    maps: pl_structs.FunctionMaps,
) -> tuple[pl.LazyFrame, structs.ProfileFeatures]:
    """Load and postprocess a Perun profile into a Polars LazyFrame.

    The resource consumption for each UID are aggregated into a single value according to the
    aggregation function specified in the postprocessing parameters.

    Note that the returned profile features contain only those features that can be computed
    cheaply during the parsing.

    :param native_profile: the Perun profile to convert to Polars
    :param postprocess_params: postprocessing parameters and configuration
    :param maps: function maps

    :return: a LazyFrame and incomplete profile features structure
    """
    features: structs.ProfileFeatures = structs.ProfileFeatures()
    # Check whether we should squash recursion and select the parse function accordingly.
    parse_func = (
        parser.parse_polars_squash
        if postprocess_params.squash_recursion
        else parser.parse_polars_no_squash
    )
    # We re-use the native-to-folded conversion which takes care of aggregating the resource values.
    polars_prof: pl.LazyFrame = parse_func(
        native_folded.native_to_folded(native_profile, "amount", postprocess_params.agg_func),
        maps,
        postprocess_params,
        features,
    )
    return polars_prof, features
