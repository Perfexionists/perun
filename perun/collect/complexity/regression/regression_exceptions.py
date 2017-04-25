"""Regression exceptions module. Contains specific exceptions for regression analysis.

"""


class GenericRegressionExceptionBase(Exception):
    """Base class for all regression specific exception

    All specific exceptions should be derived from the base
    - this allows to catch all regression exceptions in one clause

    """
    def __init__(self, msg):
        """Base constructor with exception message"""
        self.msg = msg


class InvalidPointsException(GenericRegressionExceptionBase):
    """Raised when regression data points count is too low or the x and y coordinates count is different"""
    def __init__(self, x_len, y_len, threshold=2, msg=None):
        self.x_len = x_len
        self.y_len = y_len
        if msg is not None:
            self.msg = msg
        elif x_len != y_len:
            self.msg = "Points coordinates x and y have different lengths - x:{0}, y:{1}".format(x_len, y_len)
        elif x_len < threshold or y_len < threshold:
            self.msg = "Too few points coordinates to perform regression - x:{0}, y:{1}".format(x_len, y_len)


class InvalidSequenceSplit(GenericRegressionExceptionBase):
    """Raised when the sequence split would produce too few points to use in regression analysis"""
    def __init__(self, ratio, msg=None):
        self.ratio = ratio
        if msg is not None:
            self.msg = msg
        else:
            self.msg = "The sequence split would produce too few points: {0}".format(ratio)


class DataFormatExcessArgument(GenericRegressionExceptionBase):
    """Raised when data format has excess argument which may cause incorrect behaviour"""
    def __init__(self, argument, msg=None):
        self.argument = argument
        if msg is not None:
            self.msg = msg
        else:
            self.msg = "Excess argument in function (data loss warning): {0}".format(str(argument))


class DataFormatMissingArgument(GenericRegressionExceptionBase):
    """Raised when data format is missing required argument"""
    def __init__(self, argument, msg=None):
        self.argument = argument
        if msg is not None:
            self.msg = msg
        else:
            self.msg = "Expected argument missing: {0}".format(str(argument))


class DataFormatInvalidCoeffs(GenericRegressionExceptionBase):
    """Raised when data format contains unexpected number of coefficient"""
    def __init__(self, coeffs_count, msg=None):
        self.coeffs_count = coeffs_count
        if msg is not None:
            self.msg = msg
        else:
            self.msg = "Missing coefficients list or their count different from: {0}".format(str(coeffs_count))


class InvalidModelType(GenericRegressionExceptionBase):
    """Raised when invalid or unknown regression model is required"""
    def __init__(self, model, msg=None):
        self.model = model
        if msg is not None:
            self.msg = msg
        else:
            self.msg = "Invalid or unsupported regression model: {0}".format(str(model))
