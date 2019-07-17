"""The module contains common methods, which are use by three detection methods
(fast_check, linear_regression, polynomial_regression).

The module contains one general method, which controls the all logic of the detection.
This method is called by three other methods and its task is calculating the needed
metrics to check performance change between two profiles and obtaining required models from
these profiles. Module contains two other temporary methods, which are using by mentioned
general methods.
"""

from enum import Enum

import numpy as np

import perun.utils as utils
import perun.check as check
import perun.postprocess.regression_analysis.regression_models as regression_models
import perun.profile.query as query

from perun.utils.structs import PerformanceChange, DegradationInfo

__author__ = 'Simon Stupinsky'

SAMPLES = 1000
ClassificationMethod = Enum(
    'ClassificationMethod', 'FastCheck LinearRegression PolynomialRegression'
)

np.seterr(divide='ignore', invalid='ignore')


def create_filter_by_model(model_name):
    """Creates a filter w.r.t to given model_name

    Note this is to be used in get_filtered_best_models_of

    :param str model_name: name of the model, that will be filtered out
    :return: filter function that retrieves only models of given type
    """
    def filter_by_model(_, model):
        """Filters the models according to the model name

        :param dict _: dictionary with already found models
        :param dict model: model of given uid
        :return: true if the given model is of the given type
        """
        return model['model'] == model_name
    return filter_by_model


def filter_by_r_square(model_map, model):
    """Filters the models according to the value of the r_square

    :param dict model_map: dictionary with already found models
    :param dict model: model of given uid
    :return:  filter function that retrieves only the best model w.r.t r_square
    """
    return model_map[model['uid']]['r_square'] < model['r_square']


