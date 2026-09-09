"""
Adapter for selecting methods based on specification
"""

from __future__ import annotations

# Standard Imports
from typing import Optional

# Third-Party Imports

# Perun Imports
from perun.logic import config
from perun.utils import decorators
from perun.selection import whole_repository_selection, abstract_base_selection
from perun.utils.exceptions import UnsupportedModuleException


@decorators.singleton_with_args
def selection(
    selection_type: Optional[str] = None,
) -> abstract_base_selection.AbstractBaseSelection:
    """Factory method for creating selection method

    Currently, supports:
      1. Whole Repository Selection: selects everything in the repository
    """
    if selection_type is None:
        selection_type = config.lookup_key_recursively(
            "selection_method", "whole_repository_selection"
        )

    if selection_type == "whole_repository_selection":
        return whole_repository_selection.WholeRepositorySelection()

    raise UnsupportedModuleException(selection_type)
