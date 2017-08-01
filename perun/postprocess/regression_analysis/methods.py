"""Module with available regression computational methods.

This module exposes all currently implemented computational methods for regression analysis.

"""

import collections

import perun.postprocess.regression_analysis.regression_models as mod
import perun.utils.exceptions as exceptions
import perun.postprocess.regression_analysis.tools as tools


def get_supported_methods():
    return [key for key in _methods.keys()]


def compute(data_gen, method, models, **kwargs):
    """The regression analysis wrapper for various computation methods.

    Arguments:
        data_gen(iter): the generator object with collected data (data provider generators)
        method(str): the _methods key value indicating requested computation method
        models(list of str): list of requested regression models to compute
        kwargs: various additional configuration arguments for specific models
    Raises:
        GenericRegressionExceptionBase: derived versions which are used in the computation functions
        DictionaryKeysValidationFailed: in case the data format dictionary is incorrect
    Returns:
        list of dict: the computation results

    """
    # Initialize the resulting dictionary
    analysis = []

    for chunk in data_gen:
        try:
            for result in _methods[method](chunk[0], chunk[1], models, **kwargs):
                result['uid'] = chunk[2]
                result['method'] = method
                result = _transform_to_output_data(result, ['uid', 'method'])
                analysis.append(result)
        except exceptions.GenericRegressionExceptionBase as e:
            print("info: unable to perform regression analysis on function '{0}'.".format(chunk[2]))
            print("  - " + e.msg)
    return analysis


def full_computation(x, y, computation_models, **kwargs):
    """The full computation method which fully computes every specified regression model.

    The method might have performance issues in case of too many models or data points.

    Arguments:
        x(list): the list of x points coordinates
        y(list): the list of y points coordinates
        computation_models(tuple of str): the collection of regression models that will be fully computed
        kwargs: additional configuration parameters
    Raises:
        GenericRegressionExceptionBase: derived versions which are used in the computation functions
        DictionaryKeysValidationFailed: in case the data format dictionary is incorrect
    Returns:
        iterable: the generator object which produces computed models one by one as a transformed output
                  data dictionary

    """
    # Get all the models properties
    for model in mod.map_to_models(computation_models):
        # Update the properties accordingly
        model['steps'] = 1
        model = _build_uniform_regression_data_format(x, y, model)
        # Compute each model
        for result in model['computation'](model):
            yield result


def iterative_computation(x, y, computation_models, **kwargs):
    """The iterative computation method.

    This method splits the regression data evenly into random parts, which are incrementally computed. Only
    the currently best fitting model is computed in each step.

    This method might produce only local result (local extrema), but it's generally faster than the full
    computation method.

    Arguments:
        x(list): the list of x points coordinates
        y(list): the list of y points coordinates
        computation_models(tuple of str): the collection of regression models that will be fully computed
        kwargs: additional configuration parameters
    Raises:
        GenericRegressionExceptionBase: derived versions which are used in the computation functions
        DictionaryKeysValidationFailed: in case the data format dictionary is incorrect
    Returns:
        iterable: the generator object which produces best fitting model as a transformed data dictionary

    """
    x, y = tools.shuffle_points(x, y)

    model_generators = []
    results = []
    # Get all the models properties
    for model in mod.map_to_models(computation_models):
        # Transform the properties
        model['steps'] = kwargs['steps']
        data = _build_uniform_regression_data_format(x, y, model)
        # Do a single computational step for each model
        model_generators.append(model['computation'](data))
        results.append(next(model_generators[-1]))

    best_fit = None
    while True:
        try:
            # Get the best fitting model and do next computation step
            best_fit = _find_best_fitting_model(results)
            results[best_fit] = next(model_generators[best_fit])
        except StopIteration:
            # The best fitting model finished the computation, end of computation
            yield results[best_fit]
            break


