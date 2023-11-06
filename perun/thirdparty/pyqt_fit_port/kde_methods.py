r"""
:Author: Pierre Barbier de Reuille <pierre.barbierdereuille@gmail.com>

This module contains a set of methods to compute univariate KDEs. See the
objects in the :py:mod:`pyqt_fit.kde` module for more details on these methods.

These methods provide various variations on :math:`\hat{K}(x;X,h,L,U)`, the
modified kernel evaluated on the point :math:`x` based on the estimation points
:math:`X`, a bandwidth :math:`h` and on the domain :math:`[L,U]`.

The definitions of the methods rely on the following definitions:

.. math::

   \begin{array}{rcl}
     a_0(l,u) &=& \int_l^u K(z) dz\\
     a_1(l,u) &=& \int_l^u zK(z) dz\\
     a_2(l,u) &=& \int_l^u z^2K(z) dz
   \end{array}

These definitions correspond to:

- :math:`a_0(l,u)` -- The partial cumulative distribution function
- :math:`a_1(l,u)` -- The partial first moment of the distribution. In
  particular, :math:`a_1(-\infty, \infty)` is the mean of the kernel (i.e. and
  should be 0).
- :math:`a_2(l,u)` -- The partial second moment of the distribution. In
  particular, :math:`a_2(-\infty, \infty)` is the variance of the kernel (i.e.
  which should be close to 1, unless using higher order kernel).

References:
```````````
.. [1] Jones, M. C. 1993. Simple boundary correction for kernel density
    estimation. Statistics and Computing 3: 135--146.
"""
import numpy as np
from scipy import fftpack, integrate, optimize

from perun.thirdparty.pyqt_fit_port.utils import make_ufunc, namedtuple, numpy_trans_idx


def fast_bin(X, a, b, N, weights=None, _=False):
    """
    Fast binning.

    :note: cyclic parameter is ignored. Present only for compatibility with fast_linbin
    """
    Y = X - a
    delta = (b - a) / N
    Y /= delta
    iY = np.floor(Y).astype(int)
    return np.bincount(iY, weights=weights, minlength=N), np.linspace(
        a + delta / 2, b - delta / 2, N
    )


def generate_grid(kde, N=None, cut=None):
    r"""
    Helper method returning a regular grid on the domain of the KDE.

    :param KDE1D kde: Object describing the KDE computation. The object must
        have been fitted!
    :param int N: Number of points in the grid
    :param float cut: for unbounded domains, how far past the maximum should
        the grid extend to, in term of KDE bandwidth

    :return: A vector of N regularly spaced points
    """
    if N is None:
        N = 2**10
    if cut is None:
        cut = kde.kernel.cut
    if kde.lower == -np.inf:
        lower = np.min(kde.xdata) - cut * kde.bandwidth
    else:
        lower = kde.lower
    if kde.upper == np.inf:
        upper = np.max(kde.xdata) + cut * kde.bandwidth
    else:
        upper = kde.upper
    return np.linspace(lower, upper, N)


def compute_bandwidth(kde):
    """
    Compute the bandwidth and covariance for the model, based of its xdata attribute
    """
    if kde.bandwidth_function:
        bw = float(kde.bandwidth_function(kde.xdata, model=kde))
        cov = bw * bw
    elif kde.covariance_function:
        cov = float(kde.covariance_function(kde.xdata, model=kde))
        bw = np.sqrt(cov)
    else:
        return kde.bandwidth, kde.covariance
    return bw, cov


