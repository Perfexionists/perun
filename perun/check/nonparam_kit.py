from __future__ import annotations

# Standard Imports
from typing import TYPE_CHECKING
import re

# Third-Party Imports
import numpy as np

# Perun Imports
from perun.postprocess.regression_analysis import data_provider
from perun.utils import log
from perun.utils.structs import PerformanceChange, ModelRecord
import perun.check.detection_kit as methods
import perun.postprocess.regressogram.methods as rg_methods

if TYPE_CHECKING:
    from perun.profile.factory import Profile


def classify_change(
    diff_value: float,
    no_change_threshold: float,
    change_threshold: float,
    baseline_per: float = 1,
) -> PerformanceChange:
    """
    Classification of changes according to the value of relative error.

    A method performs an evaluation of relative error value, that was
    computed between two compared profiles. This value is compared
    with threshold values and subsequently is specified the type
    of changes. Following rules are applied:

        * if DIFF_VALUE > 0 then change=DEGRADATION
        ** else DIFF_VALUE <= 0 then change=OPTIMIZATION

        | -> if DIFF_VALUE <= NO_CHANGE_THRESHOLD then state=NO_CHANGE
        || -> elif DIFF_VALUE <= CHANGE_THRESHOLD then state=MAYBE_CHANGE
        ||| -> else DIFF_VALUE > CHANGE_THRESHOLD then state=CHANGE

    :param float diff_value: value of diff value computed between compared profiles
    :param float no_change_threshold: threshold to determine `no_change` state
    :param float change_threshold: threshold to determine remaining two states
        (`maybe_change` and `change`)
    :param float baseline_per: percentage rate from the threshold according to the baseline value
    :return PerformanceChange: determined changes in the basis of given arguments
    """
    if abs(diff_value) <= no_change_threshold * baseline_per:
        result = PerformanceChange.NoChange
    elif abs(diff_value) <= change_threshold * baseline_per:
        result = (
            PerformanceChange.MaybeOptimization
            if diff_value < 0
            else PerformanceChange.MaybeDegradation
        )
    else:
        result = PerformanceChange.Optimization if diff_value < 0 else PerformanceChange.Degradation

    return result


def unify_buckets_in_regressogram(
    uid: str,
    baseline_model_record: ModelRecord,
    target_model_record: ModelRecord,
    target_profile: Profile,
) -> ModelRecord:
    """
    The method unifies the regressograms into the same count of buckets.

    A method unifies the target regressogram model with the regressogram model
    from the baseline profile. It set the options for new post-processing of
    target model according to the options at baseline model and then call the
    method to compute the new regressogram models. This method returns the new
    regressogram model, which has the same 'uid' as the given models.

    :param str uid: unique identification of both analysed models
    :param ModelRecord baseline_model_record: baseline regressogram model with all its parameters
    :param ModelRecord target_model_record: target regressogram model with all its parameters
    :param Profile target_profile: target profile corresponding to the checked minor version
    :return dict: new regressogram model with the required 'uid'
    """
    uid = re.sub(baseline_model_record.type + "$", "", uid)
    baseline_coeff_len = baseline_model_record.coeff_size()
    target_coeff_len = target_model_record.coeff_size()
    log.warn(
        f"{uid}: {baseline_model_record.type} models with different length "
        f"({baseline_coeff_len} != {target_coeff_len}) will be sliced accordingly",
        end=": ",
    )
    log.cprint("Target regressogram model will be post-processed again.\n", "yellow")
    # find target model with all needed items from target profile
    target_model = target_profile.get_model_of(target_model_record.type, uid)
    # set needed parameters for regressogram post-processors
    mapper_keys = {"per_key": target_model["per_key"], "of_key": target_model["of_key"]}
    config = {
        "statistic_function": target_model["statistic_function"],
        "bucket_number": baseline_coeff_len,
        "bucket_method": None,
    }
    config.update(mapper_keys)
    # compute new regressogram models with the new parameters needed to unification
    new_regressogram_models = rg_methods.compute_regressogram(
        data_provider.generic_profile_provider(target_profile, **mapper_keys), config
    )

    # match the regressogram model with the right 'uid'
    model = [model for model in new_regressogram_models if model["uid"] == uid][0]
    return methods.create_model_record(model)


