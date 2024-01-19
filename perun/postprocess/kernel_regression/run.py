"""
Postprocessor module with non-parametric analysis using the kernel regression methods.
"""
from __future__ import annotations

# Standard Imports
from typing import Any, TYPE_CHECKING

# Third-Party Imports
import click

# Perun Imports
from perun.logic import runner
from perun.postprocess.kernel_regression import methods
from perun.postprocess.regression_analysis import data_provider, tools
from perun.utils.common import cli_kit
from perun.utils.structs import PostprocessStatus

if TYPE_CHECKING:
    from perun.profile.factory import Profile


# Supported types of regression estimator:
# - 'lc': local-constant (Nadaraya-Watson kernel regression), 'll': local-linear
# -- First estimator is set as default: 'll'
_REGRESSION_ESTIMATORS: list[str] = ["ll", "lc"]
# Supported methods for bandwidth estimation:
# - 'cv_ls': least-squares cross validation, 'aic': AIC Hurvich bandwidth estimation
# -- First estimate method is set as default: 'cv_ls'
_BANDWIDTH_METHODS: list[str] = ["cv_ls", "aic"]
# Efficient execution of the bandwidth estimation
_DEFAULT_EFFICIENT: bool = False
# The way of performing of the bandwidth estimation: randomize or routine
_DEFAULT_RANDOMIZE: bool = False
# Default size of the sub-samples
_DEFAULT_N_SUB: int = 50
# Default number of random re-samples used to bandwidth estimation
_DEFAULT_N_RES: int = 25
# Using the median of all scaling factors for each sub-sample
# - Default is computed the mean of all scaling factors
_DEFAULT_RETURN_MEDIAN: bool = False
# Set of kernels for use with `kernel-smoothing` mode of kernel-regression
# - Epanechnikov kernel by default at computation
_KERNEL_TYPES: list[str] = [
    "epanechnikov",
    "tricube",
    "normal",
    "epanechnikov4",
    "normal4",
]
# Supported method for non-parametric regression using kernel methods
# - Default non-parametric regression method: spatial-average
_SMOOTHING_METHODS: list[str] = ["spatial-average", "local-linear", "local-polynomial"]
# Default value for order of the polynomial to fit with `local-polynomial` kernel smoothing method
_DEFAULT_POLYNOMIAL_ORDER: int = 3
# Default range (minimal and maximal values) for automatic bandwidth selection at `kernel-ridge`
_DEFAULT_GAMMA_RANGE: tuple[float, float] = (1e-5, 1e-4)
# Default size of step for iteration over given range in gamma parameter at `kernel-ridge`
_DEFAULT_GAMMA_STEP: float = 1e-5


def postprocess(
    profile: Profile, **configuration: Any
) -> tuple[PostprocessStatus, str, dict[str, Any]]:
    """
    Invoked from perun core, handles the postprocess actions

    :param dict profile: the profile to analyze
    :param configuration: the perun and options context
    """
    # Perform the non-parametric analysis using the kernel regression
    kernel_models = methods.compute_kernel_regression(
        data_provider.generic_profile_provider(profile, **configuration), configuration
    )

    # Return the profile after the execution of kernel regression
    return (
        PostprocessStatus.OK,
        "",
        {"profile": tools.add_models_to_profile(profile, kernel_models)},
    )