class KDE1DMethod:
    """
    Base class providing a default grid method and a default method for
    unbounded evaluation of the PDF and CDF. It also provides default methods
    for the other metrics, based on PDF and CDF calculations.

    :Note:
        - It is expected that all grid methods will return the same grid if
          used with the same arguments.
        - It is fair to assume all array-like arguments will be at least 1D
          arrays.

    """

    name = "unbounded"

    def pdf(self, kde, points, out):
        """
        Compute the PDF of the estimated distribution.

        :param pyqt_fit.kde.KDE1D kde: KDE object
        :param ndarray points: Points to evaluate the distribution on
        :param ndarray out: Result object. If must have the same shapes as ``points``
        :rtype: ndarray
        :return: Returns the ``out`` variable, updated with the PDF.
        :Default: Direct implementation of the formula for unbounded pdf
            computation.
        """
        xdata = kde.xdata
        points = points[..., np.newaxis]

        bw = kde.bandwidth * kde.lambdas

        z = (points - xdata) / bw

        kernel = kde.kernel

        terms = kernel(z)

        terms *= kde.weights / bw

        terms.sum(axis=-1, out=out)
        out /= kde.total_weights

        return out

    def fit(self, kde):
        """
        Method called by the KDE1D object right after fitting to allow for
        one-time calculation.

        :param pyqt_fit.kde.KDE1D kde: KDE object being fitted
        :Default: Compute the bandwidth and covariance if specified as functions
        """
        kde.compute_bandwidth()

    def __call__(self, kde, points, out):
        """
        Call the :py:meth:`pdf` method.
        """
        return self.pdf(kde, points, out)

    def cdf(self, kde, points, out):
        r"""
        Compute the CDF of the estimated distribution, defined as:

        .. math::

            cdf(x) = P(X \leq x) = \int_l^x p(t) dt

        where :math:`l` is the lower bound of the distribution domain and
        :math:`p` the density of probability

        :param pyqt_fit.kde.KDE1D kde: KDE object
        :param ndarray points: Points to evaluate the CDF on
        :param ndarray out: Result object. If must have the same shapes as ``points``
        :rtype: ndarray
        :return: Returns the ``out`` variable, updated with the CDF.
        :Default: Direct implementation of the formula for unbounded CDF
            computation.
        """
        xdata = kde.xdata
        points = points[..., np.newaxis]
        bw = kde.bandwidth * kde.lambdas

        z = (points - xdata) / bw

        kernel = kde.kernel

        terms = kernel.cdf(z)
        terms *= kde.weights

        terms.sum(axis=-1, out=out)
        out /= kde.total_weights

        return out

    def icdf(self, kde, points, out):
        r"""
        Compute the inverse cumulative distribution (quantile) function,
        defined as:

        .. math::

            icdf(p) = \inf\left\{x\in\mathbb{R} : cdf(x) \geq p\right\}

        :param pyqt_fit.kde.KDE1D kde: KDE object
        :param ndarray points: Points to evaluate the iCDF on
        :param ndarray out: Result object. If must have the same shapes as ``points``
        :rtype: ndarray
        :return: Returns the ``out`` variable, updated with the iCDF.
        :Default: First approximate the result using linear interpolation on
            the CDF and refine the result numerically using the Newton method.
        """
        xs, ys = self.cdf_grid(kde)
        coarse_result = np.interp(points, ys, xs, kde.lower, kde.upper)
        lower = kde.lower
        upper = kde.upper
        cdf = self.cdf
        pdf_out = np.empty(1, dtype=float)

        def pdf(x):
            if x <= lower:
                return 0
            if x >= upper:
                return 0
            return self.pdf(kde, np.atleast_1d(x), pdf_out)

        @make_ufunc()
        def find_inverse(p, approx):
            if p > 1 - 1e-10:
                return upper
            if p < 1e-10:
                return lower
            if approx >= xs[-1] or approx <= xs[0]:
                return approx
            cdf_out = np.empty(1, dtype=float)

            def f(x):
                if x <= lower:
                    return -p
                elif x >= upper:
                    return 1 - p
                return cdf(kde, np.atleast_1d(x), cdf_out) - p

            return optimize.newton(f, approx, fprime=pdf, tol=1e-6)

        return find_inverse(points, coarse_result, out=out)

    def sf(self, kde, points, out):
        r"""
        Compute the survival function, defined as:

        .. math::

            sf(x) = P(X \geq x) = \int_x^u p(t) dt = 1 - cdf(x)

        :param pyqt_fit.kde.KDE1D kde: KDE object
        :param ndarray points: Points to evaluate the survival function on
        :param ndarray out: Result object. If must have the same shapes as ``points``
        :rtype: ndarray
        :return: Returns the ``out`` variable, updated with the survival function.
        :Default: Compute explicitly :math:`1 - cdf(x)`
        """
        self.cdf(kde, points, out)
        out -= 1
        out *= -1
        return out

    def isf(self, kde, points, out):
        r"""
        Compute the inverse survival function, defined as:

        .. math::

            isf(p) = \sup\left\{x\in\mathbb{R} : sf(x) \leq p\right\}

        :param pyqt_fit.kde.KDE1D kde: KDE object
        :param ndarray points: Points to evaluate the iSF on
        :param ndarray out: Result object. If must have the same shapes as ``points``
        :rtype: ndarray
        :return: Returns the ``out`` variable, updated with the inverse survival function.
        :Default: Compute :math:`icdf(1-p)`
        """
        return self.icdf(kde, 1 - points, out)

    def hazard(self, kde, points, out):
        r"""
        Compute the hazard function evaluated on the points.

        The hazard function is defined as:

        .. math::

            h(x) = \frac{p(x)}{sf(x)}

        where :math:`p(x)` is the probability density function and
        :math:`sf(x)` is the survival function.

        :param pyqt_fit.kde.KDE1D kde: KDE object
        :param ndarray points: Points to evaluate the hazard function on
        :param ndarray out: Result object. If must have the same shapes as ``points``
        :rtype: ndarray
        :return: Returns the ``out`` variable, updated with the hazard function
        :Default: Compute explicitly :math:`pdf(x) / sf(x)`
        """
        self.pdf(kde, points, out=out)
        sf = np.empty(out.shape, dtype=out.dtype)
        self.sf(kde, points, sf)
        sf[sf < 0] = 0  # Some methods can produce negative sf
        out /= sf
        return out

    def cumhazard(self, kde, points, out):
        r"""
        Compute the cumulative hazard function evaluated on the points.

        The hazard function is defined as:

        .. math::

            ch(x) = \int_l^x h(t) dt = -\ln sf(x)

        where :math:`l` is the lower bound of the domain, :math:`h` the hazard
        function and :math:`sf` the survival function.

        :param pyqt_fit.kde.KDE1D kde: KDE object
        :param ndarray points: Points to evaluate the cumulative hazard function on
        :param ndarray out: Result object. If must have the same shapes as ``points``
        :rtype: ndarray
        :return: Returns the ``out`` variable, updated with the cumulative hazard function
        :Default: Compute explicitly :math:`-\ln sf(x)`
        """
        self.sf(kde, points, out)
        out[out < 0] = 0  # Some methods can produce negative sf
        np.log(out, out=out)
        out *= -1
        return out

    def grid(self, kde, N=None, cut=None):
        """
        Evaluate the PDF of the distribution on a regular grid with at least
        ``N`` elements.

        :param pyqt_fit.kde.KDE1D kde: KDE object
        :param int N: minimum number of element in the returned grid. Most
            methods will want to round it to the next power of 2.
        :param float cut: for unbounded domains, how far from the last data
            point should the grid go, as a fraction of the bandwidth.
        :rtype: (ndarray, ndarray)
        :returns: The array of positions the PDF has been estimated on, and the
            estimations.
        :Default: Evaluate :math:`pdf(x)` on a grid generated using
            :py:func:`generate_grid`
        """
        N = self.grid_size(N)
        g = generate_grid(kde, N, cut)
        out = np.empty(g.shape, dtype=float)
        return g, self.pdf(kde, g, out)

    def cdf_grid(self, kde, N=None, cut=None):
        """
        Evaluate the CDF of the distribution on a regular grid with at least
        ``N`` elements.

        :param pyqt_fit.kde.KDE1D kde: KDE object
        :param int N: minimum number of element in the returned grid. Most
            methods will want to round it to the next power of 2.
        :param float cut: for unbounded domains, how far from the last data
            point should the grid go, as a fraction of the bandwidth.
        :rtype: (ndarray, ndarray)
        :returns: The array of positions the CDF has been estimated on, and the
            estimations.
        :Default: Evaluate :math:`cdf(x)` on a grid generated using
            :py:func:`generate_grid`
        """
        N = self.grid_size(N)
        g = generate_grid(kde, N, cut)
        out = np.empty(g.shape, dtype=float)
        return g, self.cdf(kde, g, out)

    def icdf_grid(self, kde, N=None, cut=None):
        """
        Compute the inverse cumulative distribution (quantile) function on
        a grid.

        :Note: The default implementation is not as good an approximation as
            the plain icdf default method.

        :param pyqt_fit.kde.KDE1D kde: KDE object
        :param int N: minimum number of element in the returned grid. Most
            methods will want to round it to the next power of 2.
        :param float cut: for unbounded domains, how far from the last data
            point should the grid go, as a fraction of the bandwidth.
        :rtype: (ndarray, ndarray)
        :returns: The array of positions the CDF has been estimated on, and the
            estimations.
        :Default: Linear interpolation of the inverse CDF on a grid
        """
        xs, ys = self.cdf_grid(kde, N, cut)
        N = len(xs)
        points = np.linspace(0, 1, N)
        icdf = np.interp(points, ys, xs, kde.lower, kde.upper)
        return points, icdf

    def sf_grid(self, kde, N=None, cut=None):
        r"""
        Compute the survival function on a grid.

        :param pyqt_fit.kde.KDE1D kde: KDE object
        :param int N: minimum number of element in the returned grid. Most
            methods will want to round it to the next power of 2.
        :param float cut: for unbounded domains, how far from the last data
            point should the grid go, as a fraction of the bandwidth.
        :rtype: (ndarray, ndarray)
        :returns: The array of positions the survival function has been
            estimated on, and the estimations.
        :Default: Compute explicitly :math:`1 - cdf(x)`
        """
        points, out = self.cdf_grid(kde, N, cut)
        out -= 1
        out *= -1
        return points, out

    def isf_grid(self, kde, N=None, cut=None):
        """
        Compute the inverse survival function on a grid.

        :Note: The default implementation is not as good an approximation as
            the plain isf default method.

        :param pyqt_fit.kde.KDE1D kde: KDE object
        :param int N: minimum number of element in the returned grid. Most
            methods will want to round it to the next power of 2.
        :param float cut: for unbounded domains, how far from the last data
            point should the grid go, as a fraction of the bandwidth.
        :rtype: (ndarray, ndarray)
        :returns: The array of positions the CDF has been estimated on, and the
            estimations.
        :Default: Linear interpolation of the inverse survival function on a grid
        """
        xs, ys = self.sf_grid(kde, N, cut)
        N = len(xs)
        points = np.linspace(0, 1, N)
        isf = np.interp(points, ys[::-1], xs[::-1], kde.upper, kde.lower)
        return points, isf

    def hazard_grid(self, kde, N=None, cut=None):
        r"""
        Compute the hazard function on a grid.

        :param pyqt_fit.kde.KDE1D kde: KDE object
        :param int N: minimum number of element in the returned grid. Most
            methods will want to round it to the next power of 2.
        :param float cut: for unbounded domains, how far from the last data
            point should the grid go, as a fraction of the bandwidth.
        :rtype: (ndarray, ndarray)
        :returns: The array of positions the hazard function has been
            estimated on, and the estimations.
        :Default: Compute explicitly :math:`pdf(x) / sf(x)`
        """
        points, out = self.grid(kde, N, cut)
        _, sf = self.sf_grid(kde, N, cut)
        sf[sf < 0] = 0  # Some methods can produce negative sf
        out /= sf
        return points, out

    def cumhazard_grid(self, kde, N=None, cut=None):
        r"""
        Compute the hazard function on a grid.

        :param pyqt_fit.kde.KDE1D kde: KDE object
        :param int N: minimum number of element in the returned grid. Most
            methods will want to round it to the next power of 2.
        :param float cut: for unbounded domains, how far from the last data
            point should the grid go, as a fraction of the bandwidth.
        :rtype: (ndarray, ndarray)
        :returns: The array of positions the hazard function has been
            estimated on, and the estimations.
        :Default: Compute explicitly :math:`-\ln sf(x)`
        """
        points, out = self.sf_grid(kde, N, cut)
        out[out < 0] = 0  # Some methods can produce negative sf
        np.log(out, out=out)
        out *= -1
        return points, out

    def __str__(self):
        """
        Return the name of the method
        """
        return self.name

    def numeric_cdf(self, kde, points, out):
        """
        Provide a numeric approximation of the CDF based on integrating the pdf
        using :py:func:`scipy.integrate.quad`.
        """
        pts = points.ravel()

        pts[pts < kde.lower] = kde.lower
        pts[pts > kde.upper] = kde.upper

        ix = pts.argsort()

        sp = pts[ix]

        pdf_out = np.empty((1,), dtype=float)

        def pdf(x):
            return self.pdf(kde, np.array([x]), pdf_out)

        @make_ufunc()
        def comp_cdf(i):
            low = kde.lower if i == 0 else sp[i - 1]
            return integrate.quad(pdf, low, sp[i])[0]

        parts = np.empty(sp.shape, dtype=float)
        comp_cdf(np.arange(len(sp)), out=parts)

        ints = parts.cumsum()

        out.put(ix, ints)
        return out

    def numeric_cdf_grid(self, kde, N=None, cut=None):
        """
        Compute the CDF on a grid using a trivial, but fast, numeric
        integration of the pdf.
        """
        pts, pdf = self.grid(kde, N, cut)
        cdf = integrate.cumtrapz(pdf, pts, initial=0)
        return pts, cdf

    def grid_size(self, N=None):
        if N is None:
            return 2**10
        return N


