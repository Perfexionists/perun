"""TODO: Write short docstring of the new postprocessor

TODO: Write long docstring of the new postprocessor
"""

import click

import perun.logic.runner as runner
import perun.postprocess.kernel_regression.methods as methods
import perun.postprocess.regression_analysis.data_provider as data_provider
import perun.postprocess.regression_analysis.tools as tools
import perun.utils.cli_helpers as cli_helpers
from perun.utils.helpers import PostprocessStatus

__author__ = 'Simon Stupinsky'

# Supported types of regression estimator:
# - 'lc': local-constant (Nadaraya-Watson kernel regression), 'll': local-linear
# -- First estimator is set as default: 'll'
_REGRESSION_ESTIMATORS = ['ll', 'lc']
# Supported methods for bandwidth estimation:
# - 'cv_ls': least-squares cross validation, 'aic': AIC Hurvich bandwidth estimation
# -- First estimate method is set as default: 'cv_ls'
_BANDWIDTH_METHODS = ['cv_ls', 'aic']
# Efficient execution of the bandwidth estimation
_DEFAULT_EFFICIENT = False
# The way of performing of the bandwidth estimation: randomize or routine
_DEFAULT_RANDOMIZE = False
# Default size of the sub-samples
_DEFAULT_N_SUB = 50
# Default number of random re-samples used to bandwidth estimation
_DEFAULT_N_RES = 25
# Using the median of all scaling factors for each sub-sample
# - Default is computed the mean of all scaling factors
_DEFAULT_RETURN_MEDIAN = False
# Set of kernels for use with `kernel-smoothing` mode of kernel-regression
# - Gaussian (normal) kernel by default at computation
_KERNEL_TYPES = ['normal', 'tricube', 'epanechnikov', 'epanechnikov4', 'normal4']
# Supported method for non-parametric regression using kernel methods
# - Default non-parametric regression method: local-polynomial(q=1)
_SMOOTHING_METHODS = ['local-polynomial', 'spatial-average', 'local-linear']
# Default value for order of the polynomial to fit with `local-polynomial` kernel smoothing method
_DEFAULT_POLYNOMIAL_ORDER = 3
# Default range (minimal and maximal values) for automatic bandwidth selection at `kernel-ridge`
_DEFAULT_GAMMA_RANGE = (1e-5, 2e-1)
# Default size of step for iteration over given range in gamma parameter at `kernel-ridge`
_DEFAULT_GAMMA_STEP = 1e-5


# TODO: The possibility of before postprocessing phase


def postprocess(profile, **configuration):
    """
    Invoked from perun core, handles the postprocess actions

    :param dict profile: the profile to analyze
    :param configuration: the perun and options context
    """
    # Perform the non-parametric analysis using the kernel regression
    kernel_models = methods.compute_kernel_regression(
        data_provider.data_provider_mapper(profile, **configuration), configuration)

    # Return the profile after the execution of kernel regression
    return PostprocessStatus.OK, '', {'profile': tools.add_models_to_profile(profile, kernel_models)}


# TODO: The possibility of after postprocessing phase


@click.command(name='estimator-settings')
@click.option('--reg-type', '-rt', type=click.Choice(_REGRESSION_ESTIMATORS), default=_REGRESSION_ESTIMATORS[0],
              help=('Provides the type for regression estimator. Supported types are: "lc": local-constant '
                    '(Nadaraya-Watson) and "ll": local-linear estimator. Default is "ll". For more information '
                    'about these types you can visit Perun Documentation.'))
@click.option('--bandwidth-method', '-bw', type=click.Choice(_BANDWIDTH_METHODS), default=_BANDWIDTH_METHODS[0],
              help='Provides the method for bandwidth selection. Supported values are: "cv-ls": least-squares'
                   'cross validation and "aic": AIC Hurvich bandwidth estimation. Default is "cv-ls". For more '
                   'information about these methods you can visit Perun Documentation.')
@click.option('--efficient/--no-efficient', default=_DEFAULT_EFFICIENT,
              help=('If True, is executing the efficient bandwidth estimation - by taking smaller '
                    'sub-samples and estimating the scaling factor of each sub-sample. It is useful '
                    'for large samples and/or multiple variables. If False (default), all data is '
                    'used at the same time.'))
