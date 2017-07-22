"""Module with available regression computational methods.

This module exposes all currently implemented computational methods for regression analysis.

"""


import regression_analysis.regression_models as mod
import regression_analysis.tools as tools


def full_computation(x, y, computation_models):
    """The full computation method which fully computes every specified regression model.

    The method might have performance issues in case of too many models or data points.

    Arguments:
        x(list): the list of x points coordinates
        y(list): the list of y points coordinates
        computation_models(list): the list of Models values representing the models which will be fully computed
    Raises:
        GenericRegressionExceptionBase: derived versions which are used in the computation functions
    Returns:
        iterable: the generator object which produces computed models one by one as a transformed output
                  data dictionary

    """
    # Get all the models properties
    for model in mod.map_to_models(computation_models):
        # Update the properties accordingly
        model['parts'] = 1
        model = _build_uniform_regression_data_format(x, y, model)
        # Compute each model
        for result in model['computation'](model):
            yield _transform_to_output_data(result)


def iterative_computation(x, y, parts, computation_models):
    """The iterative computation method.

    This method splits the regression data evenly into random parts, which are incrementally computed. Only
    the currently best fitting model is computed in each step.

    This method might produce only local result (local extrema), but it's generally faster than the full
    computation method.

    Arguments:
        x(list): the list of x points coordinates
        y(list): the list of y points coordinates
        parts(int): the number of iterative steps until the computation is finished
        computation_models(list): the list of Models values representing the models which will be computed
    Raises:
        GenericRegressionExceptionBase: derived versions which are used in the computation functions
    Returns:
        iterable: the generator object which produces best fitting model in each step as a transformed
                  data dictionary

    """
    x, y = tools.shuffle_points(x, y)

    model_generators = []
    results = []
    # Get all the models properties
    for model in mod.map_to_models(computation_models):
        # Transform the properties
        model['parts'] = parts
        data = _build_uniform_regression_data_format(x, y, model)
        # Do a single computational step for each model
        model_generators.append(model['computation'](data))
        results.append(next(model_generators[-1]))

    while True:
        try:
            # Get the best fitting model and do next computation step
            best_fit = _find_best_fitting_model(results)
            yield _transform_to_output_data(results[best_fit], ['x', 'y'])
            results[best_fit] = next(model_generators[best_fit])
        except StopIteration:
            # The best fitting model finished the computation, end of computation
            break


def interval_computation(x, y, parts, computation_models):
    """The interval computation method.

    This method splits the regression data into evenly distributed sorted parts (i.e. intervals) and each
    interval is computed separately using the full computation.

    This technique allows to find different regression models in each interval and thus discover different
    complexity behaviour for algorithm based on it's input size.

    Arguments:
        x(list): the list of x points coordinates
        y(list): the list of y points coordinates
        parts(int): the number of intervals to divide the regression data into
        computation_models(list): the list of Models values representing the models which will be computed
    Raises:
        GenericRegressionExceptionBase: derived versions which are used in the computation functions
    Returns:
        iterable: the generator object which produces a generator pro each interval. The interval generator
                  is actually the full computational result generator - see return value for full
                  computation for more details

    """
    # Sort the regression data
    x, y = tools.sort_points(x, y)
    # Split the data into intervals and do a full computation on each one of them
    for part_start, part_end in tools.split_sequence(len(x), parts):
        interval_gen = full_computation(x[part_start:part_end], y[part_start:part_end], computation_models)
        yield interval_gen


def initial_guess_computation(x, y, computation_models, sample):
    """The initial guess computation method.

    This method does initial computation of a data sample and then computes the rest of the model that has best
    r^2 coefficient.

    This method might produce only local result (local extrema), but it's generally faster than the full
    computation method.

    Arguments:
        x(list): the list of x points coordinates
        y(list): the list of y points coordinates
        computation_models(list): the list of Models values representing the models which will be computed
        sample(int): the sample of the regression data used to compute the initial guess
    Raises:
        GenericRegressionExceptionBase: derived versions which are used in the computation functions
    Returns:
        iterable: the generator object that produces the complete result in one step

    """
    x, y = tools.shuffle_points(x, y)
    best_model_gen = None
    best_model_result = None
    # Get all the models properties
    for model in mod.map_to_models(computation_models):
        # Transform the properties
        model['parts'] = sample
        data = _build_uniform_regression_data_format(x, y, model)
        # Do a single computational step for each model and get the best one
        new_gen = model['computation'](data)
        best_model_gen, best_model_result = _compare_models_fit(
            best_model_gen, best_model_result, new_gen, next(new_gen))

    # Now compute the rest of the model
    while True:
        try:
            best_model_result = next(best_model_gen)
        except StopIteration:
            # The best fitting model finished the computation, end of computation
            yield _transform_to_output_data(best_model_result)
            break


