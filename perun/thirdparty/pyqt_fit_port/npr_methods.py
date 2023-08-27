import scipy
import numpy as np

from perun.thirdparty.pyqt_fit_port import kernels, kde


def local_linear_1d(bw, xdata, ydata, points, _, out):
    r"""
    We are trying to find the fitting for points :math:`x` given a gaussian kernel
    Given the following definitions:

    .. math::

        x_0 &=& x-x_i

        \begin{array}{rlc|rlc}
        w_i &=& \mathcal{K}\left(\frac{x_0}{h}\right) & W &=& \sum_i w_i \\
        X &=& \sum_i w_i x_0 & X_2 &=& w_i x_0^2 \\
        Y &=& \sum_i w_i y_i & Y_2 &=& \sum_i w_i y_i x_0
        \end{array}



    The fitted value is given by:

    .. math::

        f(x) = \frac{X_2 T - X Y_2}{W X_2 - X^2}

    """
    x0 = points - xdata[:, np.newaxis]
    x02 = x0 * x0
    # wi = kernel(x0 / bw)
    wi = np.exp(-x02 / (2.0 * bw * bw))
    X = np.sum(wi * x0, axis=0)
    X2 = np.sum(wi * x02, axis=0)
    wy = wi * ydata[:, np.newaxis]
    Y = np.sum(wy, axis=0)
    Y2 = np.sum(wy * x0, axis=0)
    W = np.sum(wi, axis=0)
    return None, np.divide(X2 * Y - Y2 * X, W * X2 - X * X, out)


def compute_bandwidth(reg):
    """
    Compute the bandwidth and covariance for the model, based of its xdata attribute
    """
    if reg.bandwidth_function:
        bw = np.atleast_2d(reg.bandwidth_function(reg.xdata, model=reg))
        cov = np.dot(bw, bw).real
    elif reg.covariance_function:
        cov = np.atleast_2d(reg.covariance_function(reg.xdata, model=reg))
        bw = scipy.linalg.sqrtm(cov)
    else:
        return reg.bandwidth, reg.covariance
    return bw, cov


class RegressionKernelMethod:
    r"""
    Base class for regression kernel methods
    """

    def fit(self, reg):
        """Fit the method and returns the fitted object that will be used for actual evaluation.

        The object needs to call the
        :py:meth:`pyqt_fit.nonparam_regression.NonParamRegression.set_actual_bandwidth` method with
        the computed bandwidth and covariance.

        :Default: Compute the bandwidth based on the real data and set it in the regression object
        """
        reg.set_actual_bandwidth(*compute_bandwidth(reg))
        return self

    def evaluate(self, points, out):
        """
        Evaluate the regression of the provided points.

        :param ndarray points: 2d-array of points to compute the regression on. Each column is
               a point.
        :param ndarray out: 1d-array in which to store the result
        :rtype: ndarray
        :return: The method must return the ``out`` array, updated with the regression values
        """
        raise NotImplementedError()


