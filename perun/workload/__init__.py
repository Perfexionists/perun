"""Package containing generators of workloads.

In previous Perun version, the workloads were considered to be string supplied by the user.
Now, this has been changed to a set of generators, that can generate a wider range of values and
also serve as missing independent variable.

This package contains the general generator object and the concrete generators of workload, such
as the string workload, integer workload, etc.
"""
__author__ = 'Tomas Fiedor'
