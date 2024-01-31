"""Collections of test for perun.logic.pcs package"""
from __future__ import annotations

# Standard Imports
import pytest

# Third-Party Imports

# Perun Imports
from perun.utils.exceptions import UnsupportedModuleException
from perun.logic import pcs
from perun.select.whole_repository_selection import WholeRepositorySelection


def test_selection(pcs_with_root):
    """Tests basic selection"""
    selection = pcs.selection()
    assert isinstance(selection, WholeRepositorySelection)

    with pytest.raises(UnsupportedModuleException):
        pcs.selection("nonexisting_selection")