def interval_computation(x, y, computation_models, **kwargs):
    """The interval computation method.

    This method splits the regression data into evenly distributed sorted parts (i.e. intervals) and each
    interval is computed separately using the full computation.

    This technique allows to find different regression models in each interval and thus discover different
    complexity behaviour for algorithm based on it's input size.

    Arguments:
        x(list): the list of x points coordinates
        y(list): the list of y points coordinates
        computation_models(tuple of str): the collection of regression models that will be fully computed
        kwargs: additional configuration parameters, 'steps' expected
    Raises:
        GenericRegressionExceptionBase: derived versions which are used in the computation functions
        DictionaryKeysValidationFailed: in case the data format dictionary is incorrect
    Returns:
        the generator object which produces computed models one by one for every interval as a transformed
        output data dictionary

    """
    # Sort the regression data
    x, y = tools.sort_points(x, y)
    # Split the data into intervals and do a full computation on each one of them
    for part_start, part_end in tools.split_sequence(len(x), kwargs['steps']):
        interval_gen = full_computation(x[part_start:part_end], y[part_start:part_end], computation_models)
        # Provide result for each model on every interval
        results = []
        for model in interval_gen:
            results.append(model)

        # Find the best model for the given interval
        best_fit = _find_best_fitting_model(results)
        yield results[best_fit]


def initial_guess_computation(x, y, computation_models, **kwargs):
    """The initial guess computation method.

    This method does initial computation of a data sample and then computes the rest of the model that has best
    r^2 coefficient.

    This method might produce only local result (local extrema), but it's generally faster than the full
    computation method.

    Arguments:
        x(list): the list of x points coordinates
        y(list): the list of y points coordinates
        computation_models(tuple of str): the collection of regression models that will be fully computed
        kwargs: additional configuration parameters, 'steps' expected
    Raises:
        GenericRegressionExceptionBase: derived versions which are used in the computation functions
        DictionaryKeysValidationFailed: in case the data format dictionary is incorrect
    Returns:
        iterable: the generator object that produces the complete result in one step

    """
    x, y = tools.shuffle_points(x, y)

    model_generators = []
    results = []
    # Get all the models properties
    for model in mod.map_to_models(computation_models):
        # Transform the properties
        model['steps'] = kwargs['steps']
        data = _build_uniform_regression_data_format(x, y, model)
        # Do a single computational step for each model
        model_generators.append(model['computation'](data))
        results.append(next(model_generators[-1]))
    # Find the model that fits the most
    best_fit = _find_best_fitting_model(results)

    # Now compute the rest of the model
    while True:
        try:
            results[best_fit] = next(model_generators[best_fit])
        except StopIteration:
            # The best fitting model finished the computation, end of computation
            yield results[best_fit]
            break


def bisection_computation(x, y, computation_models, **kwargs):
    """The bisection computation method.

    This method computes the best fitting model for the whole profiling data and then perform interval
    bisection in order to find potential difference between interval models.

    Arguments:
        x(list): the list of x points coordinates
        y(list): the list of y points coordinates
        computation_models(tuple of str): the collection of regression models that will be fully computed
        kwargs: additional configuration parameters
    Raises:
        GenericRegressionExceptionBase: derived versions which are used in the computation functions
        DictionaryKeysValidationFailed: in case the data format dictionary is incorrect
    Returns:
        iterable: the generator object that produces interval models in order

    """
    # Sort the regression data
    x, y = tools.sort_points(x, y)

    # Compute the initial model on the whole data set
    init_model = _compute_bisection_model(x, y, computation_models)

    # Do bisection and try to find different model for the new sections
    for sub_model in _bisection_step(x, y, computation_models, init_model):
        yield sub_model


def _bisection_step(x, y, computation_models, last_model):
    """The bisection step computation.

    Performs one computation step for bisection. Splits the interval set by x, y and tries to compute each
    half. In case of model change, the interval is split again and the process repeats. Otherwise the last
    model is used as a final model.


    Arguments:
        x(list): the list of x points coordinates
        y(list): the list of y points coordinates
        computation_models(tuple of str): the collection of regression models that will be fully computed
        last_model(dict): the full interval model that is split
    Raises:
        GenericRegressionExceptionBase: derived versions which are used in the computation functions
        DictionaryKeysValidationFailed: in case the data format dictionary is incorrect
    Returns:
        iterable: the generator object that produces interval result

    """
    # Split the interval and compute each one of them
    half_models = []
    parts = []
    for part_start, part_end in tools.split_sequence(len(x), 2):
        half_models.append(_compute_bisection_model(x[part_start:part_end], y[part_start:part_end], computation_models))
        parts.append((part_start, part_end))

    # The half models are not different, return the full interval model
    if half_models[0]['model'] == last_model['model'] and half_models[1]['model'] == last_model['model']:
        yield last_model
        return

    if half_models[0]['model'] != last_model['model']:
        # First model is different, continue with bisection
        for submodel in _bisection_step(
                x[parts[0][0]:parts[0][1]], y[parts[0][0]:parts[0][1]], computation_models, half_models[0]):
            yield submodel
    else:
        # First model is the same, but the second is not, return the half model
        yield half_models[0]

    if half_models[1]['model'] != last_model['model']:
        # Second model is different, continue with bisection
        for submodel in _bisection_step(
                x[parts[1][0]:parts[1][1]], y[parts[1][0]:parts[1][1]], computation_models, half_models[1]):
            yield submodel
    else:
        # Second model is the same, but the first was not
        yield half_models[1]