def preprocess_nonparam_models(
    uid: str,
    baseline_model: ModelRecord,
    target_profile: Profile,
    target_model: ModelRecord,
) -> tuple[list[float], list[float], list[float]]:
    """
    Function prepare models to execute the computation of statistics between them.

    This function in the case of parametric models obtains their functional values directly
    from coefficients these models. The function checks lengths of both models interval and
    potentially sliced the intervals to the same length. In the case of the regressogram model,
    function unifies two regressogram models according to the length of the shorter interval.
    The function returns the values of both model (baseline and target) and the common interval
    on which are defined these models.

    :param str uid: unique identification of both analysed models
    :param ModelRecord baseline_model: baseline model with its parameters for processing
    :param Profile target_profile: target profile
    :param ModelRecord target_model: target model with all its parameters for processing
    :return: tuple with values of both models and their relevant x-interval
    """

    def get_model_coordinates(model: ModelRecord) -> tuple[list[float], list[float]]:
        """
        Function obtains the coordinates of given model.

        The function according to the kind of model obtains its coordinates.
        When the model is parametric, then are coordinates obtained from its
        formula. When the model is non-parametric then the function divides
        the stored x-interval according to the length of its stored values.

        :param ModelRecord model: dictionary with model and its required properties
        :return: obtained x and y coordinates - x-points, y-points
        """
        if model.b1 is not None:
            x_pts, y_pts = methods.get_function_values(model)
        else:
            x_pts = np.linspace(model.x_start, model.x_end, num=len(model.b0))
            y_pts = model.b0
        return x_pts, y_pts

    def check_model_coordinates() -> tuple[list[float], list[float], list[float], list[float]]:
        """
        Function check the lengths of the coordinates from both models.

        When the length of coordinates from both models are not equal, then
        the function applies the slicing of all intervals to the length of the
        shorter model. The function returns the all potentially reduced intervals
        of coordinates. When the lengths are valid, then the function returns
        original coordinates without change.

        :return foursome: x-points and y-points from both profiles (baseline and target)
        """
        baseline_x_pts_len = len(baseline_x_pts)
        baseline_y_pts_len = len(baseline_y_pts)
        target_x_pts_len = len(target_x_pts)
        target_y_pts_len = len(target_y_pts)
        if baseline_y_pts_len != target_y_pts_len:
            log.warn(
                f"{uid}: {baseline_model.type} models with different length "
                f"({baseline_y_pts_len} != {target_y_pts_len}) will be sliced"
            )
            return (
                baseline_x_pts[: min(baseline_x_pts_len, target_x_pts_len)],
                baseline_y_pts[: min(baseline_y_pts_len, target_y_pts_len)],
                target_x_pts[: min(baseline_x_pts_len, target_x_pts_len)],
                target_y_pts[: min(baseline_y_pts_len, target_y_pts_len)],
            )
        return baseline_x_pts, baseline_y_pts, target_x_pts, target_y_pts

    # check whether both models are regressogram and whether there are not about the same length
    if (
        baseline_model.type == "regressogram"
        and target_model.type == "regressogram"
        and baseline_model.coeff_size() != target_model.coeff_size()
    ):
        target_model = unify_buckets_in_regressogram(
            uid, baseline_model, target_model, target_profile
        )

    # obtains coordinates from both models and perform the check their lengths
    baseline_x_pts, baseline_y_pts = get_model_coordinates(baseline_model)
    target_x_pts, target_y_pts = get_model_coordinates(target_model)
    (
        baseline_x_pts,
        baseline_y_pts,
        target_x_pts,
        target_y_pts,
    ) = check_model_coordinates()

    return baseline_x_pts, baseline_y_pts, target_y_pts
