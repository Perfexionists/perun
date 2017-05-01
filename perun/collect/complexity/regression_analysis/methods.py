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