unbounded = KDE1DMethod()


class RenormalizationMethod(KDE1DMethod):
    r"""
    This method consists in using the normal kernel method, but renormalize
    to only take into account the part of the kernel within the domain of the
    density [1]_.

    The kernel is then replaced with:

    .. math::

        \hat{K}(x;X,h,L,U) \triangleq \frac{1}{a_0(u,l)} K(z)

    where:

    .. math::

        z = \frac{x-X}{h} \qquad l = \frac{L-x}{h} \qquad u = \frac{U-x}{h}

    """

    name = "renormalization"

    def pdf(self, kde, points, out):
        if not kde.bounded:
            return KDE1DMethod.pdf(self, kde, points, out)

        xdata = kde.xdata
        points = points[..., np.newaxis]

        bw = kde.bandwidth * kde.lambdas

        l = (points - kde.lower) / bw
        u = (points - kde.upper) / bw
        z = (points - xdata) / bw

        kernel = kde.kernel

        a1 = kernel.cdf(l) - kernel.cdf(u)

        terms = kernel(z) * ((kde.weights / bw) / a1)

        terms.sum(axis=-1, out=out)
        out /= kde.total_weights

        return out

    def cdf(self, kde, points, out):
        if not kde.bounded:
            return KDE1DMethod.cdf(self, kde, points, out)
        return self.numeric_cdf(kde, points, out)

    def cdf_grid(self, kde, N=None, cut=None):
        if N is None:
            N = 2**10
        if not kde.bounded or N <= 2**11:
            return KDE1DMethod.cdf_grid(self, kde, N, cut)
        return self.numeric_cdf_grid(kde, N, cut)


