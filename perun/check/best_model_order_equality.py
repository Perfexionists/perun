import perun.profile.query as query
import perun.check.factory as check

from perun.utils.structs import DegradationInfo

__author__ = 'Tomas Fiedor'

CONFIDENCE_THRESHOLD = 0.9
MODEL_ORDERING = [
    'constant',
    'logarithmic',
    'linear',
    'quadratic',
    'power',
    'exponential'
]


def get_best_models_of(profile):
    """Retrieves the best models for unique identifiers and their models

    :param dict profile: dictionary of profile resources and stuff
    :returns: map of unique identifier of computed models to their best models
    """
    best_model_map = {
        uid: ("", 0.0) for uid in query.unique_model_values_of(profile, 'uid')
    }
    for _, model in query.all_models_of(profile):
        model_uid = model['uid']
        if best_model_map[model_uid][1] < model['r_square']:
            best_model_map[model_uid] = (model['model'], model['r_square'])

    return best_model_map


def best_model_order_equality(baseline_profile, target_profile):
    """Checks between pair of (baseline, target) profiles, whether the can be degradation detected

    This is based on simple heuristic, where for the same function models, we only check the order
    of the best fit models. If these differ, we detect the possible degradation.

    :param dict baseline_profile: baseline against which we are checking the degradation
    :param dict target_profile: profile corresponding to the checked minor version
    :returns: tuple (degradation result, degradation location, degradation rate)
    """
    best_baseline_models = get_best_models_of(baseline_profile)
    best_target_profiles = get_best_models_of(target_profile)

    for uid, best_model in best_target_profiles.items():
        best_corresponding_baseline_model = best_baseline_models.get(uid)
        if best_corresponding_baseline_model:
            confidence = min(best_corresponding_baseline_model[1], best_model[1])
            if confidence >= CONFIDENCE_THRESHOLD \
               and best_corresponding_baseline_model[0] != best_model[0]:
                baseline_ordering = MODEL_ORDERING.index(best_corresponding_baseline_model[0])
                target_ordering = MODEL_ORDERING.index(best_model[0])
                if baseline_ordering > target_ordering:
                    change = check.PerformanceChange.Optimization
                else:
                    change = check.PerformanceChange.Degradation
            else:
                change = check.PerformanceChange.NoChange

            yield DegradationInfo(
                change, "model", uid,
                best_corresponding_baseline_model[0],
                best_model[0],
                "r_square", confidence
            )
