"""A package for Perun-native profile.

Contains queries over profiles, storage and loading of the profile in the filesystem, transforming
the profiles, and converting profiles to different formats.
"""

import lazy_loader as lazy

__getattr__, __dir__, __all__ = lazy.attach_stub(__name__, __file__)