renormalization = RenormalizationMethod()


class ReflectionMethod(KDE1DMethod):
    r"""
    This method consist in simulating the reflection of the data left and
    right of the boundaries. If one of the boundary is infinite, then the
    data is not reflected in that direction. To this purpose, the kernel is
    replaced with:

    .. math::

        \hat{K}(x; X, h, L, U) \triangleq K(z)
        + K\left(\frac{x+X-2L}{h}\right)
        + K\left(\frac{x+X-2U}{h}\right)

    where:

    .. math::

        z = \frac{x-X}{h}


    See the :py:mod:`pyqt_fit.kde_methods` for a description of the various
    symbols.

    When computing grids, if the bandwidth is constant, the result is computing
    using CDT.
    """

    name = "reflection"

    def pdf(self, kde, points, out):
        if not kde.bounded:
            return KDE1DMethod.pdf(self, kde, points, out)

        xdata = kde.xdata
        points = points[..., np.newaxis]

        # Make sure points are between the bounds, with reflection if needed
        if any(points < kde.lower) or any(points > kde.upper):
            span = kde.upper - kde.lower
            points = points - (kde.lower + span)
            points %= 2 * span
            points -= kde.lower + span
            points = np.abs(points)

        bw = kde.bandwidth * kde.lambdas

        z = (points - xdata) / bw
        z1 = (points + xdata) / bw
        L = kde.lower
        U = kde.upper

        kernel = kde.kernel

        terms = kernel(z)

        if L > -np.inf:
            terms += kernel(z1 - (2 * L / bw))

        if U < np.inf:
            terms += kernel(z1 - (2 * U / bw))

        terms *= kde.weights / bw
        terms.sum(axis=-1, out=out)
        out /= kde.total_weights

        return out

    def cdf(self, kde, points, out):
        if not kde.bounded:
            return KDE1DMethod.cdf(self, kde, points, out)

        xdata = kde.xdata
        points = points[..., np.newaxis]

        # Make sure points are between the bounds, with reflection if needed
        if any(points < kde.lower) or any(points > kde.upper):
            span = kde.upper - kde.lower
            points = points - (kde.lower + span)
            points %= 2 * span
            points -= kde.lower + span
            points = np.abs(points)

        bw = kde.bandwidth * kde.lambdas

        z = (points - xdata) / bw
        z1 = (points + xdata) / bw
        L = kde.lower
        U = kde.upper

        kernel = kde.kernel

        terms = kernel.cdf(z)

        if L > -np.inf:
            terms -= kernel.cdf((L - xdata) / bw)  # Remove the truncated part on the left
            terms += kernel.cdf(z1 - (2 * L / bw))  # Add the reflected part
            terms -= kernel.cdf((xdata - L) / bw)  # Remove the truncated part from the reflection

        if U < np.inf:
            terms += kernel.cdf(z1 - (2 * U / bw))  # Add the reflected part

        terms *= kde.weights
        terms.sum(axis=-1, out=out)
        out /= kde.total_weights

        return out

    def grid(self, kde, N=None, cut=None):
        """
        DCT-based estimation of KDE estimation, i.e. with reflection boundary
        conditions. This works only for fixed bandwidth (i.e. lambdas = 1) and
        gaussian kernel.

        For open domains, the grid is taken with 3 times the bandwidth as extra
        space to remove the boundary problems.
        """
        if kde.lambdas.shape:
            return KDE1DMethod.grid(self, kde, N, cut)

        bw = kde.bandwidth * kde.lambdas
        data = kde.xdata
        N = self.grid_size(N)

        if cut is None:
            cut = kde.kernel.cut

        if kde.lower == -np.inf:
            lower = np.min(data) - cut * kde.bandwidth
        else:
            lower = kde.lower
        if kde.upper == np.inf:
            upper = np.max(data) + cut * kde.bandwidth
        else:
            upper = kde.upper

        R = upper - lower

        # Histogram the data to get a crude first approximation of the density
        weights = kde.weights
        if not weights.shape:
            weights = None

        DataHist, mesh = fast_bin(data, lower, upper, N, weights=weights, cyclic=False)

        DataHist = DataHist / kde.total_weights
        DCTData = fftpack.dct(DataHist, norm=None)

        t_star = bw / R
        gp = np.arange(N) * np.pi * t_star
        smth = kde.kernel.dct(gp)

        # Smooth the DCTransformed data using t_star
        SmDCTData = DCTData * smth
        # Inverse DCT to get density
        density = fftpack.idct(SmDCTData, norm=None) / (2 * R)

        return mesh, density

    def grid_size(self, N=None):
        if N is None:
            return 2**14
        return 2 ** int(np.ceil(np.log2(N)))