class SpatialAverage(RegressionKernelMethod):
    r"""
    Perform a Nadaraya-Watson regression on the data (i.e. also called
    local-constant regression) using a gaussian kernel.

    The Nadaraya-Watson estimate is given by:

    .. math::

        f_n(x) \triangleq \frac{\sum_i K\left(\frac{x-X_i}{h}\right) Y_i}
        {\sum_i K\left(\frac{x-X_i}{h}\right)}

    Where :math:`K(x)` is the kernel and must be such that :math:`E(K(x)) = 0`
    and :math:`h` is the bandwidth of the method.

    :param ndarray xdata: Explaining variables (at most 2D array)
    :param ndarray ydata: Explained variables (should be 1D array)

    :type  cov: ndarray or callable
    :param cov: If an ndarray, it should be a 2D array giving the matrix of
        covariance of the gaussian kernel. Otherwise, it should be a function
        ``cov(xdata, ydata)`` returning the covariance matrix.
    """

    def __init__(self):
        self.correction = 1.0

    def fit(self, reg):
        self = super().fit(reg)
        self.inv_bw = scipy.linalg.inv(reg.bandwidth)
        return self

    def evaluate(self, reg, points, out):
        d, m = points.shape
        norm = np.zeros((m,), points.dtype)
        xdata = reg.xdata[..., np.newaxis]
        ydata = reg.fitted_ydata
        correction = self.correction
        N = reg.N
        inv_bw = scipy.linalg.inv(reg.bandwidth)
        kernel = reg.kernel

        out.fill(0)
        # iterate on the internal points
        for i, ci in np.broadcast(range(N), range(correction.shape[0])):
            diff = correction[ci] * (xdata[:, i, :] - points)
            # tdiff = np.dot(inv_cov, diff)
            # energy = np.exp(-np.sum(diff * tdiff, axis=0) / 2.0)
            energy = kernel(np.dot(inv_bw, diff)).squeeze()
            out += ydata[i] * energy
            norm += energy

        out[norm > 0] /= norm[norm > 0]
        return out

    @property
    def correction(self):
        """
        The correction coefficient allows to change the width of the kernel
        depending on the point considered. It can be either a constant (to
        correct globaly the kernel width), or a 1D array of same size as the
        input.
        """
        return self._correction

    @correction.setter
    def correction(self, value):
        value = np.atleast_1d(value)
        assert len(value.shape) == 1, "Error, the correction must be a single value or a 1D array"
        self._correction = value

    def set_density_correction(self):
        """
        Add a correction coefficient depending on the density of the input
        """
        est = kde.KDE1D(self.xdata)
        dens = est(self.xdata)
        dm = dens.max()
        dens[dens < 1e-50] = dm
        self._correction = dm / dens

    @property
    def q(self):
        """
        Degree of the fitted polynom
        """
        return 0


class LocalLinearKernel1D(RegressionKernelMethod):
    r"""
    Perform a local-linear regression using a gaussian kernel.

    The local constant regression is the function that minimises, for each
    position:

    .. math::

        f_n(x) \triangleq \argmin_{a_0\in\mathbb{R}}
            \sum_i K\left(\frac{x-X_i}{h}\right)
            \left(Y_i - a_0 - a_1(x-X_i)\right)^2

    Where :math:`K(x)` is the kernel and must be such that :math:`E(K(x)) = 0`
    and :math:`h` is the bandwidth of the method.
    """

    def fit(self, reg):
        return super().fit(reg)

    def evaluate(self, reg, points, out):
        """
        Evaluate the spatial averaging on a set of points

        :param ndarray points: Points to evaluate the averaging on
        :param ndarray result: If provided, the result will be put in this
            array
        """
        points = points[0]
        xdata = reg.xdata[0]
        ll = local_linear_1d
        if not isinstance(reg.kernel, kernels.NormalKernel1d):
            ll = local_linear_1d
        li2, out = ll(reg.bandwidth, xdata, reg.fitted_ydata, points, reg.kernel, out)
        self.li2 = li2
        return out

    @property
    def q(self):
        """
        Degree of the fitted polynom
        """
        return 1


class PolynomialDesignMatrix1D:
    def __init__(self, degree):
        self.degree = degree
        powers = np.arange(0, degree + 1).reshape((1, degree + 1))
        self.powers = powers

    def __call__(self, dX, out=None):
        return np.power(dX, self.powers, out)