def get_filtered_best_models_of(profile, group, model_filter=filter_by_r_square):
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
    :param function model_filter: filter function for models
    :returns: map of unique identifier of computed models to their best models
    """
    best_model_map = {
        uid: {'r_square': 0.0} for uid in query.unique_model_values_of(profile, 'uid')
    }
    for _, model in profile.all_models(group=group):
        if model_filter(best_model_map, model):
            best_model_map[model['uid']] = model

    return {k: v for k, v in best_model_map.items() if v['r_square'] != 0.0}


def get_function_values(model):
    """Obtains the relevant values of dependent and independent variables according to
    the given profile, respectively its coefficients. On the base of the count of samples
    is interval divide into several parts and to them is computed relevant values of
    dependent variables.

    :param dict model: model with its required metrics (value of coefficient, type, ...)
    :returns: np_array (x-coordinates, y-coordinates)
    """
    model_handler = regression_models._MODELS[model['model']]
    plotter = model_handler['transformations']['plot_model']

    array_x_pts = plotter['model_x'](
        model['x_start'], model['x_end'], SAMPLES, transform_by=utils.identity
    )

    if model['model'] == 'quadratic':
        array_y_pts = plotter['model_y'](
            array_x_pts,
            model['coeffs'][0]['value'],
            model['coeffs'][1]['value'],
            model['coeffs'][2]['value'],
            plotter['formula'],
            transform_by=utils.identity
        )
    else:
        array_y_pts = plotter['model_y'](
            array_x_pts,
            model['coeffs'][0]['value'],
            model['coeffs'][1]['value'],
            plotter['formula'],
            model_handler['f_x'],
            transform_by=utils.identity
        )

    return array_y_pts, array_x_pts


def general_detection(
        base_profile, targ_profile, classification_method=ClassificationMethod.PolynomialRegression
):
    """The general method, which covers all detection logic. At the begin obtains the pairs
    of the best models from the given profiles and the pairs of the linears models. Subsequently
    are computed the needed statistics metrics, concretely relative and absolute error. According
    to the calling method is call the relevant classification method. After the returned from this
    classification is know the type of occurred changes. In the last steps is determined
    information, which will be returned to users (i.e. confidence, change between models).

    :param Profile base_profile: baseline against which we are checking the degradation
    :param Profile targ_profile: profile corresponding to the checked minor version
    :param ClassificationMethod classification_method: method used for actual classification of
        performance changes
    :returns: tuple (degradation result, degradation location, degradation rate, confidence)
    """

    # obtaining the needed models from both profiles
    best_base_models = get_filtered_best_models_of(base_profile, group='param')
    best_targ_models = get_filtered_best_models_of(targ_profile, group='param')
    linear_base_model = get_filtered_best_models_of(
        base_profile, group='param', model_filter=create_filter_by_model('linear')
    )
    linear_targ_model = get_filtered_best_models_of(
        targ_profile, group='param', model_filter=create_filter_by_model('linear')
    )

    covered_uids = set.intersection(
        set(best_base_models.keys()), set(best_targ_models.keys()),
        set(linear_base_model.keys()), set(linear_targ_model.keys())
    )
    models = {
        uid: (
            best_base_models[uid], best_targ_models[uid],
            linear_base_model[uid], linear_targ_model[uid]
        ) for uid in covered_uids
    }

    # iterate through all uids and corresponding models
    for uid, model_quadruple in models.items():
        base_model, targ_model, baseline_linear_model, target_linear_model = model_quadruple

        # obtaining the dependent and independent variables of all models
        baseline_y_pts, baseline_x_pts = get_function_values(base_model)
        target_y_pts, _ = get_function_values(targ_model)
        linear_baseline_y_pts, _ = get_function_values(baseline_linear_model)
        linear_target_y_pts, _ = get_function_values(target_linear_model)

        # calculating the absolute and relative error
        lin_abs_error = np.subtract(linear_target_y_pts, linear_baseline_y_pts)
        abs_error = np.subtract(target_y_pts, baseline_y_pts)
        sum_abs_err = np.sum(abs_error)
        rel_error = np.nan_to_num(np.divide(abs_error, baseline_y_pts))
        rel_error = np.sum(rel_error) / len(rel_error) * 100

        # check state, when no change has occurred
        change = PerformanceChange.Unknown
        change_type = ''
        threshold_b0 = abs(0.05 * base_model['coeffs'][0]['value'])
        threshold_b1 = abs(0.05 * base_model['coeffs'][1]['value'])
        diff_b0 = targ_model['coeffs'][0]['value'] - base_model['coeffs'][0]['value']
        diff_b1 = targ_model['coeffs'][1]['value'] - base_model['coeffs'][1]['value']
        if abs(diff_b0) <= threshold_b0 and abs(diff_b1) <= threshold_b1:
            change = PerformanceChange.NoChange
        else:  # some change between profile was occurred
            if classification_method == ClassificationMethod.PolynomialRegression:
                change_type = check.polynomial_regression.exec_polynomial_regression(
                    baseline_x_pts, lin_abs_error
                )
            elif classification_method == ClassificationMethod.LinearRegression:
                change_type = check.linear_regression.exec_linear_regression(
                    uid, baseline_x_pts, lin_abs_error, 0.05 * np.amax(abs_error),
                    target_linear_model['coeffs'][1]['value'] -
                    baseline_linear_model['coeffs'][1]['value'],
                    base_model, targ_model, base_profile
                )
            elif classification_method == ClassificationMethod.FastCheck:
                err_profile = check.fast_check.exec_fast_check(
                    uid, base_profile, baseline_x_pts, abs_error
                )
                std_err_model = get_filtered_best_models_of(err_profile, group='param')
                change_type = std_err_model[uid][0].upper()

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

        best_corresponding_linear_model = best_base_models[uid]
        best_corresponding_base_model = best_base_models[uid]
        if best_corresponding_linear_model:
            confidence = min(
                best_corresponding_linear_model['r_square'], target_linear_model['r_square']
            )
        else:
            confidence = 0.0

        yield DegradationInfo(
            res=change,
            loc=uid,
            fb=best_corresponding_base_model['model'],
            tt=targ_model['model'],
            t=change_type,
            rd=rel_error,
            ct='r_square',
            cr=confidence
        )