reflection = ReflectionMethod()


class LinearCombinationMethod(KDE1DMethod):
    r"""
    This method uses the linear combination correction published in [1]_.

    The estimation is done with a modified kernel given by:

    .. math::

        \hat{K}(x;X,h,L,U) \triangleq \frac{a_2(l,u) - a_1(-u, -l) z}{a_2(l,u)a_0(l,u)
        - a_1(-u,-l)^2} K(z)

    where:

    .. math::

        z = \frac{x-X}{h} \qquad l = \frac{L-x}{h} \qquad u = \frac{U-x}{h}

    """

    name = "linear combination"

    def pdf(self, kde, points, out):
        if not kde.bounded:
            return KDE1DMethod.pdf(self, kde, points, out)

        xdata = kde.xdata
        points = np.atleast_1d(points)[..., np.newaxis]

        bw = kde.bandwidth * kde.lambdas

        l = (kde.lower - points) / bw
        u = (kde.upper - points) / bw
        z = (points - xdata) / bw

        kernel = kde.kernel

        a0 = kernel.cdf(u) - kernel.cdf(l)
        a1 = kernel.pm1(-l) - kernel.pm1(-u)
        a2 = kernel.pm2(u) - kernel.pm2(l)

        denom = a2 * a0 - a1 * a1
        upper = a2 - a1 * z

        upper /= denom
        upper *= (kde.weights / bw) * kernel(z)

        upper.sum(axis=-1, out=out)
        out /= kde.total_weights

        return out

    def cdf(self, kde, points, out):
        if not kde.bounded:
            return KDE1DMethod.cdf(self, kde, points, out)
        return self.numeric_cdf(kde, points, out)

    def cdf_grid(self, kde, N=None, cut=None):
        if N is None:
            N = 2**10
        if not kde.bounded or N <= 2**11:
            return KDE1DMethod.cdf_grid(self, kde, N, cut)
        return self.numeric_cdf_grid(kde, N, cut)


