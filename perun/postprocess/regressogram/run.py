"""
Postprocessor module with non-parametric analysis using the regressogram method.
"""
from __future__ import annotations

# Standard Imports
from typing import Any

# Third-Party Imports
import click

# Perun Imports
from perun.logic import runner
from perun.postprocess.regression_analysis import data_provider, tools
from perun.postprocess.regressogram import methods
from perun.profile.factory import pass_profile, Profile
from perun.utils.common import cli_kit
from perun.utils.structs import PostprocessStatus


_DEFAULT_BUCKETS_METHOD = "doane"
_DEFAULT_STATISTIC = "mean"


def postprocess(
    profile: Profile, **configuration: Any
) -> tuple[PostprocessStatus, str, dict[str, Any]]:
    """
    Invoked from perun core, handles the postprocess actions

    :param dict profile: the profile to analyze
    :param configuration: the perun and options context
    """
    # Perform the non-parametric analysis using the regressogram method
    regressogram_models = methods.compute_regressogram(
        data_provider.generic_profile_provider(profile, **configuration), configuration
    )

    # Return the profile after the execution of regressogram method
    return (
        PostprocessStatus.OK,
        "",
        {"profile": tools.add_models_to_profile(profile, regressogram_models)},
    )


@click.command()
@click.option(
    "--bucket_number",
    "-bn",
    required=False,
    multiple=False,
    type=click.IntRange(min=1, max=None),
    help=(
        "Restricts the number of buckets to which will be "
        "placed the values of the selected statistics."
    ),
)
@click.option(
    "--bucket_method",
    "-bm",
    required=False,
    type=click.Choice(methods.get_supported_selectors()),
    default=_DEFAULT_BUCKETS_METHOD,
    multiple=False,
    help="Specifies the method to estimate the optimal number of buckets.",
)
@click.option(
    "--statistic_function",
    "-sf",
    type=click.Choice(["mean", "median"]),
    required=False,
    default=_DEFAULT_STATISTIC,
    multiple=False,
    help=(
        "Will use the <statistic_function> to compute the values "
        "for points within each bucket of regressogram."
    ),
)
@cli_kit.resources_key_options
@pass_profile
def regressogram(profile: Profile, **kwargs: Any) -> None:
    """
    Execution of the interleaving of profiled resources by **regressogram** models.

    \b
      * **Limitations**: `none`
      * **Dependencies**: `none`

    Regressogram belongs to the simplest non-parametric methods and its properties are
    the following:

        **Regressogram**: can be described such as step function (i.e. constant function
        by parts). Regressogram uses the same basic idea as a histogram for density estimate.
        This idea is in dividing the set of values of the x-coordinates (`<per_key>`) into
        intervals and the estimate of the point in concrete interval takes the mean/median of the
        y-coordinates (`<of_resource_key>`), respectively of its value on this sub-interval.
        We currently use the `coefficient of determination` (:math:`R^2`) to measure the fitness of
        regressogram. The fitness of estimation of regressogram model depends primarily on the
        number of buckets into which the interval will be divided. The user can choose number of
        buckets manually (`<bucket_window>`) or use one of the following methods to estimate the
        optimal number of buckets (`<bucket_method>`):

            | - **sqrt**: square root (of data size) estimator, used for its speed and simplicity
            | - **rice**: does not take variability into account, only data size and commonly
                    overestimates
            | - **scott**: takes into account data variability and data size, less robust estimator
            | - **stone**: based on leave-one-out cross validation estimate of the integrated
                    squared error
            | - **fd**: robust, takes into account data variability and data size, resilient to
                    outliers
            | - **sturges**: only accounts for data size, underestimates for large non-gaussian data
            | - **doane**: generalization of Sturges' formula, works better with non-gaussian data
            | - **auto**: max of the Sturges' and 'fd' estimators, provides good all around
                    performance

        .. _SciPy: https://docs.scipy.org/doc/numpy/reference/generated/numpy.histogram_bin_edges.
                html#numpy.histogram_bucket_edges

        For more details about these methods to estimate the optimal number of buckets or to view
        the code of these methods, you can visit SciPy_.

    For more details about this approach of non-parametric analysis refer to
    :ref:`postprocessors-regressogram`.
    """
    runner.run_postprocessor_on_profile(profile, "regressogram", kwargs)
