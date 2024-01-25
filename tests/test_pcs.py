"""Collections of test for perun.logic.pcs package"""

# Standard Imports
import pytest

# Third-Party Imports

# Perun Imports
from perun.logic import pcs
from perun.select.whole_repository_selection import WholeRepositorySelection


def test_selection(pcs_with_root):
    """Tests basic selection"""
    selection = pcs.selection()
    assert isinstance(selection, WholeRepositorySelection)

    with pytest.raises(SystemExit):
        pcs.selection("nonexisting_selection")