def _transform_to_output_data(data, extra_keys=None):
    """Transforms the data dictionary into their output format - omitting computational details and keys that are
       not important for the result and it's further manipulation.

    The function provides dictionary with 'model', 'coeffs', 'r_square' and 'x_limits' keys taken from the
    data dictionary. The function also allows to specify extra keys to be included in the output dictionary.
    If certain key is missing in the data dictionary, then it's not included in the output dictionary.

    Arguments:
        data(dict): the data dictionary with results
        extra_keys(list of str): the extra keys to include
    Raises:
        DictionaryKeysValidationFailed: in case the data format dictionary is incorrect
    Returns:
        dict: the output dictionary

    """
    tools.validate_dictionary_keys(data, ['model', 'coeffs', 'r_square', 'x_max', 'x_min'], [])

    # Specify the keys which should be directly mapped
    transform_keys = ['model', 'coeffs', 'r_square']
    if extra_keys is not None:
        transform_keys += extra_keys
    transformed = {key: data[key] for key in transform_keys if key in data}
    # Specify the x borders
    transformed['x_limits'] = [data['x_min'], data['x_max']]
    return transformed


def _find_best_fitting_model(model_results):
    """Finds the model which is currently the best fitting one.

    This function operates on a (intermediate) result dictionaries, where 'r_square' key is required.

    Arguments:
        model_results(list of dict): the list of result dictionaries for models
    Return:
        int: the index of best fitting model amongst the list

    """
    # Guess the best fitting model is the first one
    best_fit = 0
    for i in range(1, len(model_results)):
        # Compare and find the best one
        if model_results[i]['r_square'] > model_results[best_fit]['r_square']:
            best_fit = i
    return best_fit


def _compute_bisection_model(x, y, computation_models, **kwargs):
    """Compute specified models on a given data set and find the best fitting model.

    Currently uses the full computation method.

    Arguments:
        x(list): the list of x points coordinates
        y(list): the list of y points coordinates
        computation_models(tuple of str): the collection of regression models that will be computed
        kwargs: additional configuration parameters
    Raises:
        GenericRegressionExceptionBase: derived versions which are used in the computation functions
        DictionaryKeysValidationFailed: in case the data format dictionary is incorrect
    Returns:
        dict: the best fitting model
    """

    results = []
    # Compute the step using the full computation
    for result in full_computation(x, y, computation_models, **kwargs):
        results.append(result)
    # Find the best model
    return results[_find_best_fitting_model(results)]


def _build_uniform_regression_data_format(x, y, model):
    """Creates the uniform regression data dictionary from the model properties and regression data points.

    The uniform data dictionary is used in the regression computation as it allows to build generic and
    easily extensible computational methods and models.

    Arguments:
        x(list): the list of x points coordinates
        y(list): the list of y points coordinates
        model(dict): the regression model properties
    Raises:
        InvalidPointsException: if the points count is too low or their coordinates list have different lengths
        DictionaryKeysValidationFailed: in case the data format dictionary is incorrect
    Return:
        dict: the uniform data dictionary

    """
    # Check the requirements
    tools.check_points(len(x), len(y), tools.MIN_POINTS_COUNT)
    tools.validate_dictionary_keys(model, ['data_gen'], ['x', 'y'])

    model['x'] = x
    model['y'] = y
    # Initialize the data generator
    model['data_gen'] = model['data_gen'](model)
    return model

# supported methods mapping
# - every method must have the same argument signature to be called in 'compute' function
# -- the signature: x, y, models, **kwargs
_methods = collections.OrderedDict([
    ('full', full_computation),
    ('iterative', iterative_computation),
    ('interval', interval_computation),
    ('initial_guess', initial_guess_computation),
    ('bisection', bisection_computation)
])