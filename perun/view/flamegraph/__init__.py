"""`Flame graph` shows the relative consumption of resources w.r.t. to the trace of the resource
origin. The usage of flame graphs is for faster localization of resource consumption hot spots
and bottlenecks.
"""

import lazy_loader as lazy

__getattr__, __dir__, __all__ = lazy.attach_stub(__name__, __file__)

SUPPORTED_PROFILES = ["memory", "time"]