@click.command(name="estimator-settings")
@click.option(
    "--reg-type",
    "-rt",
    type=click.Choice(_REGRESSION_ESTIMATORS),
    default=_REGRESSION_ESTIMATORS[0],
    help=(
        'Provides the type for regression estimator. Supported types are: "lc": '
        'local-constant (Nadaraya-Watson) and "ll": local-linear estimator. Default is '
        '"ll". For more information about these types you can visit Perun '
        "Documentation."
    ),
)
@click.option(
    "--bandwidth-method",
    "-bw",
    type=click.Choice(_BANDWIDTH_METHODS),
    default=_BANDWIDTH_METHODS[0],
    help=(
        'Provides the method for bandwidth selection. Supported values are: "cv-ls": '
        'least-squares cross validation and "aic": AIC Hurvich bandwidth estimation. '
        'Default is "cv-ls". For more information about these methods you can visit '
        "Perun Documentation."
    ),
)
@click.option(
    "--efficient/--uniformly",
    default=_DEFAULT_EFFICIENT,
    help=(
        "If True, is executing the efficient bandwidth estimation - by taking smaller "
        "sub-samples and estimating the scaling factor of each sub-sample. It is useful"
        " for large samples and/or multiple variables. If False (default), all data is "
        "used at the same time."
    ),
)
@click.option(
    "--randomize/--no-randomize",
    default=_DEFAULT_RANDOMIZE,
    help=(
        "If True, the bandwidth estimation is performed by taking <n_res> random "
        "re-samples of size <n-sub-samples> from the full sample. If set to False "
        "(default), is performed by slicing the full sample in sub-samples of "
        "<n-sub-samples> size, so that all samples are used once."
    ),
)
@click.option(
    "--n-sub-samples",
    "-nsub",
    type=click.IntRange(min=1, max=None),
    default=_DEFAULT_N_SUB,
    help="Size of the sub-samples (default is 50).",
)
@click.option(
    "--n-re-samples",
    "-nres",
    type=click.IntRange(min=1, max=None),
    default=_DEFAULT_N_RES,
    help=(
        "The number of random re-samples used to bandwidth estimation. "
        "It has effect only if <randomize> is set to True. Default values is 25."
    ),
)
@click.option(
    "--return-median/--return-mean",
    default=_DEFAULT_RETURN_MEDIAN,
    help=(
        "If True, the estimator uses the median of all scaling factors for each "
        "sub-sample to estimate bandwidth of the full sample. If False (default), the "
        "estimator used the mean."
    ),
)
@click.pass_context
def estimator_settings(ctx: click.Context, **kwargs: Any) -> None:
    r"""
    Nadaraya-Watson kernel regression with specific settings for estimate.

    As has been mentioned above, the kernel regression aims to estimate the functional relation
    between explanatory variable **y** and the response variable **X**. This mode of kernel
    regression postprocessor calculates the conditional mean **E[y|X] = m(X)**, where **y = m(X) +**
    :math:`\epsilon`. Variable **X** is represented in the postprocessor by <per-key> option and
    the variable **y** is represented by <of-key> option.

    **Regression Estimator <reg-type>**:

         This mode offer two types of *regression estimator* <`reg-type`>. *Local Constant (`ll`)*
         type of regression provided by this mode is also known as *Nadaraya-Watson*
         kernel regression:

            **Nadaraya-Watson**: expects the following conditional expectation: **E[y|X] = m(X)**,
            where function **m(*)** represents the regression function to estimate. Then we can
            alternatively write the following formula: **y = m(X) +** :math:`\epsilon`, **E**
            (:math:`\epsilon`) **= 0**. Then we can suppose, that we have the set of independent
            observations {(:math:`{x_1}`, :math:`{y_1}`), ..., (:math:`{x_n}`, :math:`{y_n}`)} and
            the **Nadaraya-Watson** estimator is defined as:

                .. math::

                       m_{h}(x) = \sum_{i=1}^{n}K_h(x - x_i)y_i / \sum_{j=1}^{n}K_h(x - x_j)

            where :math:`{K_h}` is a kernel with bandwidth *h*. The denominator is a weighting term
            with sum 1. It easy to see that this kernel regression estimator is just a weighted sum
            of the observed responses :math:`{y_i}`. There are many other kernel estimators that
            are various in compare to this presented estimator. However, since all are asymptotic
            equivalently, we will not deal with them closer. **Kernel Regression** postprocessor
            works in all modes only with **Nadaraya-Watson** estimator.

        The second supported *regression estimator* in this mode of postprocessor is *Local Linear
        (`lc`)*. This type is an extension of that which suffers less from bias issues at the
        edge of the support.

            **Local Linear**: estimator, that offers various advantages compared with other
            kernel-type estimators, such as the *Nadaraya-Watson* estimator. More precisely, it
            adapts to both random and fixed designs, and to various design densities such as highly
            clustered designs and nearly uniform designs. It turns out that the *local linear*
            smoother repairs the drawbacks of other kernel regression estimators. A regression
            estimator *m* of *m* is a linear smoother if, for each *x*, there is a vector
            :math:`l(x) = (l_1(x), ..., l_n(x))^T` such that:

                .. math::

                    m(x) = \sum_{i=1}^{n}l_i(x)Y_i = l(x)^TY

                where :math:`Y = (Y_1, ..., Y_n)^T`. For kernel estimators:

                .. math::

                    l_i(x) = K(||x - X_i|| / h) / \sum_{j=1}^{n}K(||x - X_j|| / h)

                where *K* represents kernel and *h* its bandwidth.

            For a better imagination, there is an interesting fact, that the following estimators
            are linear smoothers too: *Gaussian process regression*, *splines*.

    **Bandwidth Method <bandwidth-method>**:

        As has been said in the general description of the *kernel regression*, one of the most
        important factors of the resulting estimate is the kernel **bandwidth**. When the
        inappropriate value is selected may occur to *under-laying* or *over-laying* fo the
        resulting kernel estimate. Since the bandwidth of the kernel is a free parameter which
        exhibits a strong influence on the resulting estimate postprocessor offers the method for
        its selection. Two most popular data-driven methods of bandwidth selection that have
        desirable properties are *least-squares cross-validation* (`cv_ls`) and the *AIC-based*
        method of *Hurvich et al. (1998)*, which is based on minimizing a modified
        *Akaike Information Criterion* (`aic`):

            **Cross-Validation Least-Squares**: determination of the optimal kernel bandwidth for
            kernel regression is based on minimizing

            .. math::

                CV(h) = n^{-1} \sum_{i=1}^{n}(Y_i - g_{-i}(X_i))^2,

            where :math:`g_{-i}(X_i)` is the estimator of :math:`g(X_i)` formed by leaving out the
            *i-th* observation when generating the prediction for observation *i*.

            **Hurvich et al.'s** (1998) approach is based on the minimization of

            .. math::

                AIC_c = ln(\sigma^2) + ((1 + tr(H) / n) / (1 - (tr(H) + 2) / n),

            where

            .. math::

                \sigma^2  = 1 / n \sum_{i=1}^{n}(Y_i - g(X_i))^2 = Y'(I - H)'(I - H)Y / n

            with :math:`g(X_i)` being a non-parametric regression estimator and *H* being an *n x n*
            matrix of kernel weights with its *(i, j)-th* element given by
            :math:`H_{ij} = K_h(X_i, X_j) / \sum_{l=1}^{n} K_h(X_i, X_l)`, where :math:`K_h(*)`
            is a generalized product kernel.

        Both methods for kernel bandwidth selection the *least-squared cross-validation* and the
        *AIC* have been shown to be asymptotically equivalent.

    .. _EstimatorSettings: https://www.statsmodels.org/dev/generated/statsmodels.nonparametric.
            kernel_density.EstimatorSettings.html
    .. _StatsModels: https://www.statsmodels.org/dev/generated/statsmodels.nonparametric.
            kernel_regression.KernelReg.html#statsmodels.nonparametric.kernel_regression.KernelReg

    The remaining options at this mode of kernel regression postprocessor are described within usage
    from the CLI and you can see this in the list below. All these options are parameters to
    *EstimatorSettings* (see EstimatorSettings_), that optimizing the kernel bandwidth based on the
    these specified settings.

    In the case of confusion about this approach of kernel regression, you can visit StatsModels_.
    """
    assert ctx.parent is not None and f"impossible happened: {ctx} has no parent"
    # update the current set of params with the selected mode of kernel regression
    kwargs.update({"kernel_mode": "estimator-settings"})
    # update the current set of params with the params entered at `kernel regression` command
    kwargs.update(ctx.parent.params)
    runner.run_postprocessor_on_profile(ctx.obj, "kernel_regression", kwargs)


