"""TODO: Write short docstring of the new postprocessor

TODO: Write long docstring of the new postprocessor
"""
import click.exceptions as click
import numpy as np
import pyqt_fit.nonparam_regression as smooth
import sklearn.metrics as metrics
import statsmodels.nonparametric.api as nparam

import perun.postprocess.regression_analysis.tools as tools
from perun.postprocess.kernel_regression.kernel_ridge import KernelRidge

# Supported helper methods for determines the kernel bandwidth
# - scott: Scott's Rule of Thumb (default method)
# - silverman: Silverman's Rule of Thumb
BW_SELECTION_METHODS = ['scott', 'silverman']


def compute_kernel_regression(data_gen, config):
    """
    The wrapper for kernel regression to execute the non-parametric analysis
    on the individual chunks of given resources.

    :param iter data_gen: the generator object with collected data (data provider generator)
    :param dict config: the perun and option context
    :return list of dict: the computed kernel models according to selected specification
    """
    # checking the presence of specific keys according to selected modes of kernel regression
    tools.validate_dictionary_keys(config,
                                   _MODES_REQUIRED_KEYS[config['kernel_mode']] + _MODES_REQUIRED_KEYS['common_keys'],
                                   [])

    # list of resulting models computed by kernel analysis
    kernel_models = []
    for x_pts, y_pts, uid in data_gen:
        kernel_model = execute_kernel_regression(x_pts, y_pts, config)
        kernel_model['uid'] = uid
        kernel_model['method'] = 'kernel_regression'
        # add partial result (kernel model) to the model result list - create output dictionary with kernel models
        kernel_models.append(kernel_model)
    return kernel_models


def kernel_regression(x_pts, y_pts, config):
    """
    TODO: Write documentation of `kernel_regression()`

    :param list x_pts: the list of x points coordinates
    :param list y_pts: the list of y points coordinates
    :param dict config: the perun and option context with needed parameters
    :return dict: the output dictionary with result of kernel regression
    """
    if config['kernel_mode'] == 'estimator-settings':
        bw = config.get('bandwidth_method')
    else:
        bw = np.array(config.get('bandwidth_value',
                                 nparam.bandwidths.select_bandwidth(x_pts,
                                                                    config.get('method_name', BW_SELECTION_METHODS[0]),
                                                                    kernel=None))).reshape((1, -1))

    estimator_settings = nparam.EstimatorSettings(n_res=config.get('n_res'), efficient=config.get('efficient'),
                                                  randomize=config.get('randomize'), n_sub=config.get('n_sub'),
                                                  return_median=config.get('return_median'))

    kernel_estimate = nparam.KernelReg(endog=[y_pts], exog=[x_pts], reg_type=config['reg_type'], var_type='c',
                                       bw=bw, defaults=estimator_settings)
    kernel_stats, _ = kernel_estimate.fit()

    return {
        "bandwidth": bw[0][0] if config['kernel_mode'] != 'estimator-settings' else kernel_estimate.bw[0],
        'r_square': kernel_estimate.r_squared(),
        'kernel_stats': list(kernel_stats),
    }


def iterative_computation(x_pts, y_pts, kernel_estimate, **kwargs):
    """
    TODO: Write documentation of `iterative_computation()`

    :param x_pts:
    :param y_pts:
    :param kernel_estimate:
    :param kwargs:
    :return:
    """
    kernel_values = None
    while kernel_values is None:
        try:
            kernel_values = kernel_estimate(x_pts)
        except np.linalg.LinAlgError:
            kernel_estimate = smooth.NonParamRegression(x_pts, y_pts, bandwidth=kernel_estimate.bandwidth[0][0] + 1,
                                                        kernel=kwargs.get('kernel'), method=kwargs.get('method'))
    return kernel_values


def kernel_smoothing(x_pts, y_pts, config):
    """
    TODO: Write documentation of `kernel_smoothing()`

    :param list x_pts: the list of x points coordinates
    :param list y_pts: the list of y points coordinates
    :param dict config: the perun and option context with needed parameters
    :return dict: the output dictionary with result of kernel regression
    """
    x_pts = np.asanyarray(x_pts, dtype=np.float_)
    y_pts = np.asanyarray(y_pts, dtype=np.float_)

    kernel = _KERNEL_TYPES_MAPS[config['kernel_type']]
    method = _SMOOTHING_METHODS_MAPS[config['smoothing_method']](config['polynomial_order'])

    if config['bandwidth_value']:
        kernel_estimate = smooth.NonParamRegression(x_pts, y_pts, bandwidth=config['bandwidth_value'], kernel=kernel,
                                                    method=method)
    else:
        covariance = smooth.npr_methods.kde.scotts_covariance(x_pts) if config['bandwidth_method'] == 'scott' else \
            smooth.npr_methods.kde.silverman_covariance(x_pts)
        kernel_estimate = smooth.NonParamRegression(x_pts, y_pts, covariance=covariance, method=method, kernel=kernel)

    kernel_estimate.fit()
    kernel_values = iterative_computation(x_pts, y_pts, kernel_estimate, method=method, kernel=kernel)

    return {
        'bandwidth': kernel_estimate.bandwidth[0][0],
        'r_square': metrics.r2_score(y_pts, kernel_values),
        'kernel_stats': list(kernel_values),
    }


