"""A package for conversions between profile formats.

Each module is lazily loaded so that only the necessary dependencies are imported.
"""

import lazy_loader as lazy

__getattr__, __dir__, __all__ = lazy.attach_stub(__name__, __file__)
