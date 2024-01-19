"""Regression analysis postprocessor module."""
from __future__ import annotations

# Standard Imports
from typing import Any

# Third-Party Imports
import click

# Perun Imports
from perun.logic import runner
from perun.postprocess.regression_analysis import data_provider, methods, regression_models, tools
from perun.profile.factory import pass_profile, Profile
from perun.utils import metrics
from perun.utils.common import cli_kit
from perun.utils.structs import PostprocessStatus


_DEFAULT_STEPS = 3


def postprocess(
    profile: Profile, **configuration: Any
) -> tuple[PostprocessStatus, str, dict[str, Any]]:
    """Invoked from perun core, handles the postprocess actions

    :param dict profile: the profile to analyze
    :param configuration: the perun and options context
    """
    # Validate the input configuration
    tools.validate_dictionary_keys(configuration, ["method", "regression_models", "steps"], [])

    # Perform the regression analysis
    analysis = methods.compute(
        data_provider.generic_profile_provider(profile, **configuration),
        configuration["method"],
        configuration["regression_models"],
        steps=configuration["steps"],
    )
    store_model_counts(analysis)
    # Store the results
    new_profile = tools.add_models_to_profile(profile, analysis)

    return PostprocessStatus.OK, "", {"profile": new_profile}


def store_model_counts(analysis: list[dict[str, Any]]) -> None:
    """Store the number of best-fit models for each model category as a metric.

    :param list analysis: the list of inferred models.
    """
    # Ignore if metrics are disabled
    if not metrics.is_enabled():
        return

    # Get the regression model with the highest R^2 for all functions
    funcs: dict[str, Any] = {}
    func_summary: dict[str, dict[str, Any]] = {}
    for record in analysis:
        func_record = funcs.setdefault(
            record["uid"], {"r_square": record["r_square"], "model": record["model"]}
        )
        if record["r_square"] > func_record["r_square"]:
            func_record["r_square"] = record["r_square"]
            func_record["model"] = record["model"]

        summary_record = func_summary.setdefault(record["uid"], {})
        summary_record[record["model"]] = record["r_square"]
    metrics.save_separate(f"details/{metrics.Metrics.metrics_id}.json", func_summary)

    # Count the number of respective models
    models = {model: 0 for model in regression_models.get_supported_models() if model != "all"}
    models["undefined"] = 0
    for func_record in funcs.values():
        models["undefined" if (func_record["r_square"] <= 0.5) else func_record["model"]] += 1
    # Store the counts in the metrics
    for model, count in models.items():
        metrics.add_metric(f"{model}_model", count)


@click.command()
@click.option(
    "--method",
    "-m",
    type=click.Choice(methods.get_supported_param_methods()),
    default="full",
    multiple=False,
    help=(
        "Will use the <method> to find the best fitting models for the given profile. "
        "By default 'full' computation will be performed"
    ),
)
@click.option(
    "--regression_models",
    "-r",
    type=click.Choice(regression_models.get_supported_models()),
    required=False,
    multiple=True,
    help=(
        "Restricts the list of regression models used by the"
        " specified <method> to fit the data. If omitted, all"
        " regression models will be used in the computation."
    ),
)
@click.option(
    "--steps",
    "-s",
    type=click.IntRange(1, None, clamp=True),
    required=False,
    default=_DEFAULT_STEPS,
    help=(
        "Restricts the number of number of steps / data parts used"
        " by the iterative, interval and initial guess methods"
    ),
)
@click.option(
    "--depending-on",
    "-dp",
    "per_key",
    default="structure-unit-size",
    nargs=1,
    metavar="<depending_on>",
    callback=cli_kit.process_resource_key_param,
    help="Sets the key that will be used as a source of independent variable.",
)
@click.option(
    "--of",
    "-o",
    "of_key",
    nargs=1,
    metavar="<of_resource_key>",
    default="amount",
    callback=cli_kit.process_resource_key_param,
    help="Sets key for which we are finding the model.",
)
@pass_profile
def regression_analysis(profile: Profile, **kwargs: Any) -> None:
    """Finds fitting regression models to estimate models of profiled resources.

    \b
      * **Limitations**: Currently limited to models of `amount` depending on
        `structural-unit-size`
      * **Dependencies**: :ref:`collectors-trace`

    Regression analyzer tries to find a fitting model to estimate the `amount`
    of resources depending on `structural-unit-size`.

    The following strategies are currently available:

        1. **Full Computation** uses data points to obtain the best
           fitting model for each type of model from the database (unless
           ``--regression_models``/``-r`` restrict the set of models)

        2. **Iterative Computation** uses a percentage of data points to obtain
           some preliminary models together with their errors or fitness. The
           most fitting model is then expanded, until it is fully computed or
           some other model becomes more fitting.

        3. **Full Computation with initial estimate** first uses some percent
           of data to estimate which model would be best fitting. Given model
           is then fully computed.

        4. **Interval Analysis** uses finer set of intervals of data and
           estimates models for each interval providing more precise modeling
           of the profile.

        5. **Bisection Analysis** fully computes the models for full interval.
           Then it does a split of the interval and computes new models for
           them. If the best fitting models changed for sub intervals, then we
           continue with the splitting.

    Currently, we support **linear**, **quadratic**, **power**, **logarithmic**
    and **constant** models and use the `coefficient of determination`
    (:math:`R^2`) to measure the fitness of model. The models are stored as
    follows:

    .. code-block:: json

        \b
        {
            "uid": "SLList_insert(SLList*, int)",
            "r_square": 0.0017560012128507133,
            "coeffs": [
                {
                    "value": 0.505375215875552,
                    "name": "b0"
                },
                {
                    "value": 9.935159839322705e-06,
                    "name": "b1"
                }
            ],
            "x_start": 0,
            "x_end": 11892,
            "model": "linear",
            "method": "full",
        }

    For more details about regression analysis refer to
    :ref:`postprocessors-regression-analysis`. For more details how to collect
    suitable resources refer to :ref:`collectors-trace`.
    """
    runner.run_postprocessor_on_profile(profile, "regression_analysis", kwargs)
