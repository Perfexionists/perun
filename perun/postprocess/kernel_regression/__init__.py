"""A postprocessor that executing the kernel regression over the resources.

Postprocessing of inputs profiles using the kernel regression. Postprocessor,
implementing kernel regression offers several computational methods with
different approaches and different strategies to find optimal parameters.
"""

# TODO: Is it correct to support all types of profiles?
SUPPORTED_PROFILES = ['mixed|memory|time']

__author__ = 'Simon Stupinsky'