linear_combination = LinearCombinationMethod()


class CyclicMethod(KDE1DMethod):
    r"""
    This method assumes cyclic boundary conditions and works only for closed
    boundaries.

    The estimation is done with a modified kernel given by:

    .. math::

        \hat{K}(x; X, h, L, U) \triangleq K(z)
        + K\left(z - \frac{U-L}{h}\right)
        + K\left(z + \frac{U-L}{h}\right)

    where:

    .. math::

        z = \frac{x-X}{h}

    When computing grids, if the bandwidth is constant, the result is computing
    using FFT.
    """

    name = "cyclic"

    def pdf(self, kde, points, out):
        if not kde.bounded:
            return KDE1DMethod.pdf(self, kde, points, out)
        if not kde.closed:
            raise ValueError(
                "Cyclic boundary conditions can only be used with closed or un-bounded domains."
            )

        xdata = kde.xdata
        points = np.atleast_1d(points)[..., np.newaxis]

        # Make sure points are between the bounds
        if any(points < kde.lower) or any(points > kde.upper):
            points = points - kde.lower
            points %= kde.upper - kde.lower
            points += kde.lower

        bw = kde.bandwidth * kde.lambdas

        z = (points - xdata) / bw
        L = kde.lower
        U = kde.upper

        span = (U - L) / bw

        kernel = kde.kernel

        terms = kernel(z)
        terms += kernel(z + span)  # Add points to the left
        terms += kernel(z - span)  # Add points to the right

        terms *= kde.weights / bw
        terms.sum(axis=-1, out=out)
        out /= kde.total_weights

        return out

    def cdf(self, kde, points, out):
        if not kde.bounded:
            return KDE1DMethod.cdf(self, kde, points, out)
        if not kde.closed:
            raise ValueError(
                "Cyclic boundary conditions can only be used with closed or unbounded domains."
            )

        xdata = kde.xdata
        points = np.atleast_1d(points)[..., np.newaxis]

        # Make sure points are between the bounds
        if any(points < kde.lower) or any(points > kde.upper):
            points = points - kde.lower
            points %= kde.upper - kde.lower
            points += kde.lower

        bw = kde.bandwidth * kde.lambdas

        z = (points - xdata) / bw
        L = kde.lower
        U = kde.upper

        span = (U - L) / bw

        kernel = kde.kernel

        terms = kernel.cdf(z)
        terms -= kernel.cdf((L - xdata) / bw)  # Remove the parts left of the lower bound

        terms += kernel.cdf(z + span)  # Repeat on the left
        terms -= kernel.cdf((L - xdata) / bw + span)  # Remove parts left of lower bounds

        terms += kernel.cdf(z - span)  # Repeat on the right

        terms *= kde.weights
        terms.sum(axis=-1, out=out)
        out /= kde.total_weights

        return out

    def grid(self, kde, N=None, cut=None):
        """
        FFT-based estimation of KDE estimation, i.e. with cyclic boundary
        conditions. This works only for closed domains, fixed bandwidth
        (i.e. lambdas = 1) and gaussian kernel.
        """
        if kde.lambdas.shape:
            return KDE1DMethod.grid(self, kde, N, cut)
        if kde.bounded and not kde.closed:
            raise ValueError(
                "Error, cyclic boundary conditions require a closed or un-bounded domain."
            )
        bw = kde.bandwidth * kde.lambdas
        data = kde.xdata
        N = self.grid_size(N)

        lower = kde.lower
        upper = kde.upper

        if upper == np.inf:
            lower = np.min(data) - cut * kde.bandwidth
            upper = np.max(data) + cut * kde.bandwidth

        R = upper - lower
        weights = kde.weights
        if not weights.shape:
            weights = None

        DataHist, mesh = fast_bin(data, lower, upper, N, weights=weights, cyclic=True)
        DataHist = DataHist / kde.total_weights
        FFTData = np.fft.rfft(DataHist)

        t_star = 2 * bw / R
        gp = np.arange(len(FFTData)) * np.pi * t_star
        smth = kde.kernel.fft(gp)

        SmoothFFTData = FFTData * smth
        density = np.fft.irfft(SmoothFFTData, len(DataHist)) / (mesh[1] - mesh[0])
        return mesh, density

    def cdf_grid(self, kde, N=None, cut=None):
        if kde.lambdas.shape:
            return KDE1DMethod.cdf_grid(self, kde, N, cut)
        if not kde.closed:
            raise ValueError("Error, cyclic boundary conditions require a closed domain.")
        N = self.grid_size(N)

        if N <= 2**12:
            return KDE1DMethod.cdf_grid(self, kde, N, cut)
        return self.numeric_cdf_grid(kde, N, cut)

    def grid_size(self, N=None):
        if N is None:
            return 2**14
        return 2 ** int(np.ceil(np.log2(N)))


