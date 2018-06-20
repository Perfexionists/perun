"""The module contains common methods, which are use by three detection methods 
(fast_check, linear_regression, polynomial_regression).

The module contains one general method, which controls the all logic of the detection.
This method is called by three other methods and its task is calculating the needed
metrics to check performance change between two profiles and obtaining required models from 
these profiles. Module contains two other temporary methods, which are using by mentioned
general methods. 

"""

import numpy as np
np.seterr(divide='ignore', invalid='ignore')

import perun.check as check
import perun.postprocess.regression_analysis.tools as tools
import perun.postprocess.regression_analysis.regression_models as regression_models
import perun.profile.query as query
import perun.logic.runner as runner

from perun.utils.structs import PerformanceChange, DegradationInfo

__author__ = 'Simon Stupinsky'

SAMPLES = 1000

def get_best_models_of(profile, model_type=None):
    """Obtains the models from the given profile. In the first case the method obtains the
    best fitting models, it means, that it obtains the models which have the higher values
    of coefficient determination. In the case, that arguments model_type was given, method
    obtains model of that type. Method maps the individually metrics from obtained profile
    to map, which is returns to calling function. Models are chosen unique according to its UID. 

    :param dict profile: dictionary of profile resources and stuff
    :param string model_type: the type of model for obtaining
    :returns: map of unique identifier of computed models to their best models
    """

    if model_type is None:
        best_model_map = {
            uid: ("", 0.0, 0.0, 0.0, 0, 0, 0.0) for uid in query.unique_model_values_of(profile, 'uid')
        }
        for _, model in query.all_models_of(profile):
            model_uid = model['uid']
            if best_model_map[model_uid][1] < model['r_square']:
                if model['model'] == 'quadratic':
                    best_model_map[model_uid] = (
                        model['model'], model['r_square'], model['coeffs'][0]['value'],
                        model['coeffs'][1]['value'], model['x_interval_start'],
                        model['x_interval_end'], model['coeffs'][2]['value'])
                else:
                    best_model_map[model_uid] = (
                        model['model'], model['r_square'], model['coeffs'][0]['value'], model['coeffs'][1]['value'],
                        model['x_interval_start'], model['x_interval_end'])
    else:
        best_model_map = {
            uid: ("", 0.0, 0.0, 0.0, 0, 0, 0.0) for uid in query.unique_model_values_of(profile, 'uid')
        }
        for _, model in query.all_models_of(profile):
            model_uid = model['uid']
            if model['model'] == model_type:
                if model['model'] == 'quadratic':
                    best_model_map[model_uid] = (
                        model['model'], model['r_square'], model['coeffs'][0]['value'],
                        model['coeffs'][1]['value'], model['x_interval_start'],
                        model['x_interval_end'], model['coeffs'][2]['value'])
                else:
                    best_model_map[model_uid] = (
                        model['model'], model['r_square'], model['coeffs'][0]['value'], model['coeffs'][1]['value'],
                        model['x_interval_start'], model['x_interval_end'])

    return best_model_map

def get_function_values(model):
    """Obtains the relevant values of dependent and independent variables according to
    the given profile, respectively its coefficients. On the base of the count of samples
    is interval divide into several parts and to them is computed relevant values of
    dependent variables.

    :param dict model: model with its required metrics (value of coefficient, type, ...) 
    :returns: np_array (x-coordinates, y-coordinates)
    """

    array_x_pts = regression_models._MODELS[model[1][0]
        ]['transformations']['plot_model']['model_x'](model[1][4], model[1][5], SAMPLES, False)

    if model[1][0] == 'quadratic':
        array_y_pts = regression_models._MODELS[model[1][0]]['transformations']['plot_model']['model_y'](
            array_x_pts, model[1][2], model[1][3], model[1][6], 
            regression_models._MODELS[model[1][0]]['transformations']['plot_model']['formula'], 
            return_dict=False)
    else:
        array_y_pts = regression_models._MODELS[model[1][0]]['transformations']['plot_model']['model_y'](
            array_x_pts, model[1][2], model[1][3], 
            regression_models._MODELS[model[1][0]]['transformations']['plot_model']['formula'], 
            regression_models._MODELS[model[1][0]]['f_x'], return_dict=False)

    return array_y_pts, array_x_pts
    