@click.command(name="user-selection")
@click.option(
    "--reg-type",
    "-rt",
    type=click.Choice(_REGRESSION_ESTIMATORS),
    default=_REGRESSION_ESTIMATORS[0],
    help=(
        'Provides the type for regression estimator. Supported types are: "lc": '
        'local-constant (Nadaraya-Watson) and "ll": local-linear estimator. Default is '
        '"ll". For more information about these types you can visit '
        "Perun Documentation."
    ),
)
@click.option(
    "--bandwidth-value",
    "-bv",
    type=click.FloatRange(min=1e-10, max=None),
    required=True,
    help="The float value of <bandwidth> defined by user, which will be used at kernel regression.",
)
@click.pass_context
def user_selection(ctx: click.Context, **kwargs: Any) -> None:
    """
    Nadaraya-Watson kernel regression with user bandwidth.

    This mode of kernel regression postprocessor is very similar to *estimator-settings* mode. Also
    offers two types of *regression estimator* <reg-type> and that the *Nadaraya-Watson* estimator,
    so known as *local-constant* (`lc`) and the *local-linear* estimator (`ll`). Details about these
    estimators are available in :ref:`postprocessors-kernel-regression-estimator_settings`. In
    contrary to this mode, which selected a kernel bandwidth using the *EstimatorSettings* and
    chosen parameters, in this mode the user itself selects a kernel bandwidth <bandwidth-value>.
    This value will be used to execute the kernel regression. The value of kernel bandwidth in the
    resulting estimate may change occasionally, specifically in the case, when the bandwidth value
    is too low to execute the kernel regression. Then will be a bandwidth value approximated to the
    closest appropriate value, so that is not decreased the accuracy of the resulting estimate.
    """
    assert ctx.parent is not None and f"impossible happened: {ctx} has no parent"
    # update the current set of params with the selected mode of kernel regression
    kwargs.update({"kernel_mode": "user-selection"})
    # update the current set of params with the params entered at `kernel regression` command
    kwargs.update(ctx.parent.params)
    runner.run_postprocessor_on_profile(ctx.obj, "kernel_regression", kwargs)


