"""Complexity collector collects running times of C/C++ functions along with
the sizes of the structures they were executed on. The collected data are
suitable for further postprocessing using the regression analysis and
visualization by scatter plots.
"""

COLLECTOR_TYPE = "mixed"
COLLECTOR_DEFAULT_UNITS = {"mixed(time delta)": "ms"}