cyclic = CyclicMethod()

Transform = namedtuple("Tranform", ["__call__", "inv", "Dinv"])


def _inverse(x, out=None):
    return np.divide(1, x, out)


LogTransform = Transform(np.log, np.exp, np.exp)
ExpTransform = Transform(np.exp, np.log, _inverse)


def transform_distribution(xs, ys, Dinv, out):
    r"""
    Transform a distribution into another one by a change a variable.

    :param ndarray xs: Evaluation points of the distribution
    :param ndarray ys: Distribution value on the points xs
    :param func Dinv: Function evaluating the derivative of the inverse transformation  function
    :param ndarray out: Array in which to store the result
    :rtype: ndarray
    :returns: The variable ``out``, updated wih the transformed distribution

    Given a random variable :math:`X` of distribution :math:`f_X`, the random
    variable :math:`Y = g(X)` has a distribution :math:`f_Y` given by:

    .. math::

        f_Y(y) = \left| \frac{1}{g'(g^{-1}(y))} \right| \cdot f_X(g^{-1}(y))

    """
    Dinv(xs, out=out)
    np.abs(out, out=out)
    _inverse(out, out=out)
    np.multiply(out, ys, out=out)
    return out


def create_transform(obj, inv=None, Dinv=None):
    """
    Create a transform object.

    :param fun obj: This can be either simple a function, or a function-object with an 'inv' and/or 'Dinv' attributes
        containing the inverse function and its derivative (respectively)
    :param fun inv: If provided, inverse of the main function
    :param fun Dinv: If provided, derivative of the inverse function
    :rtype: Transform
    :returns: A transform object with function, inverse and derivative of the inverse

    The inverse function must be provided, either as argument or as attribute to the object. The derivative of the
    inverse will be estimated numerically if not provided.

    :Note: All the functions should accept an ``out`` argument to store the result.
    """
    if isinstance(obj, Transform):
        return obj
    fct = obj.__call__
    if inv is None:
        if not hasattr(obj, "inv"):
            raise AttributeError(
                "Error, transform object must have a 'inv' "
                "attribute or you must specify the 'inv' argument"
            )
        inv = obj.inv
    if Dinv is None:
        if hasattr(obj, "Dinv"):
            Dinv = obj.Dinv
        else:

            @numpy_trans_idx
            def Dinv(x):
                dx = x * 1e-9
                dx[x == 0] = np.min(dx[x != 0])
                return (inv(x + dx) - inv(x - dx)) / (2 * dx)

    return Transform(fct, inv, Dinv)


class _fakeKDE(object):
    def __init__(self, method):
        self.method = method.method


