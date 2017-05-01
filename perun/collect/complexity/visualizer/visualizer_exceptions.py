"""Visualization specific exception hierarchy similar to the regression hierarchy.

"""


class VisualizationExceptionBase(Exception):
    """The hierarchy base exception, should be used for exception catching."""
    def __init__(self, msg):
        self.msg = msg


class VisualizationDataMissingArgument(VisualizationExceptionBase):
    """Raised when argument is missing in the kwargs or collection."""
    def __init__(self, argument, msg=None):
        self.argument = argument
        if msg is not None:
            self.msg = msg
        else:
            self.msg = "Expected argument missing: {0}".format(str(argument))