def bisection_computation(x, y, computation_models):
    """The bisection computation method.

    This method computes the best fitting model for the whole profiling data and then perform interval
    bisection in order to find potential difference between interval models.

    Arguments:
        x(list): the list of x points coordinates
        y(list): the list of y points coordinates
        computation_models(list): the list of Models values representing the models which will be computed
    Raises:
        GenericRegressionExceptionBase: derived versions which are used in the computation functions
    Returns:
        iterable: the generator object that produces interval models in order

    """
    # Sort the regression data
    x, y = tools.sort_points(x, y)

    init_model = _get_best_model(full_computation(x, y, computation_models))

    for submodel in _bisection_step(x, y, init_model, computation_models):
        yield submodel


def _bisection_step(x, y, last_model, computation_models):
    """The bisection step computation.

    Performs one computation step for bisection. Splits the interval set by x, y and tries to compute each
    half. In case of model change, the interval is split again and the process repeats. Otherwise the last
    model is used as a final model.


    Arguments:
        x(list): the list of x points coordinates
        y(list): the list of y points coordinates
        last_model(dict): the full interval model that is split
        computation_models(list): the list of Models values representing the models which will be computed
    Raises:
        GenericRegressionExceptionBase: derived versions which are used in the computation functions
    Returns:
        iterable: the generator object that produces interval result

    """
    # Split the interval and compute each one of them
    half_models = []
    parts = []
    for part_start, part_end in tools.split_sequence(len(x), 2):
        half_models.append(_get_best_model(full_computation(
            x[part_start:part_end], y[part_start:part_end], computation_models)))
        parts.append((part_start, part_end))

    # The half models are not different, return the full interval model
    if half_models[0]['model'] == last_model['model'] and half_models[1]['model'] == last_model['model']:
        yield last_model
        return

    if half_models[0]['model'] != last_model['model']:
        # First model is different, continue with bisection
        for submodel in _bisection_step(
                x[parts[0][0]:parts[0][1]], y[parts[0][0]:parts[0][1]], half_models[0], computation_models):
            yield submodel
    else:
        # First model is the same, but the second is not, return the half model
        yield half_models[0]

    if half_models[1]['model'] != last_model['model']:
        # Second model is different, continue with bisection
        for submodel in _bisection_step(
                x[parts[1][0]:parts[1][1]], y[parts[1][0]:parts[1][1]], half_models[1], computation_models):
            yield submodel
    else:
        # Second model is the same, but the first was not
        yield half_models[1]


def _transform_to_output_data(data, extra_keys=None):
    """Transforms the data dictionary into their output format - omitting computational details and keys that are
       not important for the result and it's further manipulation.

    The function provides dictionary with 'model', 'coeffs', 'r_square', 'plot_x', 'plot_y', 'len', 'x_max',
    'x_min', 'y_min' and 'y_max' keys taken from the data dictionary. The function also allows to specify extra
    keys to be included in the output dictionary. If certain key is missing in the data dictionary, then it's not
    included in the output dictionary.

    Arguments:
        data(dict): the data dictionary with results
        extra_keys(list of str): the extra keys to include
    Returns:
        dict: the output dictionary

    """
    # Specify the keys which should be in the output
    transform_keys = ['model', 'coeffs', 'r_square', 'plot_x', 'plot_y', 'len',
                      'x_min', 'x_max', 'y_min', 'y_max']
    if extra_keys is not None:
        transform_keys += extra_keys
    transformed = {key: data[key] for key in transform_keys if key in data}
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


def _compare_models_fit(old_gen, old_model, new_gen, new_model):
    """Compares two models and find the best fitting one.

    Arguments:
        old_gen(iter): the generator of first model
        old_model(dict): the first model
        new_gen(iter): the generator of second model
        new_model(dict): the second model
    Return:
        tuple: the best model generator and model specification

    """
    if old_model is None or old_model['r_square'] < new_model['r_square']:
        return new_gen, new_model
    else:
        return old_gen, old_model


def _get_best_model(model_gen):
    """Chooses best fitting model from model generator.

    Arguments:
        model_gen(iter): the model results generator
    Return:
        dict: the best fitting model

    """
    best_model = None
    # Compare the models results and choose the best fitting one
    for result in model_gen:
        _, best_model = _compare_models_fit(None, best_model, None, result)
    return best_model


def _build_uniform_regression_data_format(x, y, kwargs):
    """Creates the uniform regression data dictionary from the model properties and regression data points.

    The uniform data dictionary is used in the regression computation as it allows to build generic and
    easily extensible computational methods and models.

    Arguments:
        x(list): the list of x points coordinates
        y(list): the list of y points coordinates
        kwargs(dict): the regression model properties
    Return:
        dict: the uniform data dictionary
    """
    # Check the requirements
    tools.check_points(len(x), len(y), tools.MIN_POINTS_COUNT)
    tools.check_excess_arg(['x', 'y'], kwargs)

    kwargs['x'] = x
    kwargs['y'] = y
    # Initialize the data generator
    kwargs['data_gen'] = kwargs['data_gen'](kwargs)
    return kwargs
