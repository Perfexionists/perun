"""
Module implements methods of kernel regression postprocessor.

This module contains the methods that implements the whole set of methods
to execute the kernel regression. Also contains the auxiliary methods to
validate the options and to execute the individual computations.
"""
from __future__ import annotations

# Standard Imports
from typing import Any, TYPE_CHECKING, Callable, Optional, Iterator, cast

# Third-Party Imports
from sklearn import metrics, base as sklearn
import click.exceptions as click_exp
import numpy as np
import sklearn.metrics.pairwise as kernels
import statsmodels.nonparametric.api as nparam

# Perun Imports
from perun.postprocess.regression_analysis import tools
import perun.thirdparty.pyqt_fit_port as pyqt_fit

if TYPE_CHECKING:
    import numpy.typing as npt
    import click


# set numpy variables to ignore warning messages at computation
# - it is only temporary solution for clearly listings
np.seterr(divide="ignore", invalid="ignore")

# Supported helper methods for determines the kernel bandwidth
# - scott: Scott's Rule of Thumb (default method)
# - silverman: Silverman's Rule of Thumb
BW_SELECTION_METHODS = ["scott", "silverman"]

# Minimum points count to perform the regression
_MIN_POINTS_COUNT = 3


class KernelRidge(sklearn.BaseEstimator, sklearn.RegressorMixin):
    """
    This class implements the Nadaraya-Watson kernel approach for
    `kernel-ridge` mode of this kernel regression postprocessor.

    Class to execute the kernel regression with the support of automatic
    kernel bandwidth selection. This automatic selection is performing
    by leave-one-out cross-validation. The specific value of gamma is
    selected from the given range of values entered by the user. The
    selection is based on the minimizing mean-squared error in
    leave-one-out cross-validation.

    :param sklearn.base.BaseEstimator: base class for all estimators in scikit-learn
    :param sklearn.base.RegressorMixin: mixin class for all regression estimators in scikit-learn
    """

    __slots__ = ["x_pts", "y_pts", "kernel", "gamma"]

    def __init__(self, gamma: Optional[npt.NDArray[np.float64] | float] = None) -> None:
        """
        Initialization method for `KernelRidge` class.

        :param np.ndarray/float gamma: parameter for the `rbf` kernel represent kernel bandwidth,
                if the np.ndarray is given, then is executing the selection with minimizing the
                `mse` of leave-one-out cross-validation
        """
        self.x_pts: npt.NDArray[np.float64] = np.array([])
        self.y_pts: npt.NDArray[np.float64] = np.array([])
        # Fixme: This might break everything -^
        self.kernel: str = "rbf"
        self.gamma: Optional[npt.NDArray[np.float64] | float] = gamma

    def fit(self, x_pts: npt.NDArray[np.float64], y_pts: npt.NDArray[np.float64]) -> KernelRidge:
        """
        The method provides the fitting of the model according to the given set of points.
        If the user entered the sequence of gamma values, then one of these values is
        selected by application the minimizing mean-squared-error in leave-one-out
        cross-validation.

        :param list x_pts: the list of x points coordinates
        :param list y_pts: the list of y points coordinates
        :return KernelRidge: return fitted instance of a self-class
        """
        self.x_pts = x_pts
        self.y_pts = y_pts

        # Check whether was given a sequence of the gamma values
        if isinstance(self.gamma, np.ndarray):
            self._optimize_gamma(self.gamma)

        return self

    def predict(self, x_pts: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """
        This method predict target values using the kernel function.

        :param list x_pts: the list of x points coordinates to predict
        :return np.ndarray: array with values of resulting kernel estimates
        """
        kernel = kernels.pairwise_kernels(self.x_pts, x_pts, metric=self.kernel, gamma=self.gamma)
        return (kernel * self.y_pts[:, None]).sum(axis=0) / kernel.sum(axis=0)

    def _optimize_gamma(self, gamma_values: npt.NDArray[np.float64]) -> float:
        """
        This method select a specific value from a given range of values.

        Selection of the specific `gamma` value from the given range of
        values is executing by minimizing the mean-squared-error in leave-
        one-out cross-validation. More details about this selection method
        are available in the Perun documentation.

        :param np.ndarray gamma_values: range of gamma values to select one of them
        :return float: selected specific value of gamma from a given range of values
        """
        mse = np.empty_like(gamma_values, dtype=float)
        for i, gamma in enumerate(gamma_values):
            kernel = kernels.pairwise_kernels(self.x_pts, self.x_pts, self.kernel, gamma=gamma)
            np.fill_diagonal(kernel, 0)
            err = (kernel * self.y_pts[:, np.newaxis]).sum(axis=0) / kernel.sum(axis=0) - self.y_pts
            mse[i] = (err**2).mean()

        self.gamma = float(gamma_values[np.nanargmin(mse) if not np.isnan(mse).all() else 0])
        return self.gamma


def compute_kernel_regression(
    data_gen: Iterator[tuple[list[float], list[float], str]], config: dict[str, Any]
) -> list[dict[str, Any]]:
    """
    This method represents the wrapper for all modes of kernel regression postprocessor.

    Method execute the validation of entered options and subsequently ensures the executing
    the kernel analysis by relevant mode. After the returning from the analysis methods
    add to obtained model relevant `uid` of current resources and the name of the analysis.
    After the analyzing whole profile returns the dictionary with created kernel models.

    :param iter data_gen: the generator object with collected data (data provider generator)
    :param dict config: the perun and option context contains the entered options and commands
    :return list of dict: the computed kernel models according to selected specification
    """
    # checking the presence of specific keys according to selected modes of kernel regression
    tools.validate_dictionary_keys(
        config,
        _MODES_REQUIRED_KEYS[config["kernel_mode"]] + _MODES_REQUIRED_KEYS["common_keys"],
        [],
    )

    # list of resulting models computed by kernel analysis
    kernel_models = []
    for x_pts, y_pts, uid in data_gen:
        # calling the method, that ensures the calling the relevant mode of kernel regression
        kernel_model = execute_kernel_regression(x_pts, y_pts, config)
        kernel_model["uid"] = uid
        kernel_model["model"] = "kernel_regression"
        # add partial result to the model result list - create output dictionary with kernel models
        kernel_models.append(kernel_model)
    return kernel_models


def kernel_regression(
    x_pts: list[float], y_pts: list[float], config: dict[str, Any]
) -> dict[str, Any]:
    """
    This method executing the computation of three modes of kernel regression
    postprocessor: `estimator-settings`, `method-selection` and `user selection`.

    Method computing the kernel regression using the `stastmodels` non-parametric
    kernel regression class: statsmodels.nonparametric.kernel_regression.KernelReg

    The method according to the selected mode by the user performs the relevant required
    actions. In the first step, a method performs the selection of kernel bandwidth if it
    is required by mode. Subsequently, a method ensures the setting of all parameter of
    `EstimatorSettings` object, if was selected necessary mode. After the execution of
    the computation are setting the parameters in the resulting dictionary, that will
    be return.

    :param list x_pts: the list of x points coordinates
    :param list y_pts: the list of y points coordinates
    :param dict config: the perun and option context contains the entered options and commands
    :return dict: the output dictionary with result of kernel regression
    """
    estimator_settings_flag = config["kernel_mode"] == "estimator-settings"
    if estimator_settings_flag:
        # Set the method to determine kernel bandwidth with EstimatorSettings
        # - Possible values `bw` in this branch are: `cv_ls`, `aic`
        bw_value = config.get("bandwidth_method")
    else:
        # If was entered the bandwidth value by user, then will be set as `bw` value
        # - If was entered the bandwidth method to determination, then will be computing
        # -- Possible values of bandwidth method in this branch are: `scott`, `silverman`
        bw_value = config.get(
            "bandwidth_value",
            nparam.bandwidths.select_bandwidth(
                x_pts, config.get("method_name", BW_SELECTION_METHODS[0]), kernel=None
            ),
        )

    # Set specify settings for estimator object, if was selected the mode: `estimator-settings`
    # - When was not selected `estimator-settings` mode, then this object is not used at analysis
    estimator_settings = nparam.EstimatorSettings(
        n_res=config.get("n_re_samples"),
        efficient=config.get("efficient"),
        randomize=config.get("randomize"),
        n_sub=config.get("n_sub_samples"),
        return_median=config.get("return_median"),
    )

    # Set parameters for non-parametric kernel regression class
    kernel_estimate = nparam.KernelReg(
        endog=[y_pts],
        exog=[x_pts],
        reg_type=config["reg_type"],
        var_type="c",
        bw=bw_value if estimator_settings_flag else np.array(bw_value).reshape((1, -1)),
        defaults=estimator_settings,
    )
    # Returns the mean and marginal effects at the data_predict points
    kernel_stats, _ = kernel_estimate.fit()

    # Set parameter for resulting kernel model
    return {
        "bandwidth": bw_value if not estimator_settings_flag else kernel_estimate.bw[0],
        "r_square": kernel_estimate.r_squared(),
        "bucket_stats": list(kernel_stats),
        "kernel_mode": "estimator",
    }


def iterative_computation(
    x_pts: npt.NDArray[np.float64],
    y_pts: npt.NDArray[np.float64],
    kernel_estimate: Any,
    **kwargs: Any,
) -> Any:
    """
    The method represents the wrapper over the kernel-smoothing estimator.

    When the kernel bandwidth is inappropriately chosen, the kernel estimate cannot
    be fitted to original data. This method ensures increasing the kernel bandwidth
    until it is not appropriate for the resulting kernel estimate. The resulting
    accuracy of kernel estimate is not affected by this increase.

    :param list x_pts: the list of x points coordinates
    :param list y_pts: the list of y points coordinates
    :param pyqt_fit.NonParamRegression kernel_estimate: class performing kernel-based
                non-parametric regression
    :param kwargs: key args contain another required parameters: `kernel` and `model`
    :return pyqt_fit.NonParamRegression: returns the kernel estimate with optimized bandwidth
    """
    kernel_values = None
    # Repeat the computation of kernel estimate until the fitting is not successful.
    while kernel_values is None:
        try:  # Try fitting the current kernel estimate on the original data (x-coordinates)
            kernel_values = kernel_estimate(x_pts)
        # Inappropriate bandwidth cause LinAlgError (`Matrix is singular`)
        except np.linalg.LinAlgError:
            # Compute the new kernel estimate with increased bandwidth value
            kernel_estimate = pyqt_fit.NonParamRegression(
                x_pts,
                y_pts,
                bandwidth=kernel_estimate.bandwidth[0][0] + 1,
                kernel=kwargs.get("kernel"),
                method=kwargs.get("method"),
            )
    return kernel_estimate


def kernel_smoothing(
    in_x_pts: list[float], in_y_pts: list[float], config: dict[str, Any]
) -> dict[str, Any]:
    """
    This method executing the computation of `kernel-smoothing` mode.

    Method computing the kernel regression using the `PyQt-Fit` non-parametric
    kernel regression class: pyqt_fit.nonparam_regression.NonParamRegression

    After the adaption coordinates list to the required type array are obtained the
    relevant instances of kernel and regression method according to the selected options
    by the user. When a user was not entering the bandwidth value but selected the bandwidth
    method for determination, then will be calling the relevant method to compute. In the
    last steps of this analysis is fitted the estimated data a returns the obtained kernel
    models.

    :param list in_x_pts: the list of x points coordinates
    :param list in_y_pts: the list of y points coordinates
    :param dict config: the perun and option context contains the entered options and commands
    :return dict: the output dictionary with result of kernel regression
    """
    # Retype the coordinated list for requirements of computational class
    x_pts = np.asanyarray(in_x_pts, dtype=np.float_)
    y_pts = np.asanyarray(in_y_pts, dtype=np.float_)

    # Obtaining the kernel instance from supported types according to the given name
    kernel = _KERNEL_TYPES_MAPS[config["kernel_type"]]
    # Obtaining the method instance from supported regression methods according to the given name
    method = _SMOOTHING_METHODS_MAPS[config["smoothing_method"]](config["polynomial_order"])

    # User entered the bandwidth value directly
    if config["bandwidth_value"]:
        # Perform the non-parametric kernel regression with user-selected kernel bandwidth
        kernel_estimate = pyqt_fit.NonParamRegression(
            x_pts,
            y_pts,
            bandwidth=config["bandwidth_value"],
            kernel=kernel,
            method=method,
        )
    else:  # User entered the method for bandwidth selection or did not choose any option
        # Compute the optimal kernel bandwidth according to selected method
        if config["bandwidth_method"] == "scott":
            covariance = pyqt_fit.scotts_covariance(x_pts)
        else:
            covariance = pyqt_fit.silverman_covariance(x_pts)
        # Perform the non-parametric kernel regression with method-computed kernel bandwidth
        kernel_estimate = pyqt_fit.NonParamRegression(
            x_pts, y_pts, method=method, kernel=kernel, covariance=covariance
        )

    # Call the method to fit the parameters of the fitting
    kernel_estimate.fit()
    # Ensuring the achievement of the desired outcome
    kernel_estimate = iterative_computation(
        x_pts, y_pts, kernel_estimate, method=method, kernel=kernel
    )

    # Set parameter for resulting kernel model
    return {
        "bandwidth": kernel_estimate.bandwidth[0][0],
        "r_square": metrics.r2_score(y_pts, kernel_estimate(x_pts)),
        "bucket_stats": list(kernel_estimate(x_pts)),
        "kernel_mode": "smoothing",
    }


def kernel_ridge(
    in_x_pts: list[float], in_y_pts: list[float], config: dict[str, Any]
) -> dict[str, Any]:
    """
    This method executing the computation of `kernel-ridge` mode.

    Method computing the kernel regression using the `Scikit-Learn` non-parametric
    kernel regression class: sklearn.kernel_ridge.KernelRidge

    This method implements the Nadaraya-Watson kernel regression with automatic
    bandwidth selection of the kernel via leave-one-out cross-validation from
    given range of values. This kernel regression is implemented using the
    `Kernel Regressor` class from `sklearn` package. For more details about
    this approach you can see class `KernelRidge` or Perun Documentation.

    :param list in_x_pts: the list of x points coordinates
    :param list in_y_pts: the list of y points coordinates
    :param dict config: the perun and option context contains the entered options and commands
    :return dict: the output dictionary with result of kernel regression
    """
    # Retype the coordinated list for requirements of computational class
    x_pts = np.asanyarray(in_x_pts, dtype=np.float_).reshape(-1, 1)
    y_pts = np.asanyarray(in_y_pts, dtype=np.float_)

    # Obtaining the edges of the given range
    low_boundary = config["gamma_range"][0]
    high_boundary = config["gamma_range"][1]
    # Executing the kernel regression with automatic bandwidth selection
    kernel_estimate = KernelRidge(
        gamma=np.arange(low_boundary, high_boundary, config["gamma_step"])
    )
    # Fitting the obtained kernel estimate to the original data (x-coordinates)
    kernel_values = kernel_estimate.fit(x_pts, y_pts).predict(x_pts)

    # Set parameter for resulting kernel model
    return {
        "bandwidth": kernel_estimate.gamma,
        "r_square": kernel_estimate.score(x_pts, y_pts),
        "bucket_stats": list(kernel_values),
        "kernel_mode": "ridge",
    }


def execute_kernel_regression(
    x_pts: list[float], y_pts: list[float], config: dict[str, Any]
) -> dict[str, Any]:
    """
    This method serves to call the individual computing methods of a kernel regression.

    At the beginning method ensures sorting of points (x and y coordinates) and creates
    the initial resulting dictionary with common items for all kernel regression modes.
    In the case when both lists of coordinates contain more resources than one,
    then is calling the relevant method, that ensures the computing according to
    the selected mode. If the list of coordinates contains only one resources then
    no calculation is made.

    :param list x_pts: the list of x points coordinates
    :param list y_pts: the list of y points coordinates
    :param dict config: the perun and option context contains the entered options and commands
    :return dict: the output dictionary with result of kernel regression
    """
    # Sort the points to the right order for computation
    x_pts, y_pts = cast(tuple[list[float], list[float]], zip(*sorted(zip(x_pts, y_pts))))

    # Create the initial dictionary, that contains the common items for all modes
    kernel_model = {
        "x_start": min(x_pts),
        "x_end": max(x_pts),
        "per_key": config["per_key"],
    }

    # If the list of coordinates contain only one resource, then the computation will be not executing
    # - It is protection before the failure of the method to determine tha optimal kernel bandwidth
    # -- It is useless executing the kernel regression over the one pair of points
    if len(x_pts) < _MIN_POINTS_COUNT and len(y_pts) < _MIN_POINTS_COUNT:
        kernel_model.update(
            {
                "bandwidth": 1,
                "r_square": 1,
                "bucket_stats": y_pts,
                "kernel_mode": "manually",
            }
        )
    elif config["kernel_mode"] in (
        "estimator-settings",
        "method-selection",
        "user-selection",
    ):
        kernel_model.update(kernel_regression(x_pts, y_pts, config))
    elif config["kernel_mode"] == "kernel-smoothing":
        kernel_model.update(kernel_smoothing(x_pts, y_pts, config))
    elif config["kernel_mode"] == "kernel-ridge":
        kernel_model.update(kernel_ridge(x_pts, y_pts, config))

    return kernel_model


def valid_range_values(
    _: click.Context, param: click.Option, value: tuple[float, float]
) -> tuple[float, float]:
    """
    This method represents click callback option method.

    Callback method check whether the given interval is valid. Values
    must be in logical order, that is, the first value is smaller than
    the second value.

    :param click.Context _: the perun and option context contains the entered options and commands
    :param click.Option param: additive options from relevant commands decorator
    :param tuple value: the value of the parameter that invoked the callback method (name, value)
    :raises click.BadOptionsUsage: in the case when was not entered the first value smaller than
                the second value
    :return tuple(double, double): returns values (range) if the first value is lower than
                the second value
    """
    if value[0] < value[1]:
        return value
    else:
        raise click_exp.BadOptionUsage(
            param.name or "",
            (
                f"Invalid values: 1.value must be < then the 2.value ({value[0]:.2f} >="
                f" {value[1]:.2f})"
            ),
        )


def valid_step_size(step: float, step_range: tuple[float, float]) -> bool:
    """
    This method represents click callback option method.

    Callback method check whether the value of given step is valid. It
    means that a step value must be smaller than the length of the
    given range.

    :param step: value of the entered step to move around the gamma range
    :param step_range: tuple of length of the entered gamma range
    :raises click.BadOptionsUsage: in the case when the step is not smaller than the length of
                the given range
    :return bool: return True if the control was successful
    """
    range_length = step_range[1] - step_range[0]
    if step < range_length:
        return True
    else:
        raise click_exp.BadOptionUsage(
            "--gamma-step/-gs",
            (
                "Invalid values: step must be < then the length of the range "
                f"({step:.5f} >= {range_length:.5f}) for range {step_range[0]}:{step_range[1]}"
            ),
        )


# dictionary contains the required keys to check before the access to these keys
# - required keys are divided according to individual supported modes of this postprocessor
_MODES_REQUIRED_KEYS = {
    "estimator-settings": [
        "efficient",
        "randomize",
        "n_sub_samples",
        "n_re_samples",
        "return_median",
        "reg_type",
        "bandwidth_method",
    ],
    "kernel-smoothing": [
        "kernel_type",
        "smoothing_method",
        "bandwidth_method",
        "bandwidth_value",
        "polynomial_order",
    ],
    "kernel-ridge": ["gamma_range", "gamma_step"],
    "user-selection": ["bandwidth_value", "reg_type"],
    "method-selection": ["bandwidth_method", "reg_type"],
    "common_keys": ["per_key", "of_key"],
}

# dict contains the supported kernel types for `kernel-smoothing` mode, respectively its instances
# - more information about individual types of kernel are described in Perun documentation
_KERNEL_TYPES_MAPS: dict[str, object] = {
    "normal": pyqt_fit.NormalKernel(dim=1),
    "tricube": pyqt_fit.Tricube(),
    "epanechnikov": pyqt_fit.Epanechnikov(),
    "epanechnikov4": pyqt_fit.EpanechnikovOrder4(),
    "normal4": pyqt_fit.NormalOrder4(),
}

# dict contains the regression methods for `kernel-smoothing` mode, respectively their instances
# - using lambda expressions are used due to unification at calling this dictionary
# -- more information about individual types of kernel are described in Perun documentation
_SMOOTHING_METHODS_MAPS: dict[str, Callable[[int], object]] = {
    "local-polynomial": lambda dim: pyqt_fit.LocalPolynomialKernel(q=dim),
    "spatial-average": lambda _: pyqt_fit.SpatialAverage(),
    "local-linear": lambda _: pyqt_fit.LocalLinearKernel1D(),
}
