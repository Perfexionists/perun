"""Module with functions used for derived models computation.

Some models may depend on results of regression models computed previously by
standard regression analysis. Derived computations are more of a heuristics used
for special cases.

"""

import perun.postprocess.regression_analysis.tools as tools


def derived_const(analysis, const_ref, **_):
    """The computation of a constant model based on a linear regression model.

    Current implementation is based on a assumption that linear model with
    very small b1 (slope) coefficient and small R^2 coefficient is similar
    to the constant model and can be used in estimation of its parameters.

    We use a slope threshold value that produces modification coefficient
    based on a deviation from the threshold. Two scenarios may happen:

    1. slope is bigger than threshold
     - compute the multiple of the slopes divided by 10 and add 1 if
       the multiple is below 1, then use this as a modification coefficient
     - divide the 1 - (linear)R^2 by the coefficient

    2. slope is smaller than threshold
     - subtract the slope from the threshold, multiply it by the inverted
       value of the threshold and add 1
     - multiply the 1 - (linear)R^2 by the coefficient

    :param list of dict analysis: computed regression models
    :param dict const_ref: the constant model template from _MODELS dictionary
    :returns iterable: generator which produces constant model for every computed linear model
    """
    # Filter the required models from computed regression models
    analysis = _filter_by_models(analysis, const_ref['required'])
    # Set to default threshold if value is invalid
    if const_ref['b1_threshold'] <= 0:
        const_ref['b1_threshold'] = _DEFAULT_THRESHOLD

    # Compute const model for every linear
    for result in analysis:
        # Check the keys in the result dictionary
        tools.validate_dictionary_keys(
            result, ['r_square', 'coeffs', 'y_sum', 'pts_num', 'x_interval_start',
                     'x_interval_end', 'uid', 'method'], [])

        # Duplicate the constant model template
        const = const_ref.copy()
        r = 1 - result['r_square']
        slope = abs(result['coeffs'][1])

        # Compute the modification coefficient
        if slope > const['b1_threshold']:
            # b1 bigger than threshold, the modifier should reduce the fitness of the const model
            coeff = (slope / const['b1_threshold']) / 10
            if coeff < 1:
                coeff += 1
            r /= coeff
        else:
            # b1 smaller than threshold, the modifier should increase the fitness
            coeff = (1 / const['b1_threshold']) * (const['b1_threshold'] - slope) + 1
            r *= coeff

        # Truncate the r value if needed
        if r > 1:
            r = 1
        elif r < 0:
            r = 0

        # Build the const model record
        const['r_square'] = r
        const['x_interval_start'] = result['x_interval_start']
        const['x_interval_end'] = result['x_interval_end']
        const['coeffs'] = [result['y_sum'] / result['pts_num'], 0]
        const['uid'] = result['uid']
        const['method'] = result['method']
        yield const


def _filter_by_models(analysis, models):
    """Filters regression results by computed models.

    :param list of dict analysis: the computed regression models
    :param list of str models: the list of models to filter from the analysis
    :returns list: the filtered analysis results
    """
    # Filter the required models from the analysis list
    return list(filter(lambda m: 'model' in m and m['model'] in models, analysis))


# Use default threshold value if the provided is invalid
_DEFAULT_THRESHOLD = 0.001
