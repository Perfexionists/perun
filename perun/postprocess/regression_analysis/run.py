"""Regression analysis postprocessor module."""

import click

import perun.logic.runner as runner
import perun.postprocess.regression_analysis.data_provider as data_provider
import perun.postprocess.regression_analysis.tools as tools
from perun.utils.helpers import PostprocessStatus, pass_profile
from perun.postprocess.regression_analysis.methods import get_supported_methods, compute
from perun.postprocess.regression_analysis.regression_models import get_supported_models

__author__ = 'Jiri Pavela'

_DEFAULT_STEPS = 3


def postprocess(profile, **configuration):
    """Invoked from perun core, handles the postprocess actions

    Arguments:
        profile(dict): the profile to analyze
        configuration: the perun and options context
    """
    # Validate the input configuration
    tools.validate_dictionary_keys(configuration, ['method', 'regression_models', 'steps'], [])

    # Perform the regression analysis
    analysis = compute(data_provider.data_provider_mapper(profile), configuration['method'],
                       configuration['regression_models'], steps=configuration['steps'])

    # Store the results
    if 'models' not in profile['global']:
        profile['global']['models'] = analysis
    else:
        profile['global']['models'].extend(analysis)

    return PostprocessStatus.OK, "", {'profile': profile}


@click.command()
@click.option('--method', '-m', type=click.Choice(get_supported_methods()),
              required=True, multiple=False,
              help='The regression method that will be used for computation.')
@click.option('--regression_models', '-r', type=click.Choice(get_supported_models()),
              required=False, multiple=True,
              help=('List of regression models used by the regression method to fit the data. '
                    'If omitted, all regression models will be used in the computation.'))
@click.option('--steps', '-s', type=click.IntRange(1, None, True),
              required=False, default=_DEFAULT_STEPS,
              help='The number of steps / data parts used by the iterative, interval and '
                   'initial guess methods')
@pass_profile
def regression_analysis(profile, **kwargs):
    """Computation of the best fitting regression model from the profile data."""
    runner.run_postprocessor_on_profile(profile, 'regression_analysis', kwargs)
