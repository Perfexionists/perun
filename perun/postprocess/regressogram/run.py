"""
Postprocessor module with non-parametric analysis using the regressogram method.
"""
import click

import perun.logic.runner as runner
import perun.postprocess.regressogram.methods as methods
from perun.postprocess.regression_analysis.data_provider import data_provider_mapper
from perun.postprocess.regression_analysis.tools import add_analysis_to_profile
from perun.utils.cli_helpers import process_resource_key_param
from perun.utils.helpers import PostprocessStatus, pass_profile

__author__ = 'Simon Stupinsky'

_DEFAULT_BINS_METHODS = 'doane'
_DEFAULT_STATISTIC = 'mean'


# TODO: The possibility of before postprocessing phase

def postprocess(profile, **configuration):
    """
    Invoked from perun core, handles the postprocess actions

    :param dict profile: the profile to analyze
    :param configuration: the perun and options context
    """
    # Perform the non-parametric analysis using the regressogram method
    analysis = methods.compute(data_provider_mapper(profile, **configuration), configuration)

    # Store the results
    profile = add_analysis_to_profile(profile, analysis)

    # Return the profile after the execution of regressogram method
    return PostprocessStatus.OK, '', {'profile': profile}


# TODO: The possibility of after postprocessing phase

@click.command()
@click.option('--bins', '-b', required=False, default=_DEFAULT_BINS_METHODS,
              multiple=False, callback=methods.choose_bin_sizes,
              help=('Restricts the number of bins or method for its determination, to which '
                    'will be placed the values of the selected statistics at regressogram method.'))
@click.option('--statistic', '-s', type=click.Choice(['mean', 'median']),
              required=False, default=_DEFAULT_STATISTIC, multiple=False,
              help='Will use the <statistic> to compute the values for points within each bin of regressogram.')
@click.option('--depending-on', '-dp', 'per_key', default='structure-unit-size',
              nargs=1, metavar='<depending_on>', callback=process_resource_key_param,
              help='Sets the key that will be used as a source of independent variable.')
@click.option('--of', '-o', 'of_key', nargs=1, metavar='<of_resource_key>',
              default='amount', callback=process_resource_key_param,
              help='Sets key for which we are finding the model.')
@pass_profile
def regressogram(profile, **kwargs):
    """
    Execution of the interleaving of profiled resources by **regressogram** models.

    \b
      * **Limitations**: `none`
      * **Dependencies**: `none`

    Non-parametric analyzer tries to find a fitting model to estimate the `<of_resource_key>`
    of resources depending on `<depending_on>` by using the regressogram method:

        **Regressogram**: can be described such as step function (i.e. constant function
        by parts). Regressogram uses the same basic idea as a histogram for density estimate.
        This idea is in dividing the set of values of the independent variable (`<depending_on>`) into
        intervals and the estimate of the point in concrete interval takes the mean/median of the
        dependent variable (`<of_resource_key>`), respectively of its value on this sub-interval.
        We currently use the `coefficient of determination` (:math:`R^2`) to measure the fitness of
        regressogram. The models are stored as we can see an example below.

    For more details about this approach of non-parametric analysis refer to :ref:`postprocessors-regressogram`.
    """
    runner.run_postprocessor_on_profile(profile, 'regressogram', kwargs)
