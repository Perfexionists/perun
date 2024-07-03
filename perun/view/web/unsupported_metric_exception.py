class UnsupportedMetricException(Exception):
    """Exception is raised when labels for metric are not defined or metric is not supported by module"""
    def __init__(self, message):
        super().__init__(message)
