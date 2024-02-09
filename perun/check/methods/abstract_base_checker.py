"""Abstract Base Class for checking for degradations.

Each checker has to implement single method called:
  1. `check`: which takes two profiles (baseline and target)
      and returns iterable of degradations
"""
from __future__ import annotations

# Standard Imports
from abc import abstractmethod, ABC
from typing import TYPE_CHECKING, Any, Iterable

# Third-Party Imports

# Perun Imports
if TYPE_CHECKING:
    from perun.profile.factory import Profile
    from perun.utils.structs import DegradationInfo


class AbstractBaseChecker(ABC):
    """Abstract Base Class for all checkers to implement"""

    @abstractmethod
    def check(
        self, baseline_profile: Profile, target_profile: Profile, **kwargs: Any
    ) -> Iterable[DegradationInfo]:
        """Runs the checking method"""
