r"""
:Author: Pierre Barbier de Reuille <pierre.barbierdereuille@gmail.com>

Module implementing kernel-based estimation of density of probability.

Given a kernel :math:`K`, the density function is estimated from a sampling
:math:`X = \{X_i \in \mathbb{R}^n\}_{i\in\{1,\ldots,m\}}` as:

.. math::

    f(\mathbf{z}) \triangleq \frac{1}{hW} \sum_{i=1}^m \frac{w_i}{\lambda_i}
    K\left(\frac{X_i-\mathbf{z}}{h\lambda_i}\right)

    W = \sum_{i=1}^m w_i

where :math:`h` is the bandwidth of the kernel, :math:`w_i` are the weights of
the data points and :math:`\lambda_i` are the adaptation factor of the kernel
width.

The kernel is a function of :math:`\mathbb{R}^n` such that:

.. math::

    \begin{array}{rclcl}
       \idotsint_{\mathbb{R}^n} f(\mathbf{z}) d\mathbf{z}
       & = & 1 & \Longleftrightarrow & \text{$f$ is a probability}\\
       \idotsint_{\mathbb{R}^n} \mathbf{z}f(\mathbf{z}) d\mathbf{z} &=&
       \mathbf{0} & \Longleftrightarrow & \text{$f$ is
       centered}\\
       \forall \mathbf{u}\in\mathbb{R}^n, \|\mathbf{u}\|
       = 1\qquad\int_{\mathbb{R}} t^2f(t \mathbf{u}) dt &\approx&
       1 & \Longleftrightarrow & \text{The co-variance matrix of $f$ is close
       to be the identity.}
    \end{array}

The constraint on the covariance is only required to provide a uniform meaning
for the bandwidth of the kernel.

If the domain of the density estimation is bounded to the interval
:math:`[L,U]`, the density is then estimated with:

.. math::

    f(x) \triangleq \frac{1}{hW} \sum_{i=1}^n \frac{w_i}{\lambda_i}
    \hat{K}(x;X,\lambda_i h,L,U)

where :math:`\hat{K}` is a modified kernel that depends on the exact method
used. Currently, only 1D KDE supports bounded domains.
"""
import numpy as np

from perun.thirdparty.pyqt_fit_port.kernels import NormalKernel1d
from perun.thirdparty.pyqt_fit_port import kde_methods
from perun.thirdparty.pyqt_fit_port.kde_bandwidth import scotts_covariance
from perun.thirdparty.pyqt_fit_port.utils import numpy_method_idx


