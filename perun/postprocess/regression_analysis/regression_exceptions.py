"""Regression exceptions module. Contains specific exceptions for regression analysis.

"""


class DictionaryKeysValidationFailed(Exception):
    """Raised when validated dictionary is actually not a dictionary or has missing/excess keys"""
    def __init__(self, dictionary, missing_keys, excess_keys):
        """
        Arguments:
            dictionary(dict): the validated dictionary
            missing_keys(list): list of missing keys in the dictionary
            excess_keys(list): list of excess forbidden keys in the dictionary
        """
        if type(dictionary) is not dict:
            self.msg = "Validated object '{0}' is not a dictionary.".format(dictionary)
        elif not missing_keys:
            self.msg = "Validated dictionary '{0}' has excess forbidden keys: '{1}'.".format(
                dictionary, ', '.join(excess_keys))
        elif not excess_keys:
            self.msg = "Validated dictionary '{0}' is missing required keys: '{1}'.".format(
                dictionary, ', '.join(missing_keys))
        else:
            self.msg = "Validated dictionary '{0}' has excess forbidden keys: '{1}' "
            "and is missing required keys: '{2}'.".format(dictionary, ', '.join(excess_keys), ', '.join(missing_keys))


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
            self.msg = "Points coordinates x and y have different lengths - x:{0}, y:{1}.".format(x_len, y_len)
        elif x_len < threshold or y_len < threshold:
            self.msg = "Too few points coordinates to perform regression - x:{0}, y:{1}.".format(x_len, y_len)


class InvalidSequenceSplitException(GenericRegressionExceptionBase):
    """Raised when the sequence split would produce too few points to use in regression analysis"""
    def __init__(self, ratio, msg=None):
        self.ratio = ratio
        if msg is not None:
            self.msg = msg
        else:
            self.msg = "Too few points would be produced by splitting the data into {0} parts.".format(ratio)


class InvalidCoeffsException(GenericRegressionExceptionBase):
    """Raised when data format contains unexpected number of coefficient"""
    def __init__(self, coeffs_count, msg=None):
        self.coeffs_count = coeffs_count
        if msg is not None:
            self.msg = msg
        else:
            self.msg = "Missing coefficients list or their count different from: {0}.".format(str(coeffs_count))


class InvalidModelException(GenericRegressionExceptionBase):
    """Raised when invalid or unknown regression model is required"""
    def __init__(self, model, msg=None):
        self.model = model
        if msg is not None:
            self.msg = msg
        else:
            self.msg = "Invalid or unsupported regression model: {0}.".format(str(model))
