"""This package is our custom port of the no longer maintained PyQt-fit package.

Original author: Pierre Barbier de Reuille <pierre.barbierdereuille@gmail.com>
Original repository: https://github.com/PierreBdR/PyQt-fit/tree/master

The port removes Cython and Python2 support and fixes various linter warnings.
"""
from perun.thirdparty.pyqt_fit_port.nonparam_regression import NonParamRegression
from perun.thirdparty.pyqt_fit_port.npr_methods import (
    LocalPolynomialKernel,
    SpatialAverage,
    LocalLinearKernel1D,
)
from perun.thirdparty.pyqt_fit_port.kernels import (
    NormalKernel,
    Tricube,
    Epanechnikov,
    EpanechnikovOrder4,
    NormalOrder4,
)
from perun.thirdparty.pyqt_fit_port.kde_bandwidth import (
    scotts_covariance,
    silverman_covariance,
)

__all__ = [
    "NonParamRegression",
    "LocalPolynomialKernel",
    "SpatialAverage",
    "LocalLinearKernel1D",
    "NormalKernel",
    "Tricube",
    "Epanechnikov",
    "EpanechnikovOrder4",
    "NormalOrder4",
    "scotts_covariance",
    "silverman_covariance",
]
