"""A postprocessor that attempts to classify resources to clusters.

The main usage of this postprocessors is to prepare any kind of profile for further
postprocessing, mainly by :ref:`postprocessors-regression-analysis`. The clusterization
is either realized w.r.t the sorted order of the resources or sliding window,
with parametric width and height.
"""

SUPPORTED_PROFILES = ["memory", "mixed", "time"]

SUPPORTED_STRATEGIES = ["sort_order", "sliding_window"]
DEFAULT_STRATEGY = SUPPORTED_STRATEGIES[0]