@click.command(name="method-selection")
@click.option(
    "--reg-type",
    "-rt",
    type=click.Choice(_REGRESSION_ESTIMATORS),
    default=_REGRESSION_ESTIMATORS[0],
    help=(
        'Provides the type for regression estimator. Supported types are: "lc": '
        'local-constant (Nadaraya-Watson) and "ll": local-linear estimator. Default is '
        '"ll". For more information about these types you can visit '
        "Perun Documentation."
    ),
)
@click.option(
    "--bandwidth-method",
    "-bm",
    type=click.Choice(methods.BW_SELECTION_METHODS),
    default=methods.BW_SELECTION_METHODS[0],
    help=(
        "Provides the helper method to determine the kernel bandwidth. The "
        "<method_name> will be used to compute the bandwidth, which will be "
        "used at kernel regression."
    ),
)
@click.pass_context
def method_selection(ctx: click.Context, **kwargs: Any) -> None:
    r"""
    Nadaraya-Watson kernel regression with supporting bandwidth selection method.

    The last method from a group of three methods based on a similar principle. *Method-selection*
    mode offers the same type of *regression estimators* <reg-type> as the first two described
    methods. The first supported option is `ll`, which represents the *local-linear* estimator.
    *Nadaraya-Watson* or *local constant* estimator represents the second option for <reg-type>
    parameter. The more detailed description of these estimators is located in
    :ref:`postprocessors-kernel-regression-estimator_settings`. The difference between this mode
    and the two first modes is in the way of determination of a kernel bandwidth. In this mode are
    offered two methods to determine bandwidth. These methods try calculated an optimal bandwidth
    from predefined formulas:

        **Scotts's Rule** of thumb to determine the smoothing bandwidth for a kernel estimation. It
        is very fast compute. This rule was designed for density estimation but is usable for kernel
        regression too. Typically, produces a larger bandwidth, and therefore it is useful for
        estimating a gradual trend:

            .. math::

                bw = 1.059 * A * n^{-1/5},

            where *n* marks the length of X variable <per-key> and

            .. math::

                A = min(\sigma(x), IQR(x) / 1.349),

            .. _InterquartileRange: https://en.wikipedia.org/wiki/Interquartile_range
            .. _StandardDeviation: https://en.wikipedia.org/wiki/Standard_deviation

            where :math:`\sigma` marks the StandardDeviation_ and IQR marks the InterquartileRange_.

        **Silverman's Rule** of thumb to determine the smoothing bandwidth for a kernel estimation.
        Belongs to most popular method which uses the *rule-of-thumb*. Rule is originally designs
        for *density estimation* and therefore uses the normal density as a prior for approximating.
        For the necessary estimation of the :math:`\sigma` of X <per-key> he proposes a robust
        version making use of the InterquartileRange_. If the true density is uni-modal, fairly
        symmetric and does not have fat tails, it works fine:

            .. math::

                bw = 0.9 * A * n^{-1/5},

            where *n* marks the length of X variable <per-key> and

            .. math::

                A = min(\sigma(x), IQR(x) / 1.349),

            .. _InterquartileRange: https://en.wikipedia.org/wiki/Interquartile_range
            .. _StandardDeviation: https://en.wikipedia.org/wiki/Standard_deviation

            where :math:`\sigma` marks the StandardDeviation_ and IQR marks the InterquartileRange_.
    """
    assert ctx.parent is not None and f"impossible happened: {ctx} has no parent"
    # update the current set of params with the selected mode of kernel regression
    kwargs.update({"kernel_mode": "method-selection"})
    # update the current set of params with the params entered at `kernel regression` command
    kwargs.update(ctx.parent.params)
    runner.run_postprocessor_on_profile(ctx.obj, "kernel_regression", kwargs)


