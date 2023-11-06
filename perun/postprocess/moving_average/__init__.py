"""
Postprocessing of input profiles using the non-parametric method: moving average.
This method serves to analyze data points in the captured profiling resources
by creating a series of averages, eventually medians, of different subsets of
the full data set.
"""

SUPPORTED_PROFILES = ["mixed|memory|time"]
