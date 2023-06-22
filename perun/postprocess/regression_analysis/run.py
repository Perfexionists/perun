"""Regression analysis postprocessor module."""

import click

from typing import TypedDict, Any
from typing_extensions import Unpack

import perun.logic.runner as runner
import perun.postprocess.regression_analysis.data_provider as data_provider
import perun.postprocess.regression_analysis.tools as tools
import perun.utils.cli_helpers as cli_helpers
import perun.postprocess.regression_analysis.methods as methods
import perun.postprocess.regression_analysis.regression_models as reg_models

from perun.profile.factory import pass_profile
from perun.utils.structs import PostprocessStatus
import perun.utils.metrics as metrics

__author__ = 'Jiri Pavela'

_DEFAULT_STEPS = 3


class Configuration(TypedDict):
    method: str
    regression_models: list[str]
    steps: int


def postprocess(
        profile: dict, **configuration: Unpack[Configuration]
) -> tuple[PostprocessStatus, str, dict]:
    """Invoked from perun core, handles the postprocess actions

    :param dict profile: the profile to analyze
    :param configuration: the perun and options context
    """
    # Validate the input configuration
    tools.validate_dictionary_keys(configuration, ['method', 'regression_models', 'steps'], [])

    # Perform the regression analysis
    analysis = methods.compute(data_provider.data_provider_mapper(profile, **configuration),
                               configuration['method'], configuration['regression_models'],
                               steps=configuration['steps'])
    store_model_counts(analysis)
    # Store the results
    profile = tools.add_models_to_profile(profile, analysis)

    return PostprocessStatus.OK, "", {'profile': profile}


def store_model_counts(analysis: list[dict]):
    """ Store the number of best-fit models for each model category as a metric.

    :param list analysis: the list of inferred models.
    """
    # Ignore if metrics are disabled
    if not metrics.is_enabled():
        return

    # Get the regression model with the highest R^2 for all functions
    funcs = {}  # type: dict[str, Any]
    func_summary = {}  # type: dict[str, dict]
    for record in analysis:
        func_record = funcs.setdefault(
            record['uid'], {'r_square': record['r_square'], 'model': record['model']}
        )
        if record['r_square'] > func_record['r_square']:
            func_record['r_square'] = record['r_square']
            func_record['model'] = record['model']

        summary_record = func_summary.setdefault(record['uid'], {})
        summary_record[record['model']] = record['r_square']
    metrics.save_separate('details/{}.json'.format(metrics.Metrics.metrics_id), func_summary)

    # Count the number of respective models
    models = {model: 0 for model in reg_models.get_supported_models() if model != 'all'}
    models['undefined'] = 0
    for func_record in funcs.values():
        models['undefined' if (func_record['r_square'] <= 0.5) else func_record['model']] += 1
    # Store the counts in the metrics
    for model, count in models.items():
        metrics.add_metric('{}_model'.format(model), count)


@click.command()
@click.option('--method', '-m', type=click.Choice(methods.get_supported_param_methods()),
              required=True, multiple=False,
              help='Will use the <method> to find the best fitting models for'
                   ' the given profile.')
@click.option('--regression_models', '-r', type=click.Choice(reg_models.get_supported_models()),
              required=False, multiple=True,
              help=('Restricts the list of regression models used by the'
                    ' specified <method> to fit the data. If omitted, all'
                    ' regression models will be used in the computation.'))
@click.option('--steps', '-s', type=click.IntRange(1, None, True),
              required=False, default=_DEFAULT_STEPS,
              help=('Restricts the number of number of steps / data parts used'
                    ' by the iterative, interval and initial guess methods'))
@click.option('--depending-on', '-dp', 'per_key', default='structure-unit-size',
              nargs=1, metavar='<depending_on>',
              callback=cli_helpers.process_resource_key_param,
              help="Sets the key that will be used as a source of independent variable.")
@click.option('--of', '-o', 'of_key', nargs=1, metavar="<of_resource_key>",
              default='amount', callback=cli_helpers.process_resource_key_param,
              help="Sets key for which we are finding the model.")
@pass_profile
def regression_analysis(profile: dict, **kwargs: Unpack[Configuration]):
    """Finds fitting regression models to estimate models of profiled resources.

    \b
      * **Limitations**: Currently limited to models of `amount` depending on
        `structural-unit-size`
      * **Dependencies**: :ref:`collectors-trace`

    Regression analyzer tries to find a fitting model to estimate the `amount`
    of resources depending on `structural-unit-size`.

    The following strategies are currently available:

        1. **Full Computation** uses all of the data points to obtain the best
           fitting model for each type of model from the database (unless
           ``--regression_models``/``-r`` restrict the set of models)

        2. **Iterative Computation** uses a percentage of data points to obtain
           some preliminary models together with their errors or fitness. The
           most fitting model is then expanded, until it is fully computed or
           some other model becomes more fitting.

        3. **Full Computation with initial estimate** first uses some percent
           of data to estimate which model would be best fitting. Given model
           is then fully computed.

        4. **Interval Analysis** uses more finer set of intervals of data and
           estimates models for each interval providing more precise modeling
           of the profile.

        5. **Bisection Analysis** fully computes the models for full interval.
           Then it does a split of the interval and computes new models for
           them. If the best fitting models changed for sub intervals, then we
           continue with the splitting.

    Currently we support **linear**, **quadratic**, **power**, **logaritmic**
    and **constant** models and use the `coeficient of determination`
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

    Note that if your data are not suitable for regression analysis, check out
    :ref:`postprocessors-clusterizer` to postprocess your profile to be
    analysable by this analysis.

    For more details about regression analysis refer to
    :ref:`postprocessors-regression-analysis`. For more details how to collect
    suitable resources refer to :ref:`collectors-trace`.
    """
    runner.run_postprocessor_on_profile(profile, 'regression_analysis', kwargs)
