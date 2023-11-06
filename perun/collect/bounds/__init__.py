"""Automatic analysis of resource bounds of C programs.

Bounds collector employs a technique of Loopus tool (see loopus-site_), which performs an amortized
analysis of input C program. Loopus is limited to integer programs only, and for each function and
for each loop it computes a symbolic bound (e.g. 2*n + max(0, m)). Moreover, it computes the big-O
notation highlighting the main source of the complexity.

.. _loopus-site: https://forsyte.at/software/loopus/page/11/
"""

COLLECTOR_TYPE = "time"
COLLECTOR_DEFAULT_UNITS = {"bound": "iterations"}
