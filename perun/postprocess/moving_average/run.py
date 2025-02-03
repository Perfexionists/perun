"""
Postprocessor module with non-parametric analysis using the moving average methods.
"""

from __future__ import annotations

# Standard Imports
from typing import Callable, TYPE_CHECKING, Any
import functools

# Third-Party Imports
import click

# Perun Imports
from perun.logic import runner
from perun.postprocess.moving_average import methods
from perun.postprocess.regression_analysis import data_provider, tools
from perun.utils.common import cli_kit
from perun.utils.structs.common_structs import PostprocessStatus

if TYPE_CHECKING:
    from perun.profile.factory import Profile


# set the labels at the center of the window as default
_DEFAULT_CENTER: bool = True
# default computational method - Simple Moving Average
_DEFAULT_MOVING_METHOD: str = "sma"
# specify decay in terms of Center of Mass (com) as default
_DEFAULT_DECAY: tuple[str, int] = ("com", 0)
# default statistic function to compute - mean/average
_DEFAULT_STATISTIC: str = "mean"
# recognized window types for Simple Moving Average/Median
_WINDOW_TYPES: list[str] = [
    "boxcar",
    "triang",
    "blackman",
    "hamming",
    "bartlett",
    "parzen",
    "bohman",
    "blackmanharris",
    "nuttall",
    "barthann",
]


def postprocess(
    profile: Profile, **configuration: Any
) -> tuple[PostprocessStatus, str, dict[str, Any]]:
    """
    Invoked from perun core, handles the postprocess actions

    :param profile: the profile to analyze
    :param configuration: the perun and options context
    """
    # Perform the non-parametric analysis using the moving average methods
    moving_average_models = methods.compute_moving_average(
        data_provider.generic_profile_provider(profile, **configuration), configuration
    )

    # Return the profile after the execution of moving average method
    return (
        PostprocessStatus.OK,
        "",
        {"profile": tools.add_models_to_profile(profile, moving_average_models)},
    )


def common_sma_options(
    func_obj: Callable[..., Any],
) -> Callable[[click.Context, click.Option, Any], Any]:
    """
    The wrapper of common options for both supported commands represents simple
    moving average methods: Simple Moving Average and Simple Moving Average Median.

    :param func_obj: the function in which the decorator of common options is applied
    :return: returns sequence of the single options for the current function (f) as decorators
    """
    options = [
        click.option(
            "--window_width",
            "-ww",
            type=click.IntRange(min=1, max=None),
            help=(
                "Size of the moving window. This is a number of observations used "
                "for calculating the statistic. Each window will be a fixed size."
            ),
        ),
        click.option(
            "--center/--no-center",
            default=_DEFAULT_CENTER,
            help=(
                "If set to False, the result is set to the right edge of the "
                "window, else is result set to the center of the window"
            ),
        ),
    ]
    return functools.reduce(lambda x, option: option(x), options, func_obj)


@click.command(name="sma")
@click.option(
    "--window_type",
    "-wt",
    type=click.Choice(_WINDOW_TYPES),
    help=(
        "Provides the window type, if not set then all points are evenly weighted. "
        "For further information about window types see the notes in the documentation."
    ),
)
@common_sma_options
@click.pass_context
def simple_moving_average(ctx: click.Context, **kwargs: Any) -> None:
    """**Simple Moving Average**

    In the most of cases, it is an unweighted Moving Average, this means that the each
    x-coordinate in the data set (profiled resources) has equal importance and is weighted
    equally. Then the `mean` is computed from the previous `n data` (`<no-center>`), where the
    `n` marks `<window-width>`. However, in science and engineering the mean is normally taken
    from an equal number of data on either side of a central value (`<center>`). This ensures
    that variations in the mean are aligned with the variations in the mean are aligned with
    variations in the data rather than being shifted in the x-axis direction. Since the window
    at the boundaries of the interval does not contain enough count of points usually, it is
    necessary to specify the value of `<min-periods>` to avoid the NaN result. The role of the
    weighted function in this approach belongs to `<window-type>`, which represents the suite
    of the following window functions for filtering:

        | - **boxcar**: known as rectangular or Dirichlet window, is equivalent to no window
                at all: --
        | - **triang**: standard triangular window
        | - **blackman**: formed by using three terms of a summation of cosines, minimal
                leakage, close to optimal
        | - **hamming**: formed by using a raised cosine with non-zero endpoints, minimize the
                nearest side lobe
        | - **bartlett**: similar to triangular, endpoints are at zero, processing of tapering
                data sets
        | - **parzen**: can be regarded as a generalization of k-nearest neighbor techniques
        | - **bohman**: convolution of two half-duration cosine lobes
        | - **blackmanharris**: minimum in the sense that its maximum side lobes are minimized
                (symmetric 4-term)
        | - **nuttall**: minimum 4-term Blackman-Harris window according to Nuttall
                (so called 'Nuttall4c')
        | - **barthann**: has a main lobe at the origin and asymptotically decaying side lobes
                on both sides
        | - **kaiser**: formed by using a Bessel function, needs beta value
                (set to 14 - good starting point)

        .. _SciPyWindow: https://docs.scipy.org/doc/scipy/reference/signal.windows.
                html#module-scipy.signal.windows

        For more details about this window functions or for their visual view you can
        see SciPyWindow_.
    """
    assert ctx.parent is not None and f"impossible happened: {ctx} has no parent"
    kwargs.update({"moving_method": "sma"})
    kwargs.update(ctx.parent.params)
    runner.run_postprocessor_on_profile(ctx.obj, "moving_average", kwargs)