class LocalPolynomialKernel1D(RegressionKernelMethod):
    r"""
    Perform a local-polynomial regression using a user-provided kernel
    (Gaussian by default).

    The local constant regression is the function that minimises, for each
    position:

    .. math::

        f_n(x) \triangleq \argmin_{a_0\in\mathbb{R}}
            \sum_i K\left(\frac{x-X_i}{h}\right)
            \left(Y_i - a_0 - a_1(x-X_i) - \ldots -
                a_q \frac{(x-X_i)^q}{q!}\right)^2

    Where :math:`K(x)` is the kernel such that :math:`E(K(x)) = 0`, :math:`q`
    is the order of the fitted polynomial  and :math:`h` is the bandwidth of
    the method. It is also recommended to have :math:`\int_\mathbb{R} x^2K(x)dx
    = 1`, (i.e. variance of the kernel is 1) or the effective bandwidth will be
    scaled by the square-root of this integral (i.e. the standard deviation of
    the kernel).

    :param ndarray xdata: Explaining variables (at most 2D array)
    :param ndarray ydata: Explained variables (should be 1D array)
    :param int q: Order of the polynomial to fit. **Default:** 3

    :type  cov: float or callable
    :param cov: If an float, it should be a variance of the gaussian kernel.
        Otherwise, it should be a function ``cov(xdata, ydata)`` returning
        the variance.
        **Default:** ``scotts_covariance``

    """

    def __init__(self, q=3):
        self._q = q

    @property
    def q(self):
        """
        Degree of the fitted polynomials
        """
        return self._q

    @q.setter
    def q(self, val):
        self._q = int(val)

    def fit(self, reg):
        assert reg.dim == 1, "This method can only be used with 1D data"
        if self.q == 0:
            obj = SpatialAverage()
            return obj.fit(reg)
        elif self.q == 1:
            obj = LocalLinearKernel1D()
            return obj.fit(reg)
        self = super(LocalPolynomialKernel1D, self).fit(reg)
        self.designMatrix = PolynomialDesignMatrix1D(self.q)
        return self

    def evaluate(self, reg, points, out):
        """
        Evaluate the spatial averaging on a set of points

        :param ndarray points: Points to evaluate the averaging on
        :param ndarray result: If provided, the result will be put
            in this array
        """
        xdata = reg.xdata[0, :, np.newaxis]  # make it a column vector
        ydata = reg.fitted_ydata[:, np.newaxis]  # make it a column vector
        points = points[0]  # make it a line vector
        bw = reg.bandwidth
        kernel = reg.kernel
        designMatrix = self.designMatrix
        for i, p in enumerate(points):
            dX = xdata - p
            Wx = kernel(dX / bw)
            Xx = designMatrix(dX)
            WxXx = Wx * Xx
            XWX = np.dot(Xx.T, WxXx)
            Lx = scipy.linalg.solve(XWX, WxXx.T)[0]
            out[i] = np.dot(Lx, ydata)
        return out


class PolynomialDesignMatrix:
    """
    Class used to create a design matrix for polynomial regression
    """

    def __init__(self, dim, deg):
        self.dim = dim
        self.deg = deg
        self._design_matrix_size()

    def _design_matrix_size(self):
        """
        Compute the size of the design matrix for a n-D problem of order d.
        Can also compute the Taylors factors (i.e. the factors that would be
        applied for the taylor decomposition)

        :param int dim: Dimension of the problem
        :param int deg: Degree of the fitting polynomial
        :param bool factors: If true, the out includes the Taylor factors

        :returns: The number of columns in the design matrix and, if required,
            a ndarray with the taylor coefficients for each column of
            the design matrix.
        """
        dim = self.dim
        deg = self.deg
        init = 1
        dims = [0] * (dim + 1)
        cur = init
        prev = 0
        # if factors:
        #    fcts = [1]
        fact = 1
        for i in range(deg):
            diff = cur - prev
            prev = cur
            old_dims = list(dims)
            fact *= i + 1
            for j in range(dim):
                dp = diff - old_dims[j]
                cur += dp
                dims[j + 1] = dims[j] + dp
        #    if factors:
        #        fcts += [fact]*(cur-prev)
        self.size = cur
        # self.factors = np.array(fcts)

    def __call__(self, x, out=None):
        """
        Creates the design matrix for polynomial fitting using the points x.

        :param ndarray x: Points to create the design matrix.
            Shape must be (D,N) or (N,), where D is the dimension of
            the problem, 1 if not there.

        :param int deg: Degree of the fitting polynomial

        :param ndarray factors: Scaling factor for the columns of the design
            matrix. The shape should be (M,) or (M,1), where M is the number
            of columns of the out. This value can be obtained using
            the :py:func:`designMatrixSize` function.

        :returns: The design matrix as a (M,N) matrix.
        """
        dim, deg = self.dim, self.deg
        # factors = self.factors
        x = np.atleast_2d(x)
        dim = x.shape[0]
        if out is None:
            s = self._design_matrix_size(dim, deg)
            out = np.empty((s, x.shape[1]), dtype=x.dtype)
        dims = [0] * (dim + 1)
        out[0, :] = 1
        cur = 1
        for i in range(deg):
            old_dims = list(dims)
            prev = cur
            for j in range(x.shape[0]):
                dims[j] = cur
                for k in range(old_dims[j], prev):
                    np.multiply(out[k], x[j], out[cur])
                    cur += 1
        # if factors is not None:
        #    factors = np.asarray(factors)
        #    if len(factors.shape) == 1:
        #        factors = factors[:,np.newaxis]
        #    out /= factors
        return out