@click.option('--randomize/--no-randomize', default=_DEFAULT_RANDOMIZE,
              help=('If True, the bandwidth estimation is performed by taking <n_res> random re-samples '
                    'of size <n_sub> from the full sample. If set to False (default), is performed by '
                    'slicing the full sample in sub-samples of <n_sub> size, so that all samples are '
                    'used once.'))
@click.option('--n-sub', '-ns', type=click.IntRange(min=1, max=None, clamp=True), default=_DEFAULT_N_SUB,
              help='Size of the sub-samples (default is 50).')
@click.option('--n-res', '-nr', type=click.IntRange(min=1, max=None, clamp=True), default=_DEFAULT_N_RES,
              help=('The number of random re-samples used to bandwidth estimation. '
                    'It has effect only if <randomize> is set to True. Default values is 25.'))
@click.option('--return-median/--return-mean', default=_DEFAULT_RETURN_MEDIAN,
              help=('If True, the estimator uses the median of all scaling factors for each sub-sample to '
                    'estimate bandwidth of the full sample. If False (default), the estimator used the mean.'))
@click.pass_context
def estimator_settings(ctx, **kwargs):
    """TODO: Write documentation of the CLI"""
    # update the current set of params with the selected mode of kernel regression
    kwargs.update({'kernel_mode': 'estimator-settings'})
    # update the current set of params with the params entered at `kernel regression` command
    kwargs.update(ctx.parent.params)
    runner.run_postprocessor_on_profile(ctx.obj, 'kernel_regression', kwargs)


@click.command(name='user-selection')
@click.option('--reg-type', '-rt', type=click.Choice(_REGRESSION_ESTIMATORS), default=_REGRESSION_ESTIMATORS[0],
              help=('Provides the type for regression estimator. Supported types are: "lc": local-constant '
                    '(Nadaraya-Watson) and "ll": local-linear estimator. Default is "ll". For more information '
                    'about these types you can visit Perun Documentation.'))
@click.option('--bandwidth-value', '-bv', type=click.FLOAT, required=True,
              help='The float value of <bandwidth> defined by user, which will be used at kernel regression.')
@click.pass_context
def user_selection(ctx, **kwargs):
    """TODO: Write documentation of the CLI"""
    # update the current set of params with the selected mode of kernel regression
    kwargs.update({'kernel_mode': 'user-selection'})
    # update the current set of params with the params entered at `kernel regression` command
    kwargs.update(ctx.parent.params)
    runner.run_postprocessor_on_profile(ctx.obj, 'kernel_regression', kwargs)


@click.command(name='method-selection')
@click.option('--reg-type', '-rt', type=click.Choice(_REGRESSION_ESTIMATORS), default=_REGRESSION_ESTIMATORS[0],
              help=('Provides the type for regression estimator. Supported types are: "lc": local-constant '
                    '(Nadaraya-Watson) and "ll": local-linear estimator. Default is "ll". For more information '
                    'about these types you can visit Perun Documentation.'))
@click.option('--bandwidth-method', '-bm', type=click.Choice(methods.BW_SELECTION_METHODS), required=True,
              help='Provides the helper method to determine the kernel bandwidth. The <method_name> '
                   'will be used to compute the bandwidth, which will be used at kernel regression.')
@click.pass_context
def method_selection(ctx, **kwargs):
    """TODO: Write documentation of the CLI"""
    # update the current set of params with the selected mode of kernel regression
    kwargs.update({'kernel_mode': 'method-selection'})
    # update the current set of params with the params entered at `kernel regression` command
    kwargs.update(ctx.parent.params)
    runner.run_postprocessor_on_profile(ctx.obj, 'kernel_regression', kwargs)


@click.command(name='kernel-smoothing')
@click.option('--kernel-type', '-kt', type=click.Choice(_KERNEL_TYPES), default=_KERNEL_TYPES[0],
              help=('Provides the set of kernels to execute the `kernel-smoothing` with kernel '
                    'selected by the user. For exact definitions of these kernels and more '
                    'information about it, you can visit the Perun Documentation.'))
