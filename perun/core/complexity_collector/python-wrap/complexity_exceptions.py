""" The exception module for complexity collector.

"""


class UnexpectedPrototypeSyntaxError(Exception):
    """ Raised when the function prototype syntax is somehow different than expected """
    pass


class TraceLogCallStackError(Exception):
    """ Raised when the trace log has invalid overlapping function calls and exits """
    pass
