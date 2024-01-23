"""Collections of test for perun.select package"""

# Standard Imports
import pytest

# Third-Party Imports

# Perun Imports
from perun.select.abstract_base_selection import AbstractBaseSelection


def test_base_select():
    """Dummy test, that base selection is correctly installed and cannot be instantiated"""
    with pytest.raises(TypeError):
        _ = AbstractBaseSelection()