@click.command(name="kernel-smoothing")
@click.option(
    "--kernel-type",
    "-kt",
    type=click.Choice(_KERNEL_TYPES),
    default=_KERNEL_TYPES[0],
    help=(
        "Provides the set of kernels to execute the `kernel-smoothing` with kernel "
        "selected by the user. For exact definitions of these kernels and more "
        "information about it, you can visit the Perun Documentation."
    ),
)
@click.option(
    "--smoothing-method",
    "-sm",
    type=click.Choice(_SMOOTHING_METHODS),
    default=_SMOOTHING_METHODS[0],
    help=(
        "Provides kernel smoothing methods to executing non-parametric regressions: "
        "`local-polynomial` perform a local-polynomial regression in N-D using a "
        "user-provided kernel; `local-linear` perform a local-linear regression using a"
        " gaussian (normal) kernel; and `spatial-average` perform a Nadaraya-Watson "
        "regression on the data (so called local-constant regression) using a "
        "user-provided kernel."
    ),
)
@click.option(
    "--bandwidth-method",
    "-bm",
    type=click.Choice(methods.BW_SELECTION_METHODS),
    default=methods.BW_SELECTION_METHODS[0],
    help=(
        "Provides the helper method to determine the kernel bandwidth. The "
        "<bandwidth_method> will be used to compute the bandwidth, which will be used "
        "at kernel-smoothing regression. Cannot be entered in combination with "
        "<bandwidth-value>, then will be ignored and will be accepted value from "
        "<bandwidth-value>."
    ),
)
@click.option(
    "--bandwidth-value",
    "-bv",
    type=click.FloatRange(min=1e-10, max=None),
    help=(
        "The float value of <bandwidth> defined by user, which will be used at "
        "kernel regression. If is entered in the combination with <bandwidth-method>, "
        "then method will be ignored."
    ),
)
@click.option(
    "--polynomial-order",
    "-q",
    type=click.IntRange(min=1, max=None),
    default=_DEFAULT_POLYNOMIAL_ORDER,
    help=(
        "Provides order of the polynomial to fit. Default value of the order is equal "
        "to 3. Is accepted only by `local-polynomial` <smoothing-method>, another "
        "methods ignoring it."
    ),
)
@click.pass_context
def kernel_smoothing(ctx: click.Context, **kwargs: Any) -> None:
    r"""
    Kernel regression with different types of kernel and regression methods.

    This mode of kernel regression postprocessor implements non-parametric regression using
    different kernel methods and different kernel types. The calculation in this mode can be split
    into three parts. The first part is represented by the *kernel type*, the second part by
    *bandwidth computation* and the last part is represented by *regression method*, which will be
    used to interleave the given resources. We will look gradually at individual supported options
    in the each part of computation.

        **Kernel Type <kernel-type>**:

        In non-parametric statistics a *kernel* is a weighting function used in estimation
        techniques. In *kernel regression* is used to estimate the conditional expectation of a
        random variable. As has been said, *kernel width* must be specified when running a
        non-parametric estimation. The *kernel* in view of mathematical definition is a
        non-negative real-valued integrable function *K*. For most applications, it is desirable
        to define the function to satisfy two additional requirements:

            **Normalization**:

                .. math::

                    \int_{-\infty}^{+\infty}K(u)du = 1,



            **Symmetry**

                .. math::

                    K(-u) = K(u),

            for all values of u. The second requirement ensures that the average of the
            corresponding distribution is equal to that of the sample used. If *K* is a kernel,
            then so is the function :math:`K^*` defined by :math:`K^*(u) = \lambda K (\lambda u)`,
            where :math:`\lambda > 0`. This can be used to select a scale that is appropriate for
            the data. This mode offers several types of kernel functions:

        +-------------------------+--------------------------------------------+----------------+
        | **Kernel Name**         | **Kernel Function, K(u)**                  | **Efficiency** |
        +-------------------------+--------------------------------------------+----------------+
        | **Gaussian (normal)**   | :math:`K(u)=(1/\sqrt{2\pi})e^{-(1/2)u^2}`  | 95.1%          |
        +-------------------------+--------------------------------------------+----------------+
        | **Epanechnikov**        | :math:`K(u)=3/4(1-u^2)`                    | 100%           |
        +-------------------------+--------------------------------------------+----------------+
        | **Tricube**             | :math:`K(u)=70/81(1-|u^3|)^3`              | 99.8%          |
        +-------------------------+--------------------------------------------+----------------+
        | **Gaussian order4**     | :math:`\phi_4(u)=1/2(3-u^2)\phi(u)`,       | not applicable |
        |                         | where :math:`\phi` is the normal kernel    |                |
        +-------------------------+--------------------------------------------+----------------+
        | **Epanechnikov order4** | :math:`K_4(u)=-(15/8)u^2+(9/8)`, where *K* | not applicable |
        |                         | is the non-normalized Epanechnikov kernel  |                |
        +-------------------------+--------------------------------------------+----------------+

        Efficiency is defined as :math:`\sqrt{\int{}{}u^2K(u)du}\int{}{}K(u)^2du`, and
        its measured to the *Epanechnikov* kernel.

        **Smoothing Method <smoothing-method>**:

        *Kernel-Smoothing* mode of this postprocessor offers three different non-parametric
        regression methods to execute *kernel regression*. The first of them is called
        *spatial-average* and perform a *Nadaraya-Watson* regression (i.e. also called
        local-constant regression) on the data using a given kernel:

                .. math::

                    m_{h}(x) = \sum_{i=1}^{n}K_h((x-x_i)/h)y_i/\sum_{j=1}^{n}K_h((x-x_j) / h),

        where *K(x)* is the kernel and must be such that *E(K(x)) = 0* and *h* is the bandwidth of
        the method. *Local-Constant* regression was also described in
        :ref:`postprocessors-kernel-regression-estimator_settings`. The second supported regression
        method by this mode is called *local-linear*. Compared with previous method, which offers
        computational with different types of kernel, this method has restrictions and perform
        *local-linear* regression using only *Gaussian (Normal)* kernel. The *local-constant*
        regression was described in :ref:`postprocessors-kernel-regression-estimator_settings` and
        therefore will not be given no further attention to it. *Local Polynomial* regression is
        the last method in this mode and perform regression in *N-D* using a user-provided kernel.
        The *local-polynomial* regression is the function that minimizes, for each position:

            .. math::

                m_{h}(x) = \sum_{i=0}^{n}K((x - x_i) / h)(y_i - a_0 - P_q(x_i -x))^2,

        where *K(x)* is the kernel such that *E(K(x)) = 0*, *q* is the order of the fitted
        polynomial <polynomial-order>, :math:`P_q(x)` is a polynomial or order *q* in *x*, and *h*
        is the bandwidth of the method. The polynomial :math:`P_q(x)` is of the form:

            .. math::

                F_d(k) = { n \in N^d | \sum_{i=1}^{d}n_i = k }

            .. math::

                P_q(x_1, ..., x_d) = \sum_{k=1}^{q}{}\sum_{n \in F_d(k)}^{}{}
                        a_{k,n}\prod_{i=1}^{d}x_{i}^{n_i}

        For example we can have:

            .. math::

                P_2(x, y) = a_{110}x + a_{101}y + a_{220}x^2 + a_{221}xy + a_{202}y^2

    The last part of the calculation is the *bandwidth* computation. This mode offers to user enter
    the value directly with use of parameter <bandwidth-value>. The parameter <bandwidth-method>
    offers to user the selection from the two methods to determine the optimal bandwidth value.
    The supported methods are *Scotts's Rule* and *Silverman's Rule*, which are described in
    :ref:`postprocessors-kernel-regression-method_selection`. This parameter cannot be entered in
    combination with <bandwidth-value>, then will be ignored and will be accepted value from
    <bandwidth-value>.
    """
    assert ctx.parent is not None and f"impossible happened: {ctx} has no parent"
    # update the current set of params with the selected mode of kernel regression
    kwargs.update({"kernel_mode": "kernel-smoothing"})
    # update the current set of params with the params entered at `kernel regression` command
    kwargs.update(ctx.parent.params)
    runner.run_postprocessor_on_profile(ctx.obj, "kernel_regression", kwargs)


