"""The public utility module.

"""

import numpy as np


def create_generic_legend(coefficients, r_squared=None):
    """Creates the figure legend for function specified by it's coefficients and optionally a r_square value.

    Arguments:
        coefficients(list): the list of function coefficients in descending order, e.g. [bn, ..., b1, b0]
        r_squared(float): the r^2 value for the function
    Returns:
        str: the function legend as a string

    """

    coefficients = np.trim_zeros(coefficients, 'f')
    func_legend = str()
    # Create record for each coefficient
    for i, coeff in enumerate(reversed(coefficients)):
        if coeff != 0.0:
            if i > 0:
                func_legend += ', '
            # Format the coefficient value
            func_legend += 'b{0} = {1:.2e}'.format(i, coeff)
    if r_squared is not None:
        # Format the r^2 value
        func_legend += '; r^2 = {0}'.format(round(r_squared, 3))
    return func_legend
