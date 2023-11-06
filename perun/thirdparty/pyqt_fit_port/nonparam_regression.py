import numpy as np
from scipy import linalg

from perun.thirdparty.pyqt_fit_port import npr_methods, kernels, kde_bandwidth


class NonParamRegression:
    r"""
    Class performing kernel-based non-parametric regression.

    The calculation is split in three parts:

        - The kernel (:py:attr:`kernel`)
        - Bandwidth computation (:py:attr:`bandwidth`, :py:attr:`covariance`)
        - Regression method (:py:attr:`method`)
    """

    def __init__(self, xdata, ydata, **kwargs):
        self._xdata = np.atleast_2d(xdata)
        self._ydata = np.atleast_1d(ydata)
        self._covariance = None
        self._cov_fct = None
        self._bandwidth = None
        self._bw_fct = None
        self._method = None
        self._kernel = None
        self._lower = None
        self._upper = None
        self._kernel_type = None
        self._fitted_method = None
        self._n = None
        self._d = None
        self._ytrans = None
        self._fitted_ydata = None

        for key, value in kwargs.items():
            setattr(self, key, value)

        if self._kernel is None:
            self.kernel_type = kernels.NormalKernel

        if self._method is None:
            self.method = npr_methods.default_method

        if (
            self._cov_fct is None
            and self._bw_fct is None
            and self._covariance is None
            and self._bandwidth is None
        ):
            self._cov_fct = kde_bandwidth.scotts_covariance

    def copy(self):
        res = NonParamRegression.__new__(NonParamRegression)
        # Copy private members: start with a single '_'
        for m in self.__dict__:
            if len(m) > 1 and m[0] == "_" and m[1] != "_":
                obj = getattr(self, m)
                try:
                    setattr(res, m, obj.copy())
                except AttributeError:
                    setattr(res, m, obj)
        return res

    def need_fit(self):
        """
        Calling this function will mark the object as needing fitting.
        """
        self._fitted_method = None

    @property
    def fitted(self):
        """
        Check if the fitting needs to be performed.
        """
        return self._fitted_method is not None

    @property
    def kernel(self):
        r"""
        Kernel object. Should provide the following methods:

        ``kernel.pdf(xs)``
            Density of the kernel, denoted :math:`K(x)`
        """
        return self._kernel

    @kernel.setter
    def kernel(self, k):
        self._kernel_type = None
        self._kernel = k
        self.need_fit()

    @property
    def kernel_type(self):
        """
        Type of the kernel. The kernel type is a class or function accepting
        the dimension of the domain as argument and returning a valid kernel object.
        """
        return self._kernel_type

    @kernel_type.setter
    def kernel_type(self, ker):
        self._kernel_type = ker
        self._kernel = None
        self.need_fit()

    @property
    def bandwidth(self):
        r"""
        Bandwidth of the kernel.

        This is defined as the square root of the covariance matrix
        """
        return self._bandwidth

    @bandwidth.setter
    def bandwidth(self, bw):
        self._bw_fct = None
        self._cov_fct = None
        if callable(bw):
            self._bw_fct = bw
        else:
            self._bandwidth = np.atleast_2d(bw)
            self._covariance = np.dot(self._bandwidth, self._bandwidth)
        self.need_fit()

    @property
    def bandwidth_function(self):
        return self._bw_fct

    @property
    def covariance(self):
        r"""
        Covariance matrix of the kernel.

        It must be of the right dimension!
        """
        return self._covariance

    @covariance.setter
    def covariance(self, cov):
        self._bw_fct = None
        self._cov_fct = None
        if callable(cov):
            self._cov_fct = cov
        else:
            self._covariance = np.atleast_2d(cov)
            self._bandwidth = linalg.sqrtm(self._covariance)
        self.need_fit()

    @property
    def covariance_function(self):
        return self._cov_fct

    @property
    def lower(self):
        """
        Lower bound of the domain for each dimension
        """
        if self._lower is None:
            return -np.inf * np.ones(self.dim, dtype=float)
        return self._lower

    @lower.setter
    def lower(self, l):
        l = np.atleast_1d(l)
        assert len(l.shape) == 1, "The lower bound must be at most a 1D array"
        self._lower = l
        self.need_fit()

    @lower.deleter
    def lower(self):
        self._lower = None

    @property
    def upper(self):
        """
        Lower bound of the domain for each dimension
        """
        if self._upper is None:
            return np.inf * np.ones(self.dim, dtype=float)
        return self._upper

    @upper.setter
    def upper(self, l):
        l = np.atleast_1d(l)
        assert len(l.shape) == 1, "The upper bound must be at most a 1D array"
        self._upper = l
        self.need_fit()

    @upper.deleter
    def upper(self):
        self._upper = None

    @property
    def xdata(self):
        """
        2D array (D,N) with D the dimension of the domain and N the number of points.
        """
        return self._xdata

    @xdata.setter
    def xdata(self, xd):
        xd = np.atleast_2d(xd)
        assert len(xd.shape) == 2, "The xdata must be at most a 2D array"
        self._xdata = xd
        self.need_fit()

    @property
    def ydata(self):
        """
        1D array (N,) of values for each point in xdata
        """
        return self._ydata

    @ydata.setter
    def ydata(self, yd):
        yd = np.atleast_1d(yd)
        assert len(yd.shape) == 1, "The ydata must be at most a 1D array"
        self._ydata = yd
        self.need_fit()

    @property
    def fitted_ydata(self):
        """
        Data actually fitted. It may differ from ydata if ytrans is specified.
        """
        return self._fitted_ydata

    @property
    def ytrans(self):
        """
        Function used to transform the Y data before fitting.

        This must be a callable that also has a ``inv`` attribute returning the inverse function.

        :Note: The ``inv`` method must accept an ``out`` argument to store the output.
        """
        return self._ytrans

    @ytrans.setter
    def ytrans(self, tr):
        assert hasattr(tr, "__call__") and hasattr(
            tr, "inv"
        ), "The transform must be a callable with an `inv` attribute"
        self._ytrans = tr

    @ytrans.deleter
    def ytrans(self):
        self._ytrans = None

    @property
    def method(self):
        """
        Regression method itself. It should be an instance of the class following the template
        :py:class:`pyqt_fit.npr_methods.RegressionKernelMethod`.
        """
        return self._method

    @method.setter
    def method(self, m):
        self._method = m
        self.need_fit()

    @property
    def fitted_method(self):
        """
        Method actually used after fitting.

        The main method may choose to provide a more tuned method during fitting.
        """
        return self._fitted_method

    @property
    def N(self):
        """
        Number of points in the dataset (set by the fitting)
        """
        return self._n

    @property
    def dim(self):
        """
        Dimension of the domain (set by the fitting)
        """
        return self._d

    def _create_kernel(self, D):
        if self._kernel_type is None:
            return self._kernel
        return self._kernel_type(D)

    def set_actual_bandwidth(self, bandwidth, covariance):
        """
        Method computing the bandwidth if needed (i.e. if it was defined by functions)
        """
        self._bandwidth = bandwidth
        self._covariance = covariance

    def fit(self):
        """
        Method to call to fit the parameters of the fitting
        """
        D, N = self._xdata.shape
        assert self._ydata.shape[0] == N, "There must be as many points for X and Y"
        if self.ytrans is not None:
            self._fitted_ydata = self.ytrans(self.ydata)
        else:
            self._fitted_ydata = self.ydata
        self._kernel = self._create_kernel(D)
        self._n = N
        self._d = D
        lower = self.lower
        upper = self.upper
        assert (
            len(lower) == D
        ), "The 'lower' property must have one value per dimension of the domain."
        assert (
            len(upper) == D
        ), "The 'upper' property must have one value per dimension of the domain."
        self._fitted_method = self._method.fit(self)
        assert self.bandwidth.shape == (
            D,
            D,
        ), f"The bandwidth should have a shape of ({D},{D}) (actual: {self.bandwidth.shape})"
        assert self.covariance.shape == (
            D,
            D,
        ), f"The covariance should have a shape of ({D},{D}) (actual: {self.covariance.shape})"
        self._fitted = True

    def evaluate(self, points, out=None):
        if not self.fitted:
            self.fit()
        points = np.asanyarray(points)
        real_shape = points.shape
        assert len(real_shape) < 3, "The input points can be at most a 2D array"
        if len(real_shape) == 0:
            points = points.reshape(1, 1)
        elif len(real_shape) == 1:
            points = points.reshape(1, real_shape[0])
        if out is None:
            out = np.empty((points.shape[-1],), dtype=type(points.dtype.type() + 0.0))
        else:
            out.shape = (points.shape[-1],)
        self._fitted_method.evaluate(self, points, out)
        out.shape = real_shape[-1:]
        if self.ytrans:
            self.ytrans.inv(out, out=out)
        return out

    def __call__(self, points, out=None):
        return self.evaluate(points, out)
