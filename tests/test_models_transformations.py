"""Basic tests for regression analysis extensions and transformations."""

from __future__ import annotations

# Standard Imports

# Third-Party Imports
import pytest

# Perun Imports
from perun.utils import exceptions
from perun.postprocess.regression_analysis import regression_models


def test_transformation_mapping():
    """Test the transformation mapping for existing and non existing model.

    Expecting no exceptions or errors.
    """
    # First test existing model
    transformations = regression_models.get_supported_transformations("linear")
    assert transformations == ["plot_model"]

    # Test invalid model
    transformations = regression_models.get_supported_transformations("invalid")
    assert not transformations


def test_transformation_data():
    """Test the transformation data mapping for various inputs.

    Expecting 1) no error, 2) exception, 3) exception
    """
    # First test correct combination
    data = regression_models.get_transformation_data_for("linear", "plot_model")
    assert data

    # Test invalid model
    with pytest.raises(exceptions.InvalidModelException) as exc:
        regression_models.get_transformation_data_for("invalid", "plot_model")
    assert "Invalid or unsupported regression model: invalid." in str(exc.value)

    # Test invalid transformation
    with pytest.raises(exceptions.InvalidTransformationException) as exc:
        regression_models.get_transformation_data_for("linear", "invalid")
    assert "Invalid or unsupported transformation: invalid for model: linear." in str(exc.value)
