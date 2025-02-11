"""Module with graphs creation and configuration functions."""

from __future__ import annotations

# Standard Imports
from collections.abc import Iterator
from operator import itemgetter
from typing import TYPE_CHECKING, Any

# Third-Party Imports
from bokeh import palettes
import holoviews as hv
import numpy as np

# Perun Imports
from perun.postprocess.regression_analysis import data_provider
from perun.profile import query, convert
from perun.utils.common import view_kit

if TYPE_CHECKING:
    import numpy.typing as npt
    import pandas as pd

    from perun.profile.factory import Profile


ProfileModel = dict[str, Any]
ProfileModels = list[ProfileModel]


def create_from_params(
    profile: Profile,
    of_key: str,
    per_key: str,
    x_axis_label: str,
    y_axis_label: str,
    graph_title: str,
) -> Iterator[tuple[str, hv.Scatter]]:
    """Creates Scatter plot graph according to the given parameters.

    The 'of_key' is a data column (Y-axis) that is depending on the values of 'per_key' (X-axis).
    Furthermore, models records are also plotted if the profile contains them.

    :param profile: a Perun profile.
    :param of_key: the data column (Y-axis) key.
    :param per_key: the X-axis values column key.
    :param x_axis_label: X-axis label text.
    :param y_axis_label: Y-axis label text
    :param graph_title: title of the graph.
    :returns: UID and a Scatter plot with models, if there are any.
    """
    view_kit.lazy_init_holoviews()

    y_axis_label = view_kit.add_y_units(profile["header"], of_key, y_axis_label)
    for data_slice, models_slice in _generate_plot_data_slices(profile):
        # Plot the points as a scatter plot
        scatter = hv.Scatter(data_slice, (per_key, x_axis_label), (of_key, y_axis_label))
        # Add models to the plot, if there are any
        scatter *= _draw_models(profile, models_slice)

        # Create the graph title as a combination of default parameter, uid, method and
        # interval values (only if models are plotted) for easier identification
        graph_title = f"{graph_title}; uid: {data_slice.uid.values[0]}"
        if models_slice:
            graph_title += (
                f";method {models_slice[0]['model']}; "
                f"interval [{models_slice[0]['x_start']}, {models_slice[0]['x_end']}]"
            )

        # Configure the plot's visual properties
        scatter.opts(
            hv.opts.Scatter(
                title=graph_title,
                tools=["zoom_in", "zoom_out", "hover"],
                responsive=True,
                fill_color="indianred",
                line_width=1,
                line_color="black",
                size=7,
            ),
            hv.opts.Curve(
                # The max function is here so that when there are no models, the Cycle object
                # is initialized properly
                color=hv.Cycle(list(palettes.viridis(max(len(models_slice), 1)))),
                line_width=3.5,
            ),
        )

        yield f"{data_slice.uid.values[0]}", scatter


def _generate_plot_data_slices(
    profile: Profile,
) -> Iterator[tuple[pd.DataFrame, ProfileModels]]:
    """Generates data slices for plotting resources and models.

    The resources are split per UID and models are sliced per UID and interval.

    :param profile: a complete perun profile.
    :returns: slices of resources (per UID) and models (per UID and interval).
    """
    # Get resources for scatter plot points and models for curves
    resource_table = convert.resources_to_pandas_dataframe(profile)
    models = list(map(itemgetter(1), profile.all_models()))
    # Get unique uids from profile, each uid (and optionally interval) will have separate graph
    uids = map(convert.flatten, query.unique_resource_values_of(profile, "uid"))

    # Process each uid data
    for uid_slice, uid_models in _slice_resources_by_uid(resource_table, models, uids):
        # Slice the uid models according to different intervals (each interval is plotted
        # separately as it improves readability)
        if uid_models:
            for interval_models in _slice_models_by_interval(uid_models):
                yield uid_slice, interval_models
        else:
            # There are no models to plot
            yield uid_slice, []


def _slice_resources_by_uid(
    resources: pd.DataFrame,
    models: ProfileModels,
    uids: Iterator[str],
) -> Iterator[tuple[pd.DataFrame, ProfileModels]]:
    """Splits the resource tables and models into slices by the unique uids found in the resources.

    :param resources: the ``resources`` part of a profile, i.e., recorded performance data.
    :param models: the ``models`` part of a profile.
    :param uids: UIDs found in the profile.
    :returns: per-UID ``resources`` and ``models`` slices.
    """
    for uid in uids:
        # Slice only the plotted uid from the data table
        uid_slice = resources[resources.uid == uid]
        if uid_slice.size == 0 or uid_slice.shape[0] <= 1:
            # plotting one point does not work (it has no real usage anyway), fix later
            continue
        # Filter models for the given uid
        uid_models = [model for model in models if model["uid"] == uid]
        yield uid_slice, uid_models