def general_detection(baseline_profile, target_profile, mode=0):
    """The general method, which covers all detection logic. At the begin obtains the pairs 
    of the best models from the given profiles and the pairs of the linears models. Subsequently
    are computed the needed statistics metrics, concretely relative and absolute error. According 
    to the calling method is call the relevant classification method. After the returned from this
    classification is know the type of occurred changes. In the last steps is determined
    information, which will be returned to users (i.e. confidence, change between models).

    :param dict baseline_profile: baseline against which we are checking the degradation
    :param dict target_profile: profile corresponding to the checked minor version
    :returns: tuple (degradation result, degradation location, degradation rate, confidence)
    """

    # obtaining the needed models from both profiles
    best_baseline_models = get_best_models_of(baseline_profile)
    best_target_models = get_best_models_of(target_profile)
    linear_baseline_model = get_best_models_of(baseline_profile, 'linear')
    linear_target_model = get_best_models_of(target_profile, 'linear')

    for baseline_model, target_model, baseline_linear_model, target_linear_model in zip(best_baseline_models.items(), best_target_models.items(), linear_baseline_model.items(), linear_target_model.items()):

        # obtaining the dependent and independent variables of all models
        baseline_y_pts, baseline_x_pts = get_function_values(baseline_model)
        target_y_pts, _ = get_function_values(target_model)
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
        THRESHOLD_B0 = abs(0.05 * baseline_model[1][2])
        THRESHOLD_B1 = abs(0.05 * baseline_model[1][3])
        if (abs(target_model[1][2] - baseline_model[1][2]) <= THRESHOLD_B0
            and abs(target_model[1][3] - baseline_model[1][3]) <= THRESHOLD_B1):
            change = PerformanceChange.NoChange
        else: # some change between profile was occurred
            if mode == 0: # classification based on the polynomial regression
                change_type = check.polynomial_regression.exec_polynomial_regression(baseline_x_pts, lin_abs_error)
            elif mode == 1: # classification based on the linear regression
                change_type = check.linear_regression.exec_linear_regression(baseline_x_pts, lin_abs_error, 0.05 * np.amax(abs_error),target_linear_model[1][3] - baseline_linear_model[1][3],
                    baseline_model, target_model, baseline_profile)
            elif mode == 2: # classification based on the regression analysis
                change_type = check.fast_check.exec_fast_check(baseline_profile, baseline_x_pts, abs_error)
                change_type = change_type[baseline_model[0]][0].upper() + ' '
        
        # check the relevant degree of changes and its type (negative or positive)
        if change != PerformanceChange.NoChange:
            if (sum_abs_err > 0):
                if (rel_error > 25):
                    change = PerformanceChange.Degradation
                else:
                    change = PerformanceChange.MaybeDegradation
                change_type += 'ERROR'
            else:
                if (rel_error < -25):
                    change = PerformanceChange.Optimization
                else:
                    change = PerformanceChange.MaybeOptimization
                change_type += 'IMPROVEMENT'
        
        best_corresponding_linear_model = best_baseline_models.get(
            baseline_linear_model[0])
        best_corresponding_baseline_model = best_baseline_models.get(
            baseline_model[0])
        if best_corresponding_linear_model:
            confidence = min(
                best_corresponding_linear_model[1], target_linear_model[1][1])

        yield DegradationInfo(
            change, change_type, baseline_model[0],
            best_corresponding_baseline_model[0],
            target_model[1][0],
            rel_error,
            'r_square', confidence
        ) 