class LocalPolynomialKernel(RegressionKernelMethod):
    r"""
    Perform a local-polynomial regression in N-D using a user-provided kernel
    (Gaussian by default).

    The local constant regression is the function that minimises,
    for each position:

    .. math::

        f_n(x) \triangleq \argmin_{a_0\in\mathbb{R}}
            \sum_i K\left(\frac{x-X_i}{h}\right)
            \left(Y_i - a_0 - \mathcal{P}_q(X_i-x)\right)^2

    Where :math:`K(x)` is the kernel such that :math:`E(K(x)) = 0`, :math:`q`
    is the order of the fitted polynomial, :math:`\mathcal{P}_q(x)` is a
    polynomial of order :math:`d` in :math:`x` and :math:`h` is the bandwidth
    of the method.

    The polynomial :math:`\mathcal{P}_q(x)` is of the form:

    .. math::

        \mathcal{F}_d(k) = \left\{ \n \in \mathbb{N}^d \middle|
            \sum_{i=1}^d n_i = k \right\}

        \mathcal{P}_q(x_1,\ldots,x_d) = \sum_{k=1}^q
            \sum_{\n\in\mathcal{F}_d(k)} a_{k,\n}
            \prod_{i=1}^d x_i^{n_i}

    For example we have:

    .. math::

        \mathcal{P}_2(x,y) = a_{110} x + a_{101} y + a_{220} x^2 +
            a_{211} xy + a_{202} y^2

    :param ndarray xdata: Explaining variables (at most 2D array).
        The shape should be (N,D) with D the dimension of the problem
        and N the number of points. For 1D array, the shape can be (N,),
        in which case it will be converted to (N,1) array.
    :param ndarray ydata: Explained variables (should be 1D array). The shape
        must be (N,).
    :param int q: Order of the polynomial to fit. **Default:** 3
    :param callable kernel: Kernel to use for the weights. Call is
        ``kernel(points)`` and should return an array of values the same size
        as ``points``. If ``None``, the kernel will be ``normal_kernel(D)``.

    :type  cov: float or callable
    :param cov: If an float, it should be a variance of the gaussian kernel.
        Otherwise, it should be a function ``cov(xdata, ydata)`` returning
        the variance.
        **Default:** ``scotts_covariance``
    """

    def __init__(self, q=3):
        self._q = q

    @property
    def q(self):
        """
        Degree of the fitted polynomials
        """
        return self._q

    @q.setter
    def q(self, val):
        self._q = int(val)

    def fit(self, reg):
        if self.q == 0:
            obj = SpatialAverage()
            return obj.fit(reg)
        elif reg.dim == 1:
            obj = LocalPolynomialKernel1D(self.q)
            return obj.fit(reg)
        self = super().fit(reg)
        self.designMatrix = PolynomialDesignMatrix(reg.dim, self.q)
        return self

    def evaluate(self, reg, points, out):
        """
        Evaluate the spatial averaging on a set of points

        :param ndarray points: Points to evaluate the averaging on
        :param ndarray out: Pre-allocated array for the result
        """
        xdata = reg.xdata
        ydata = reg.fitted_ydata[:, np.newaxis]  # make it a column vector
        d, n = xdata.shape
        designMatrix = self.designMatrix
        dm_size = designMatrix.size
        Xx = np.empty((dm_size, n), dtype=xdata.dtype)
        WxXx = np.empty(Xx.shape, dtype=xdata.dtype)
        XWX = np.empty((dm_size, dm_size), dtype=xdata.dtype)
        inv_bw = scipy.linalg.inv(reg.bandwidth)
        kernel = reg.kernel
        for i in range(points.shape[1]):
            dX = xdata - points[:, i : i + 1]
            Wx = kernel(np.dot(inv_bw, dX))
            designMatrix(dX, out=Xx)
            np.multiply(Wx, Xx, WxXx)
            np.dot(Xx, WxXx.T, XWX)
            Lx = scipy.linalg.solve(XWX, WxXx)[0]
            out[i] = np.dot(Lx, ydata)
        return out


default_method = LocalPolynomialKernel(q=1)
