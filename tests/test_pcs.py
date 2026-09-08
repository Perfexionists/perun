"""Collections of test for perun.logic.pcs package"""

from __future__ import annotations

# Standard Imports
import pytest

# Third-Party Imports

# Perun Imports
from perun.utils.exceptions import UnsupportedModuleException
import perun.selection.factory as select
from perun.selection.whole_repository_selection import WholeRepositorySelection


def test_selection(pcs_with_root):
    """Tests basic selection"""
    selection = select.selection()
    assert isinstance(selection, WholeRepositorySelection)

    with pytest.raises(UnsupportedModuleException):
        select.selection("nonexisting_selection")