@click.command(name="kernel-ridge")
@click.option(
    "--gamma-range",
    "-gr",
    type=click.FLOAT,
    nargs=2,
    default=_DEFAULT_GAMMA_RANGE,
    callback=methods.valid_range_values,
    help=(
        "Provides the range for automatic bandwidth selection of the kernel via "
        "leave-one-out cross-validation. One value from these range will be selected "
        "with minimizing the mean-squared error of leave-one-out cross-validation. The "
        "first value will be taken as the lower bound of the range and cannot be "
        "greater than the second value."
    ),
)
@click.option(
    "--gamma-step",
    "-gs",
    type=click.FloatRange(min=1e-10, max=None),
    default=_DEFAULT_GAMMA_STEP,
    help=(
        "Provides the size of the step, with which will be executed the iteration over "
        "the given <gamma-range>. Cannot be greater than length of <gamma-range>, else "
        "will be set to value of the lower bound of the <gamma_range>."
    ),
)
@click.pass_context
def kernel_ridge(ctx: click.Context, **kwargs: Any) -> None:
    """
    Nadaraya-Watson kernel regression with automatic bandwidth selection.

    .. _K-fold: https://medium.com/datadriveninvestor/k-fold-cross-validation-6b8518070833
    .. _mean-squared-error: https://en.wikipedia.org/wiki/Mean_squared_error

    This mode implements *Nadaraya-Watson* kernel regression, which was described above in
    :ref:`postprocessors-kernel-regression-estimator_settings`. While the previous modes provided
    the methods to determine the optimal bandwidth with different ways, this method provides a
    little bit different way. From a given range of potential bandwidths <gamma-range> try to
    select the optimal kernel bandwidth with use of *leave-one-out cross-validation*. This approach
    was described in :ref:`postprocessors-kernel-regression-estimator_settings`, where was
    introduced the *least-squares cross-validation* and it is a modification of this approach.
    *Leave-one-out cross validation* is K-fold_ cross validation taken to its logical extreme, with
    *K* equal to *N*, the number of data points in the set. The original *gamma-range* will be
    divided on the base of size the given step <gamma-step>. The selection of specific value from
    this range will be executing by minimizing mean-squared-error_ in
    *leave-one-out cross-validation*. The selected *bandwidth-value* will serves for *gaussian*
    kernel in resulting estimate: :math:`K(x, y) = exp(-gamma * ||x-y||^2)`.
    """
    assert ctx.parent is not None and f"impossible happened: {ctx} has no parent"
    # validation of the step size - must be smaller than the length of the given range
    methods.valid_step_size(kwargs["gamma_step"], kwargs["gamma_range"])
    # update the current set of params with the selected mode of kernel regression
    kwargs.update({"kernel_mode": "kernel-ridge"})
    # update the current set of params with the params entered at `kernel regression` command
    kwargs.update(ctx.parent.params)
    runner.run_postprocessor_on_profile(ctx.obj, "kernel_regression", kwargs)