@click.option('--smoothing-method', '-sm', type=click.Choice(_SMOOTHING_METHODS), default=_SMOOTHING_METHODS[0],
              help=('Provides kernel smoothing methods to executing non-parametric regressions: `local-polynomial` '
                    'perform a local-polynomial regression in N-D using a user-provided kernel; `local-linear` '
                    'perform a local-linear regression using a user-provided kernel and `spatial-average` perform'
                    'a Nadaraya-Watson regression on the data (so called local-constant regression).'))
@click.option('--bandwidth-method', '-bm', type=click.Choice(methods.BW_SELECTION_METHODS),
              default=methods.BW_SELECTION_METHODS[0],
              help=('Provides the helper method to determine the kernel bandwidth. The <bandwidth_method> '
                    'will be used to compute the bandwidth, which will be used at kernel-smoothing regression. '
                    'Cannot be entered in combination with <bandwidth-value>, then will be ignored and will be '
                    'accepted value from <bandwidth-value>.'))
@click.option('--bandwidth-value', '-bv', type=click.FLOAT,
              help=('The float value of <bandwidth> defined by user, which will be used at kernel regression. '
                    'If is entered in the combination with <bandwidth-method>, then method will be ignored.'))
@click.option('--polynomial-order', '-q', type=click.IntRange(min=1, max=None, clamp=True),
              default=_DEFAULT_POLYNOMIAL_ORDER,
              help=('Provides order of the polynomial to fit. Default value of the order is equal to 3. Is '
                    'accepted only by `local-polynomial` <smoothing-method>, another methods ignoring it.'))
@click.pass_context
def kernel_smoothing(ctx, **kwargs):
    """TODO: Write documentation of the CLI"""
    # update the current set of params with the selected mode of kernel regression
    kwargs.update({'kernel_mode': 'kernel-smoothing'})
    # update the current set of params with the params entered at `kernel regression` command
    kwargs.update(ctx.parent.params)
    runner.run_postprocessor_on_profile(ctx.obj, 'kernel_regression', kwargs)


@click.command(name='kernel-ridge')
@click.option('--gamma-range', '-gr', type=click.FLOAT, nargs=2, default=_DEFAULT_GAMMA_RANGE,
              callback=methods.valid_range_values,
              help=('Provides the range for automatic bandwidth selection of the kernel via leave-one-out'
                    'cross-validation. One value from these range will be selected with minimizing the '
                    'mean-squared error of leave-one-out cross-validation. The first value will be taken '
                    'as the lower bound of the range and cannot be greater than the second value.'))
@click.option('--gamma-step', '-gs', type=click.FloatRange(min=0, max=None, clamp=True), default=_DEFAULT_GAMMA_STEP,
              help='Provides the size of the step, with which will be executed the iteration over the '
                   'given <gamma-range>. Cannot be greater than length of <gamma-range>, else will be set'
                   'to value of the lower bound of the <gamma_range>.')
@click.pass_context
def kernel_ridge(ctx, **kwargs):
    """TODO: Write documentation of the CLI"""
    # TODO: docstring
    methods.valid_step_size(kwargs['gamma_step'], kwargs['gamma_range'][1] - kwargs['gamma_range'][0])
    # update the current set of params with the selected mode of kernel regression
    kwargs.update({'kernel_mode': 'kernel-ridge'})
    # update the current set of params with the params entered at `kernel regression` command
    kwargs.update(ctx.parent.params)
    runner.run_postprocessor_on_profile(ctx.obj, 'kernel_regression', kwargs)


@click.group(invoke_without_command=True)
@cli_helpers.resources_key_options
@click.pass_context
def kernel_regression(ctx, **kwargs):
    """TODO: Write documentation of the CLI"""
    ctx.params['profile'] = ctx.obj
    # running default mode with use EstimatorSettings and its default parameters
    if ctx.invoked_subcommand is None:
        ctx.invoke(estimator_settings)


# Supported modes at executing kernel regression:
# - estimator-settings: with use EstimatorSettings and its arguments
# - user-selection: bandwidth defined by user itself
# - bandwidth_methods: bandwidth computed by helper method for its determine
# - kernel-smoothing: provides the ability to choose a kernel and other methods
# - kernel-ridge: TODO: doc
_SUPPORTED_MODES = [estimator_settings, user_selection, method_selection, kernel_smoothing, kernel_ridge]
# addition of sub-commands (supported modes) to main command represents by kernel_regression
for mode in _SUPPORTED_MODES:
    kernel_regression.add_command(mode)