def _slice_models_by_interval(models: ProfileModels) -> Iterator[ProfileModels]:
    """Splits profile models into slices according to their x-axis intervals.

    :param models: the models to split.
    :returns: model slices according to their x-axis intervals.
    """
    # Sort the models by intervals first to yield them in order
    models = sorted(models, key=itemgetter("x_start", "x_end"))
    # Separate the models into groups according to intervals
    intervals: dict[tuple[int, int], ProfileModels] = {}
    for model in models:
        intervals.setdefault((model["x_start"], model["x_end"]), []).append(model)
    # Yield the list of models with the same interval
    for interval_models in intervals.values():
        yield interval_models


def _draw_models(profile: Profile, models: ProfileModels) -> hv.Overlay:
    """Build models overlay that can be rendered in the scatter plot.

    :param profile: a complete Perun profile.
    :param models: models to plot.

    :returns: an overlay object with models to plot.
    """
    # Create an overlay object that will group the model curves
    curves = hv.Overlay()
    for model in models:
        if "coeffs" in model:
            # This is a parametric model, add it to the overlay
            curves *= _create_parametric_model(model)
        # Non-parametric models don't contain coefficients
        elif model["model"] == "regressogram":
            curves *= _create_regressogram_model(model)
        elif model["model"] in ("moving_average", "kernel_regression"):
            for curve in _create_non_param_model(profile, model):
                curves *= curve
    return curves


def _create_parametric_model(model: ProfileModel) -> hv.Curve:
    """Build a render object for a specific parametric model using its coefficients.

    :param model: the parametric model.

    :returns: a Curve plot element that represents the model.
    """
    # First transform the model type and coefficients into X and Y points that can be plotted
    model_conv = convert.plot_data_from_coefficients_of(model)
    # Create a Curve plot element that represents the model
    return hv.Curve((model_conv["plot_x"], model_conv["plot_y"]), label=_build_model_legend(model))


def _create_non_param_model(profile: Profile, model: ProfileModel) -> Iterator[hv.Curve]:
    """Build a render object for a moving average model according to its computed properties.

    :param model: the moving average model.
    :param profile: a Perun profile containing the model's X coordinates.
    :returns: Curve elements that represent the model.
    """
    params = {
        # TODO: obtain of_key from the "postprocess" entry in profile
        "of_key": "amount",
        "per_key": model["per_key"],
    }
    legend = _build_model_legend(model)
    # Obtain the x-coordinates with the required uid to pair with current model
    for x_pts, _, uid in data_provider.generic_profile_provider(profile, **params):
        if uid == model["uid"]:
            # Build the model
            yield hv.Curve(
                (sorted(x_pts), model.get("kernel_stats", model.get("bucket_stats"))),
                label=legend,
            )


def _create_regressogram_model(model: ProfileModel) -> hv.Curve:
    """Build a render object for a regressogram model according to its computed properties.

    :param model: the regressogram model.
    :returns: a Curve plot element that represents the model.
    """
    bucket_no = len(model["bucket_stats"])
    # Even division of the model interval by the number of buckets
    x_pts = np.linspace(model["x_start"], model["x_end"], num=bucket_no + 1)
    # Add the beginning of the first edge
    y_pts = np.append(model["y_start"], model["bucket_stats"])
    # Build the model
    return _render_step_function(x_pts, y_pts, legend=_build_model_legend(model))


def _render_step_function(
    x_pts: npt.NDArray[np.floating[Any]], y_pts: npt.NDArray[np.floating[Any]], legend: str
) -> hv.Curve:
    """Build regressogram's step lines according to given coordinates.

    :param x_pts: the x-coordinates for the line.
    :param y_pts: the y-coordinates for the line.
    :returns: a Curve element representing the step lines.
    """
    x_x = np.sort(list(x_pts) + list(x_pts))
    x_x = x_x[:-1]
    y_y = list(y_pts) + list(y_pts)
    y_y[::2] = y_pts
    y_y[1::2] = y_pts
    y_y = y_y[1:]
    return hv.Curve((x_x, y_y), label=legend)


def _build_model_legend(model: ProfileModel) -> str:
    """Creates a legend (label) for the given model.

    :param model: the model to create a legend for.

    :returns: a string representation of the model's legend.
    """
    if "coeffs" in model:
        # Create a legend for parametric model
        coeffs = ", ".join(f"{c['name']}={c['value']:f}" for c in model["coeffs"])
        return f"{model['model']}: {coeffs}, r^2={model['r_square']:.3f}"
    if model["model"] == "moving_average":
        # Create a legend for moving_average model
        return (
            f"{model['moving_method']}: window={model['window_width']}, R^2={model['r_square']:.3f}"
        )
    if model["model"] == "kernel_regression":
        # Create a legend for kernel model
        return f"{model['kernel_mode']}: bw={model['bandwidth']}, R^2={model['r_square']:f}"
    else:
        assert model["model"] == "regressogram"
        # Create a legend for regressogram model
        return (
            f"{model['model'][:3]}: buckets={len(model['bucket_stats'])}, "
            f"stat: {model['statistic_function']}, "
            f"R^2={model['r_square']:.3f}"
        )