class KDE1D:
    """Perform a kernel based density estimation in 1D.

    Perform a kernel based density estimation in 1D, possibly on a bounded domain :math:`[L,U]`.
    """

    def __init__(self, xdata, **kwargs):
        """Initializer

            :param ndarray data: 1D array with the data points
            :param dict kwords: setting attributes at construction time.
            Any named argument will be equivalent to setting the property
            after the fact. For example::

                >>> xs = [1,2,3]
                >>> k = KDE1D(xs, lower=0)

            will be equivalent to::

                >>> k = KDE1D(xs)
                >>> k.lower = 0

        The calculation is separated in three parts:

            - The kernel (:py:attr:`kernel`)
            - The bandwidth or covariance estimation (:py:attr:`bandwidth`,
              :py:attr:`covariance`)
            - The estimation method (:py:attr:`method`)

        """
        self._xdata = None
        self._upper = np.inf
        self._lower = -np.inf
        self._kernel = NormalKernel1d()

        self._bw_fct = None
        self._bw = None
        self._cov_fct = None
        self._covariance = None
        self._method = None

        self.weights = 1.0
        self.lambdas = 1.0

        self._fitted = False

        for key, value in kwargs.items():
            setattr(self, key, value)

        self.xdata = xdata

        has_bw = (
            self._bw is not None
            or self._bw_fct is not None
            or self._covariance is not None
            or self._cov_fct is not None
        )
        if not has_bw:
            self.covariance = scotts_covariance

        if self._method is None:
            self.method = kde_methods.default_method

    @property
    def fitted(self):
        """
        Test if the fitting has been done
        """
        return self._fitted

    def fit_if_needed(self):
        """
        Fit only if needed (testing self.fitted)
        """
        if not self._fitted:
            self.fit()

    def need_fit(self):
        """
        Calling this function will mark the object as needing fitting.
        """
        self._fitter = False

    def copy(self):
        """
        Shallow copy of the KDE object
        """
        res = KDE1D.__new__(KDE1D)
        # Copy private members: start with a single '_'
        for m in self.__dict__:
            if len(m) > 1 and m[0] == "_" and m[1] != "_":
                setattr(res, m, getattr(self, m))
        return res

    def compute_bandwidth(self):
        """
        Method computing the bandwidth if needed (i.e. if it was defined by functions)
        """
        self._bw, self._covariance = kde_methods.compute_bandwidth(self)

    def fit(self):
        """
        Compute the various parameters needed by the kde method
        """
        if self._weights.shape:
            assert (
                self._weights.shape == self._xdata.shape
            ), "There must be as many weights as data points"
            self._total_weights = sum(self._weights)
        else:
            self._total_weights = len(self._xdata)
        self.method.fit(self)
        self._fitted = True

    @property
    def xdata(self):
        return self._xdata

    @xdata.setter
    def xdata(self, xs):
        self.need_fit()
        self._xdata = np.atleast_1d(xs)
        assert len(self._xdata.shape) == 1, "The attribute xdata must be a one-dimension array"

    @property
    def kernel(self):
        r"""
        Kernel object. This must be an object modeled on
        :py:class:`pyqt_fit.kernels.Kernel1D`. It is recommended to inherit
        this class to provide numerical approximation for all methods.

        By default, the kernel is an instance of
        :py:class:`pyqt_fit.kernels.normal_kernel1d`
        """
        return self._kernel

    @kernel.setter
    def kernel(self, val):
        self.need_fit()
        self._kernel = val

    @property
    def lower(self):
        r"""
        Lower bound of the density domain. If deleted, becomes set to
        :math:`-\infty`
        """
        return self._lower

    @lower.setter
    def lower(self, val):
        self.need_fit()
        self._lower = float(val)

    @lower.deleter
    def lower(self):
        self.need_fit()
        self._lower = -np.inf

    @property
    def upper(self):
        r"""
        Upper bound of the density domain. If deleted, becomes set to
        :math:`\infty`
        """
        return self._upper

    @upper.setter
    def upper(self, val):
        self.need_fit()
        self._upper = float(val)

    @upper.deleter
    def upper(self):
        self.need_fit()
        self._upper = np.inf

    @property
    def weights(self):
        """
        Weigths associated to each data point. It can be either a single value,
        or an array with a value per data point. If a single value is provided,
        the weights will always be set to 1.
        """
        return self._weights

    @weights.setter
    def weights(self, ws):
        self.need_fit()
        try:
            ws = float(ws)
            self._weights = np.asarray(1.0)
        except TypeError:
            ws = np.array(ws, dtype=float)
            self._weights = ws
        self._total_weights = None

    @weights.deleter
    def weights(self):
        self.need_fit()
        self._weights = np.asarray(1.0)
        self._total_weights = None

    @property
    def total_weights(self):
        return self._total_weights

    @property
    def lambdas(self):
        """
        Scaling of the bandwidth, per data point. It can be either a single
        value or an array with one value per data point.

        When deleted, the lamndas are reset to 1.
        """
        return self._lambdas

    @lambdas.setter
    def lambdas(self, ls):
        self.need_fit()
        try:
            self._lambdas = np.asarray(float(ls))
        except TypeError:
            ls = np.array(ls, dtype=float)
            self._lambdas = ls

    @lambdas.deleter
    def lambdas(self):
        self.need_fit()
        self._lambdas = np.asarray(1.0)

    @property
    def bandwidth(self):
        """
        Bandwidth of the kernel.
        Can be set either as a fixed value or using a bandwidth calculator,
        that is a function of signature ``w(xdata)`` that returns a single
        value.

        .. note::

            A ndarray with a single value will be converted to a floating point
            value.
        """
        return self._bw

    @bandwidth.setter
    def bandwidth(self, bw):
        self.need_fit()
        self._bw_fct = None
        self._cov_fct = None
        if callable(bw):
            self._bw_fct = bw
        else:
            bw = float(bw)
            self._bw = bw
            self._covariance = bw * bw

    @property
    def bandwidth_function(self):
        return self._bw_fct

    @property
    def covariance(self):
        """
        Covariance of the gaussian kernel.
        Can be set either as a fixed value or using a bandwidth calculator,
        that is a function of signature ``w(xdata)`` that returns a single
        value.

        .. note::

            A ndarray with a single value will be converted to a floating point
            value.
        """
        return self._covariance

    @covariance.setter
    def covariance(self, cov):
        self.need_fit()
        self._bw_fct = None
        self._cov_fct = None
        if callable(cov):
            self._cov_fct = cov
        else:
            cov = float(cov)
            self._covariance = cov
            self._bw = np.sqrt(cov)

    @property
    def covariance_function(self):
        return self._cov_fct

    @numpy_method_idx
    def pdf(self, points, out=None):
        """
        Compute the PDF of the distribution on the set of points ``points``
        """
        self.fit_if_needed()
        return self._method.pdf(self, points, out)

    def evaluate(self, points, out=None):
        """
        Compute the PDF of the distribution on the set of points ``points``
        """
        return self.pdf(points, out)

    def __call__(self, points, out=None):
        """
        This method is an alias for :py:meth:`BoundedKDE1D.evaluate`
        """
        return self.pdf(points, out=out)

    @numpy_method_idx
    def cdf(self, points, out=None):
        r"""
        Compute the cumulative distribution function defined as:

        .. math::

            cdf(x) = P(X \leq x) = \int_l^x p(t) dt

        where :math:`l` is the lower bound of the distribution domain and
        :math:`p` the density of probability.
        """
        self.fit_if_needed()
        return self.method.cdf(self, points, out)

    def cdf_grid(self, n=None, cut=None):
        """
        Compute the cdf from the lower bound to the points given as argument.
        """
        self.fit_if_needed()
        return self.method.cdf_grid(self, n, cut)

    @numpy_method_idx
    def icdf(self, points, out=None):
        r"""
        Compute the inverse cumulative distribution (quantile) function.
        """
        self.fit_if_needed()
        return self.method.icdf(self, points, out)

    def icdf_grid(self, n=None, cut=None):
        """
        Compute the inverse cumulative distribution (quantile) function on a grid.
        """
        self.fit_if_needed()
        return self.method.icdf_grid(self, n, cut)

    @numpy_method_idx
    def sf(self, points, out=None):
        r"""
        Compute the survival function.

        The survival function is defined as:

        .. math::

            sf(x) = P(X \geq x) = \int_x^u p(t) dt = 1 - cdf(x)

        where :math:`u` is the upper bound of the distribution domain and
        :math:`p` the density of probability.

        """
        self.fit_if_needed()
        return self.method.sf(self, points, out)

    def sf_grid(self, n=None, cut=None):
        r"""
        Compute the survival function on a grid
        """
        self.fit_if_needed()
        return self.method.sf_grid(self, n, cut)

    @numpy_method_idx
    def isf(self, points, out=None):
        r"""
        Compute the inverse survival function, defined as:

        .. math::

            isf(p) = \sup\left\{x\in\mathbb{R} : sf(x) \leq p\right\}
        """
        self.fit_if_needed()
        return self.method.isf(self, points, out)

    def isf_grid(self, n=None, cut=None):
        r"""
        Compute the inverse survival function on a grid.
        """
        self.fit_if_needed()
        return self.method.isf_grid(self, n, cut)

    @numpy_method_idx
    def hazard(self, points, out=None):
        r"""
        Compute the hazard function evaluated on the points.

        The hazard function is defined as:

        .. math::

            h(x) = \frac{p(x)}{sf(x)}
        """
        self.fit_if_needed()
        return self.method.hazard(self, points, out)

    def hazard_grid(self, n=None, cut=None):
        """
        Compute the hazard function evaluated on a grid.
        """
        self.fit_if_needed()
        return self.method.hazard_grid(self, n, cut)

    @numpy_method_idx
    def cumhazard(self, points, out=None):
        r"""
        Compute the cumulative hazard function evaluated on the points.

        The cumulative hazard function is defined as:

        .. math::

            ch(x) = \int_l^x h(t) dt = -\ln sf(x)

        where :math:`l` is the lower bound of the domain, :math:`h` the hazard
        function and :math:`sf` the survival function.
        """
        self.fit_if_needed()
        return self.method.cumhazard(self, points, out)

    def cumhazard_grid(self, n=None, cut=None):
        """
        Compute the cumulative hazard function evaluated on a grid.
        """
        self.fit_if_needed()
        return self.method.cumhazard_grid(self, n, cut)

    @property
    def method(self):
        """
        Select the method to use. The method should be an object modeled on
        :py:class:`pyqt_fit.kde_methods.KDE1DMethod`, and it is recommended to
        inherit the model.

        Available methods in the :py:mod:`pyqt_fit.kde_methods` sub-module.

        :Default: :py:data:`pyqt_fit.kde_methods.default_method`
        """
        return self._method

    @method.setter
    def method(self, m):
        self.need_fit()
        self._method = m

    @method.deleter
    def method(self):
        self.need_fit()
        self._method = kde_methods.renormalization

    @property
    def closed(self):
        """
        Returns true if the density domain is closed (i.e. lower and upper
        are both finite)
        """
        return self.lower > -np.inf and self.upper < np.inf

    @property
    def bounded(self):
        """
        Returns true if the density domain is actually bounded
        """
        return self.lower > -np.inf or self.upper < np.inf

    def grid(self, n=None, cut=None):
        """
        Evaluate the density on a grid of N points spanning the whole dataset.

        :returns: a tuple with the mesh on which the density is evaluated and
            the density itself
        """
        self.fit_if_needed()
        return self._method.grid(self, n, cut)
