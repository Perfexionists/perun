"""The module contains common methods, which are use by three detection methods
(fast_check, linear_regression, polynomial_regression).

The module contains one general method, which controls the all logic of the detection.
This method is called by three other methods and its task is calculating the needed
metrics to check performance change between two profiles and obtaining required models from
these profiles. Module contains two other temporary methods, which are using by mentioned
general methods.
"""
from __future__ import annotations

# Standard Imports
from typing import Any, Callable, TYPE_CHECKING, Iterable, Optional

# Third-Party Imports
import numpy as np

# Perun Imports
from perun.check.methods import linear_regression, polynomial_regression, fast_check
from perun.postprocess.regression_analysis import regression_models
from perun.profile import query
from perun.utils.common import common_kit
from perun.utils.structs import (
    PerformanceChange,
    DegradationInfo,
    ModelRecord,
    ClassificationMethod,
)

if TYPE_CHECKING:
    from perun.profile.factory import Profile


SAMPLES: int = 1000

np.seterr(divide="ignore", invalid="ignore")


def create_filter_by_model(
    model_name: str,
) -> Callable[[dict[str, Any], dict[str, Any]], bool]:
    """Creates a filter w.r.t to given model_name

    Note this is to be used in get_filtered_best_models_of

    :param str model_name: name of the model, that will be filtered out
    :return: filter function that retrieves only models of given type
    """

    def filter_by_model(_: dict[str, Any], model: dict[str, Any]) -> bool:
        """Filters the models according to the model name

        :param dict _: dictionary with set of models
        :param dict model: filtered model of given uid
        :return: true if the given model is of the given type
        """
        return model["model"] == model_name

    return filter_by_model


def filter_by_r_square(model_map: dict[str, Any], model: dict[str, Any]) -> bool:
    """Filters the models according to the value of the r_square

    :param dict model_map: dictionary with found models
    :param dict model: filtered model of given uid
    :return: filter function that retrieves only the best model w.r.t r_square
    """
    return model_map[model["uid"]].r_square < model["r_square"]


def create_model_record(model: dict[str, Any]) -> ModelRecord:
    """
    Function transform model to ModelRecord.

    :param dict model: model for transformation
    :return ModelRecord: filled ModelRecord with model items
    """
    return ModelRecord(
        model["model"],
        model["r_square"],
        model["coeffs"][0]["value"] if model.get("coeffs") else model["bucket_stats"],
        model["coeffs"][1]["value"] if model.get("coeffs") else None,
        model["coeffs"][2]["value"] if len(model.get("coeffs", [])) == 3 else 0,
        model["x_start"],
        model["x_end"],
    )


def get_filtered_best_models_of(
    profile: Profile,
    group: str,
    model_filter: Optional[Callable[[dict[str, Any], dict[str, Any]], bool]] = filter_by_r_square,
) -> dict[str, ModelRecord]:
    """
    This function filters the models from the given profiles according to the given specification.

    A function maps the individual metrics from each model to map, according to
    their unique identification (UIDs). Models from the given profiles are filtered
    according to the required `group` and `model_filter`. The default filter is set to
    `filter_by_square`, which means, that function obtains the models which have
    the values of coefficient of determination. Models can be also filtered
    according to its type (e.g. linear, constant, etc.). The group of models
    represents the individual group of model kinds (currently parametric and
    nonparametric).

    :param Profile profile: dictionary of profile resources and stuff
    :param str group: name of the group of models kind (e.g. param, nonparam, both) to obtains
    :param function/None model_filter: filter function for models
    :returns: map of unique identifier of computed models to their best models
    """
    if model_filter is not None:
        best_model_map = {
            uid: ModelRecord("", 0.0, 0.0, 0.0, 0, 0, 0.0)
            for uid in query.unique_model_values_of(profile, "uid")
        }
        for _, model in profile.all_models(group=group):
            if model_filter(best_model_map, model):
                best_model_map[model["uid"]] = create_model_record(model)
        return {k: v for k, v in best_model_map.items() if v.r_square != 0.0}

    best_model_map = {}
    for _, model in profile.all_models(group=group):
        best_model_map[model["uid"] + model.get("model")] = create_model_record(model)
    return best_model_map


def get_function_values(model: ModelRecord) -> tuple[list[float], list[float]]:
    """Obtains the relevant values of dependent and independent variables according to
    the given profile, respectively its coefficients. On the base of the count of samples
    is interval divide into several parts and to them is computed relevant values of
    dependent variables.

    :param ModelRecord model: model with its required metrics (value of coefficient, type, ...)
    :returns: np_array (x-coordinates, y-coordinates)
    """
    model_handler = regression_models.MODEL_MAP[model.type]
    plotter = model_handler["transformations"]["plot_model"]

    array_x_pts = plotter["model_x"](
        model.x_start, model.x_end, SAMPLES, transform_by=common_kit.identity
    )

    if model.type == "quadratic":
        array_y_pts = plotter["model_y"](
            array_x_pts,
            model.b0,
            model.b1,
            model.b2,
            plotter["formula"],
            transform_by=common_kit.identity,
        )
    else:
        array_y_pts = plotter["model_y"](
            array_x_pts,
            model.b0,
            model.b1,
            plotter["formula"],
            model_handler["f_x"],
            transform_by=common_kit.identity,
        )

    return array_y_pts, array_x_pts