def kernel_ridge(x_pts, y_pts, config):
    """
    TODO: Write documentation of `kernel_ridge()`

    :param list x_pts: the list of x points coordinates
    :param list y_pts: the list of y points coordinates
    :param dict config: the perun and option context with needed parameters
    :return dict: the output dictionary with result of kernel regression
    """
    x_pts = np.asanyarray(x_pts, dtype=np.float_).reshape(-1, 1)
    y_pts = np.asanyarray(y_pts, dtype=np.float_)

    low_boundary = config['gamma_range'][0]
    high_boundary = config['gamma_range'][1]
    kernel_estimate = KernelRidge(kernel='rbf', gamma=np.arange(low_boundary, high_boundary, config['gamma_step']))
    kernel_values = kernel_estimate.fit(x_pts, y_pts).predict(x_pts)

    return {
        "bandwidth": kernel_estimate.gamma,
        'r_square': kernel_estimate.score(x_pts, y_pts),
        'kernel_stats': list(kernel_values),
    }


def execute_kernel_regression(x_pts, y_pts, config):
    """
    TODO: Write documentation of `kernel_regression()`

    :param list x_pts: the list of x points coordinates
    :param list y_pts: the list of y points coordinates
    :param dict config: the perun and option context with needed parameters
    :return dict: the output dictionary with result of kernel regression
    """
    # Sort the points to the right order for computation
    x_pts, y_pts = zip(*sorted(zip(x_pts, y_pts)))

    kernel_model = {
        'x_interval_start': min(x_pts),
        'x_interval_end': max(x_pts),
        'per_key': config['per_key'],
    }

    if config['kernel_mode'] in ('estimator-settings', 'method-selection', 'user-selection'):
        kernel_model.update(kernel_regression(x_pts, y_pts, config))
    elif config['kernel_mode'] == 'kernel-smoothing':
        kernel_model.update(kernel_smoothing(x_pts, y_pts, config))
    elif config['kernel_mode'] == 'kernel-ridge':
        kernel_model.update(kernel_ridge(x_pts, y_pts, config))

    return kernel_model


def valid_range_values(ctx, param, value):
    """
    TODO: Write documentation of `valid_range_values()`

    :param click.Context ctx: the current perun and option context
    :param click.Option param: additive options from relevant commands decorator
    :param tuple value: the value of the parameter that invoked the callback method (name, value)
    :raises click.BadOptionsUsage: in the case when was not entered the first value lower than the second value
    :return: returns tuple of values (range) if the first value is lower than the second value
    """
    if value[0] < value[1]:
        return value
    else:
        raise click.BadOptionUsage(param.name, 'Invalid values: 1.value must be < then the 2.value (%g >= %g)' %
                                   (value[0], value[1]))


def valid_step_size(step, range_length):
    """
    TODO: Write documentation of `valid_step_size()`

    :param step:
    :param range_length:
    :raises click.BadOptionsUsage:
    :return:
    """
    if step < range_length:
        return True
    else:
        raise click.BadOptionUsage("--gamma-step/g-s", 'Invalid values: step must be < then the length of the range '
                                                       '(%g >= %g)' % (step, range_length))


_MODES_REQUIRED_KEYS = {
    'estimator-settings': ['efficient', 'randomize', 'n_sub', 'n_res', 'return_median', 'reg_type', 'bandwidth_method'],
    'kernel-smoothing': ['kernel_type', 'smoothing_method', 'bandwidth_method', 'bandwidth_value', 'polynomial_order'],
    'kernel-ridge': ['gamma_range', 'gamma_step'],
    'user-selection': ['bandwidth_value', 'reg_type'],
    'method-selection': ['bandwidth_method', 'reg_type'],
    'common_keys': ['per_key', 'of_key'],
}

_KERNEL_TYPES_MAPS = {
    'normal': smooth.kernels.normal_kernel(dim=1),
    'tricube': smooth.kernels.tricube(),
    'epanechnikov': smooth.kernels.Epanechnikov(),
    'epanechnikov4': smooth.kernels.Epanechnikov_order4(),
    'normal4': smooth.kernels.normal_order4(),
}

_SMOOTHING_METHODS_MAPS = {
    'local-polynomial': lambda dim: smooth.npr_methods.LocalPolynomialKernel(q=dim),
    'spatial-average': lambda _: smooth.npr_methods.SpatialAverage(),
    'local-linear': lambda _: smooth.npr_methods.LocalLinearKernel1D(),
}