@click.command(name="smm")
@common_sma_options
@click.pass_context
def simple_moving_median(ctx: click.Context, **kwargs: Any) -> None:
    """**Simple Moving Median**

    The second representative of Simple Moving Average methods is the Simple Moving **Median**.
    For this method are applicable to the same rules as in the first described method, except
    for the option for choosing the window type, which do not make sense in this approach. The
    only difference between these two methods are the way of computation the values in the
    individual sub-intervals. Simple Moving **Median** is not based on the computation of
    average, but as the name suggests, it based on the **median**.
    """
    assert ctx.parent is not None and f"impossible happened: {ctx} has no parent"
    kwargs.update({"moving_method": "smm"})
    kwargs.update(ctx.parent.params)
    runner.run_postprocessor_on_profile(ctx.obj, "moving_average", kwargs)


@click.command(name="ema")
@click.option(
    "--decay",
    "-d",
    callback=methods.validate_decay_param,
    default=_DEFAULT_DECAY,
    type=click.Tuple([click.Choice(methods.get_supported_decay_params()), float]),
    help=(
        'Exactly one of "com", "span", "halflife", "alpha" can be provided. Allowed '
        "values and relationship between the parameters are specified in the "
        "documentation (e.g. --decay=com 3)."
    ),
)
@click.pass_context
def exponential_moving_average(ctx: click.Context, **kwargs: Any) -> None:
    """**Exponential Moving Average**

    This method is a type of moving average methods, also known as **Exponential** Weighted
    Moving Average, that places a greater weight and significance on the most recent data
    points. The weighting for each far x-coordinate decreases exponentially and never reaching
    zero. This approach of moving average reacts more significantly to recent changes than a
    *Simple* Moving Average, which applies an equal weight to all observations in the period.
    To calculate an EMA must be first computing the **Simple** Moving Average (SMA) over a
    particular sub-interval. In the next step must be calculated the multiplier for smoothing
    (weighting) the EMA, which depends on the selected formula, the following options are
    supported (`<decay>`):

        | - **com**: specify decay in terms of center of mass:
                :math:`{\\alpha}` = 1 / (1 + com), for com >= 0
        | - **span**: specify decay in terms of span:
                :math:`{\\alpha}` = 2 / (span + 1), for span >= 1
        | - **halflife**: specify decay in terms of half-life,
                :math:`{\\alpha}` = 1 - exp(log(0.5) / halflife), for halflife > 0
        | - **alpha**: specify smoothing factor
                :math:`{\\alpha}` directly: 0 < :math:`{\\alpha}` <= 1

    The computed coefficient :math:`{\\alpha}` represents the degree of weighting decrease, a
    constant smoothing factor, The higher value of :math:`{\\alpha}` discounts older
    observations faster, the small value to the contrary. Finally, to calculate the current
    value of EMA is used the relevant formula. It is important do not confuse **Exponential**
    Moving Average with **Simple** Moving Average. An **Exponential** Moving Average behaves
    quite differently from the second mentioned method, because it is the function of weighting
    factor or length of the average.
    """
    assert ctx.parent is not None and f"impossible happened: {ctx} has no parent"
    kwargs.update(
        {
            "moving_method": "ema",
            "window_width": kwargs["decay"][1],
            "decay": kwargs["decay"][0],
        }
    )
    kwargs.update(ctx.parent.params)
    runner.run_postprocessor_on_profile(ctx.obj, "moving_average", kwargs)


@click.group(invoke_without_command=True)
@click.option(
    "--min_periods",
    "-mp",
    type=click.IntRange(min=1, max=None),
    help=(
        "Provides the minimum number of observations in window required to have a value."
        " If the number of possible observations smaller then result is NaN."
    ),
)
@cli_kit.resources_key_options
@click.pass_context
def moving_average(ctx: click.Context, **_: Any) -> None:
    """
    Execution of the interleaving of profiled resources by *moving average* models.

    \b
      * **Limitations**: `none`
      * **Dependencies**: `none`

    Moving average methods are the natural generalizations of regressogram method. This
    method uses the local averages/medians of y-coordinates (`<of_resource_key>`), but
    the estimate in the x-point (`<per_key>`) is based on the centered surroundings of
    these points, more precisely:

        **Moving Average**: is a widely used estimator in the technical analysis, that helps
        smooth the dataset by filtering out the 'noise'. Among the basic properties of these
        methods belongs the ability to reduce the effect of temporary variations in data, better
        improvement of the fitness of data to a line, so-called smoothing, to show the data's
        trend more clearly and highlight any value below or above the trend. The most important
        task with this type of non-parametric approach is the choice of the `<window-width>`.
        If the user does not choose it, we try approximate this value by using the value of
        `coefficient of determination` (:math:`R^2`). At the beginning, of the analysis is set the
        initial value of window width and then follows the interleaving of the current dataset,
        which runs until the value of `coefficient of determination` will not reach the required
        level. By this way is guaranteed the desired smoothness of the resulting models. The two
        basic and commonly used `<moving-methods>` are the **simple** moving average (**sma**) and
        the *exponential* moving average (**ema**).

    For more details about this approach of non-parametric analysis refer
    to :ref:`postprocessors-moving-average`.
    """
    # run default simple moving average command
    if ctx.invoked_subcommand is None:
        ctx.invoke(simple_moving_average)


# supported methods of moving average postprocessor
_SUPPORTED_METHODS = [
    simple_moving_average,
    simple_moving_median,
    exponential_moving_average,
]
# addition of sub-commands to main command represents by moving average postprocessor
for method in _SUPPORTED_METHODS:
    moving_average.add_command(method)
