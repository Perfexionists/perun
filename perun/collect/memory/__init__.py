"""Memory collector collects allocations of C/C++ functions, target addresses
of allocations, type of allocations, etc. The collected data are suitable for
visualiation using e.g. :ref:`views-heapmap`.
"""

COLLECTOR_TYPE = 'memory'
COLLECTOR_DEFAULT_UNITS = {
    'memory': 'B'
}

__author__ = 'Radim Podola'
