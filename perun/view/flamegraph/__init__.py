"""`Flame graph` shows the relative consumption of resources w.r.t. to the
trace of the resource origin. Currently it is limited to `memory` profiles
(however, the generalization of the module is in plan). The usage of flame
graphs is for faster localization of resource consumption hot spots and
bottlenecks.
"""

SUPPORTED_PROFILES = ["memory"]
