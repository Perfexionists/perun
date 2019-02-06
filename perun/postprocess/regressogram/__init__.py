"""
Postprocessing of input profiles using the non-parametric method - regressogram.
This method serves for finding fitting models for trends in the captured
profiling resources using by constant function at the individual parts of
the whole interval.
"""

# TODO: Is it correct to support all types of profiles?
SUPPORTED_PROFILES = ['mixed|memory|time']

__author__ = 'Simon Stupinsky'