def general_detection(
    baseline_profile: Profile,
    target_profile: Profile,
    classification_method: ClassificationMethod = ClassificationMethod.PolynomialRegression,
) -> Iterable[DegradationInfo]:
    """The general method, which covers all detection logic. At the beginning obtains the pairs
    of the best models from the given profiles and the pairs of the linear models. Subsequently,
    are computed the needed statistics metrics, concretely relative and absolute error. According
    to the calling method is call the relevant classification method. After the return from this
    classification we know the type of occurred changes. In the last steps is determined
    information, which will be returned to users (i.e. confidence, change between models).

    :param Profile baseline_profile: baseline against which we are checking the degradation
    :param Profile target_profile: profile corresponding to the checked minor version
    :param ClassificationMethod classification_method: method used for actual classification of
        performance changes
    :returns: tuple (degradation result, degradation location, degradation rate, confidence)
    """

    # obtaining the needed models from both profiles
    best_baseline_models = get_filtered_best_models_of(baseline_profile, group="param")
    best_target_models = get_filtered_best_models_of(target_profile, group="param")
    linear_baseline_model = get_filtered_best_models_of(
        baseline_profile, group="param", model_filter=create_filter_by_model("linear")
    )
    linear_target_model = get_filtered_best_models_of(
        target_profile, group="param", model_filter=create_filter_by_model("linear")
    )

    covered_uids = set.intersection(
        set(best_baseline_models.keys()),
        set(best_target_models.keys()),
        set(linear_baseline_model.keys()),
        set(linear_target_model.keys()),
    )
    models = {
        uid: (
            best_baseline_models[uid],
            best_target_models[uid],
            linear_baseline_model[uid],
            linear_target_model[uid],
        )
        for uid in covered_uids
    }

    # iterate through all uids and corresponding models
    for uid, model_quadruple in models.items():
        (
            baseline_model,
            target_model,
            baseline_linear_model,
            target_linear_model,
        ) = model_quadruple

        # obtaining the dependent and independent variables of all models
        baseline_y_pts, baseline_x_pts = get_function_values(baseline_model)
        target_y_pts, _ = get_function_values(target_model)
        linear_baseline_y_pts, _ = get_function_values(baseline_linear_model)
        linear_target_y_pts, _ = get_function_values(target_linear_model)

        # calculating the absolute and relative error
        lin_abs_error = np.subtract(linear_target_y_pts, linear_baseline_y_pts)
        abs_error = np.subtract(target_y_pts, baseline_y_pts)
        sum_abs_err = np.sum(abs_error)
        rel_error_arr = np.nan_to_num(np.divide(abs_error, baseline_y_pts))
        rel_error = np.sum(rel_error_arr) / len(rel_error_arr) * 100

        # check state, when no change has occurred
        change = PerformanceChange.Unknown
        change_type = ""
        threshold_b0: float = abs(0.05 * float(baseline_model.b0))
        threshold_b1: float = abs(0.05 * float(baseline_model.b1))
        diff_b0 = float(target_model.b0 - baseline_model.b0)
        diff_b1 = float(target_model.b1 - baseline_model.b1)
        if abs(diff_b0) <= threshold_b0 and abs(diff_b1) <= threshold_b1:
            change = PerformanceChange.NoChange
        else:  # some change between profile was occurred
            if classification_method == ClassificationMethod.PolynomialRegression:
                change_type = polynomial_regression.exec_polynomial_regression(
                    baseline_x_pts, lin_abs_error
                )
            elif classification_method == ClassificationMethod.LinearRegression:
                change_type = linear_regression.exec_linear_regression(
                    uid,
                    baseline_x_pts,
                    lin_abs_error,
                    0.05 * np.amax(abs_error),
                    target_linear_model.b1 - baseline_linear_model.b1,
                    baseline_model,
                    target_model,
                    baseline_profile,
                )
            elif classification_method == ClassificationMethod.FastCheck:
                err_profile = fast_check.exec_fast_check(
                    uid, baseline_profile, baseline_x_pts, abs_error
                )
                std_err_model = get_filtered_best_models_of(err_profile, group="param")
                change_type = std_err_model[uid].type.upper()

        # check the relevant degree of changes and its type (negative or positive)
        if change != PerformanceChange.NoChange:
            if sum_abs_err > 0:
                if rel_error > 25:
                    change = PerformanceChange.Degradation
                else:
                    change = PerformanceChange.MaybeDegradation
            else:
                if rel_error < -25:
                    change = PerformanceChange.Optimization
                else:
                    change = PerformanceChange.MaybeOptimization

        best_corresponding_linear_model = best_baseline_models[uid]
        best_corresponding_baseline_model = best_baseline_models[uid]
        confidence = (
            min(best_corresponding_linear_model.r_square, target_linear_model.r_square)
            if best_corresponding_linear_model
            else 0.0
        )

        yield DegradationInfo(
            res=change,
            loc=uid,
            fb=best_corresponding_baseline_model.type,
            tt=target_model.type,
            t=change_type,
            rd=rel_error,
            ct="r_square",
            cr=confidence,
        )