@click.group(invoke_without_command=True)
@cli_kit.resources_key_options
@click.pass_context
def kernel_regression(ctx: click.Context, **_: Any) -> None:
    """
    Execution of the interleaving of profiles resources by *kernel* models.

    \b
      * **Limitations**: `none`
      * **Dependencies**: `none`

    In statistics, the kernel regression is a non-parametric approach to estimate the
    conditional expectation of a random variable. Generally, the main goal of this approach
    is to find non-parametric relation between a pair of random variables X <per-key> and
    Y <of-key>. Different from parametric techniques (e.g. linear regression), kernel
    regression does not assume any underlying distribution (e.g. linear, exponential, etc.)
    to estimate the regression function. The main idea of kernel regression is putting the
    **kernel**, that have the role of weighted function, to each observation point in the dataset.
    Subsequently, the kernel will assign weight to each point in depends on the distance from the
    current data point. The kernel basis formula depends only on the *bandwidth* from the current
    ('local') data point X to a set of neighboring data points X.

        **Kernel Selection** does not important from an asymptotic point of view. It is appropriate
        to choose the **optimal** kernel since this group of the kernels are continuously on the
        whole definition field and then the estimated regression function inherit smoothness of
        the kernel. For example, a suitable kernels can be the **epanechnikov** or **normal**
        kernel. This postprocessor offers the **kernel selection** in the **kernel-smoothing**
        mode, where are available five different types of kernels. For more information about these
        kernels or this kernel regression mode you can see
        :ref:`postprocessors-kernel-regression-kernel_smoothing`.

        **Bandwidth Selection** is the most important factor at each approach of kernel regression,
        since this value significantly affects the smoothness of the resulting estimate. In case,
        when we choose the inappropriate value, in the most cases can be expected the following two
        situations. The **small** bandwidth value reproduce estimated data and vice versa, the
        **large** value leads to over-leaving, so to average of the estimated data. Therefore, are
        used the methods to determine the bandwidth value. One of the most widespread and most
        commonly used methods is the **cross-validation** method. This method is based on the
        estimate of the regression function in which will be omitted *i-th* observation. In this
        postprocessor is this method available in the **estimator-setting** mode. Another methods
        to determine the bandwidth, which are available in the remaining modes of this postprocessor
        are **scott** and **silverman** method. More information about these methods and its
        definition you cas see in the part :ref:`postprocessors-kernel-regression-method_selection`.

    This postprocessor in summary offers five different modes, which does not differ in the
    resulting estimate, but in the way of computation the resulting estimate. Better said, it
    means, that the result of each mode is the **kernel estimate** with relevant parameters,
    selected according to the concrete mode. In short, we will describe the individual methods, for
    more information about it, you can visit the relevant parts of documentation:

        | * **Estimator-Settings**: Nadaraya-Watson kernel regression with specific settings
                for estimate
        | * **User-Selection**: Nadaraya-Watson kernel regression with user bandwidth
        | * **Method-Selection**: Nadaraya-Watson kernel regression with supporting bandwidth
                selection method
        | * **Kernel-Smoothing**: Kernel regression with different types of kernel and
                regression methods
        | * **Kernel-Ridge**: Nadaraya-Watson kernel regression with automatic bandwidth selection

    For more details about this approach of non-parametric analysis refer
    to :ref:`postprocessors-kernel-regression`.
    """
    # running default mode with use EstimatorSettings and its default parameters
    if ctx.invoked_subcommand is None:
        ctx.invoke(kernel_smoothing)


# Supported modes at executing kernel regression:
# - estimator-settings: with use EstimatorSettings and its arguments
# - user-selection: bandwidth defined by user itself
# - bandwidth_methods: bandwidth computed by helper method for its determine
# - kernel-smoothing: provides the ability to choose a kernel and other methods
# - kernel-ridge: set bandwidth by minimizing MSE in leave-one-out cross validation from given range
_SUPPORTED_MODES = [
    estimator_settings,
    user_selection,
    method_selection,
    kernel_smoothing,
    kernel_ridge,
]
# addition of sub-commands (supported modes) to main command represents by kernel_regression
for mode in _SUPPORTED_MODES:
    kernel_regression.add_command(mode)