class TransformKDE1DMethod(KDE1DMethod):
    r"""
    Compute the Kernel Density Estimate of a dataset, transforming it first to
    a domain where distances are "more meaningful".

    Often, KDE is best estimated in a different domain. This object takes
    a KDE1D object (or one compatible), and a transformation function.

    Given a random variable :math:`X` of distribution :math:`f_X`, the random
    variable :math:`Y = g(X)` has a distribution :math:`f_Y` given by:

    .. math::

        f_Y(y) = \left| \frac{1}{g'(g^{-1}(y))} \right| \cdot f_X(g^{-1}(y))

    In our term, :math:`Y` is the random variable the user is interested in,
    and :math:`X` the random variable we can estimate using the KDE. In this
    case, :math:`g` is the transform from :math:`Y` to :math:`X`.

    So to estimate the distribution on a set of points given in :math:`x`, we
    need a total of three functions:

        - Direct function: transform from the original space to the one in
          which the KDE will be perform (i.e. :math:`g^{-1}: y \mapsto x`)
        - Invert function: transform from the KDE space to the original one
          (i.e. :math:`g: x \mapsto y`)
        - Derivative of the invert function

    If the derivative is not provided, it will be estimated numerically.

    :param trans: Either a simple function, or a function object with
        attributes `inv` and `Dinv` to use in case they are not provided as
        arguments. The helper :py:func:`create_transform` will provide numeric
        approximation of the derivative if required.
    :param method: instance of KDE1DMethod used in the transformed domain.
        Default is :py:class:`pyqt_fit.kde_methods.KDE1DMethod`
    :param inv: Invert of the function. If not provided, `trans` must have
        it as attribute.
    :param Dinv: Derivative of the invert function.

    :Note: all given functions should accept an optional ``out`` argument to
        get a pre-allocated array to store its result. Also the ``out``
        parameter may be one of the input argument.
    """

    def __init__(self, trans, method=None, inv=None, Dinv=None):
        self.trans = create_transform(trans, inv, Dinv)
        if method is None:
            method = KDE1DMethod()
        self.method = method

    def fit(self, kde):
        """
        Method called by the KDE1D object right after fitting to allow for
        one-time calculation.

        This method copy, and transform, the various attributes of the KDE.

        :param pyqt_fit.kde.KDE1D kde: KDE object being fitted
        """
        fake_kde = _fakeKDE(self)
        fake_kde.lower = self.trans(kde.lower)
        fake_kde.upper = self.trans(kde.upper)
        fake_kde.xdata = self.trans(kde.xdata)

        copy_attrs = [
            "weights",
            "lambdas",
            "kernel",
            "bandwidth",
            "covariance",
            "bandwidth_function",
            "covariance_function",
            "total_weights",
        ]

        for attr in copy_attrs:
            setattr(fake_kde, attr, getattr(kde, attr))

        # Compute the bandwidth for the fake KDE and update the KDE itself
        bw, cov = compute_bandwidth(fake_kde)
        fake_kde.bandwidth = kde.bandwidth = bw
        fake_kde.covariance = kde.covariance = cov

        self.fake_kde = fake_kde

    def pdf(self, kde, points, out):
        trans = self.trans
        pts = trans(points)
        self.method(self.fake_kde, pts, out)
        return transform_distribution(pts, out, trans.Dinv, out=out)

    def grid(self, kde, N=None, cut=None):
        xs, ys = self.method.grid(self.fake_kde, N, cut)
        trans = self.trans
        transform_distribution(xs, ys, trans.Dinv, out=ys)
        trans.inv(xs, out=xs)
        return xs, ys

    def cdf(self, kde, points, out):
        return self.method.cdf(self.fake_kde, self.trans(points), out)

    def cdf_grid(self, kde, N=None, cut=None):
        xs, ys = self.method.cdf_grid(self.fake_kde, N, cut)
        self.trans.inv(xs, out=xs)
        return xs, ys

    def sf(self, kde, points, out):
        return self.method.sf(self.fake_kde, self.trans(points), out)

    def sf_grid(self, kde, N=None, cut=None):
        xs, ys = self.method.sf_grid(self.fake_kde, N, cut)
        return self.trans.inv(xs), ys

    def icdf(self, kde, points, out):
        self.method.icdf(self.fake_kde, points, out)
        self.trans.inv(out, out=out)
        return out

    def icdf_grid(self, kde, N=None, cut=None):
        xs, ys = self.method.icdf_grid(self.fake_kde, N, cut)
        self.trans.inv(ys, out=ys)
        return xs, ys

    def isf(self, kde, points, out):
        self.method.isf(self.fake_kde, points, out)
        self.trans.inv(out, out=out)
        return out

    def isf_grid(self, kde, N=None, cut=None):
        xs, ys = self.method.isf_grid(self.fake_kde, N, cut)
        self.trans.inv(ys, out=ys)
        return xs, ys


def transformKDE1D(trans, method=None, inv=None, Dinv=None):
    """
    Creates an instance of :py:class:`TransformKDE1DMethod`
    """
    return TransformKDE1DMethod(trans, method, inv, Dinv)


default_method = reflection
