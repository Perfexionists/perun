""" Basic tests for regression analysis extensions and transformations.

"""

import pytest
import perun.utils.exceptions as exceptions
import perun.postprocess.regression_analysis.regression_models as models


def test_transformation_mapping():
    """Test the transformation mapping for existing and non existing model.

    Expecting no exceptions or errors.
    """
    # First test existing model
    transformations = models.get_supported_transformations("linear")
    assert transformations == ["plot_model"]

    # Test invalid model
    transformations = models.get_supported_transformations("invalid")
    assert not transformations


def test_transformation_data():
    """Test the transformation data mapping for various inputs.

    Expecting 1) no error, 2) exception, 3) exception
    """
    # First test correct combination
    data = models.get_transformation_data_for("linear", "plot_model")
    assert data

    # Test invalid model
    with pytest.raises(exceptions.InvalidModelException) as exc:
        models.get_transformation_data_for("invalid", "plot_model")
    assert "Invalid or unsupported regression model: invalid." in str(exc.value)

    # Test invalid transformation
    with pytest.raises(exceptions.InvalidTransformationException) as exc:
        models.get_transformation_data_for("linear", "invalid")
    assert "Invalid or unsupported transformation: invalid for model: linear." in str(exc.value)
