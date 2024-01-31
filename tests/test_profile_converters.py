"""Basic tests for profile convert module.

Tests basic functionality of creating other representations of profiles, like e.g for
heap and heat map visualizations, etc.
"""
from __future__ import annotations

# Standard Imports

# Third-Party Imports
import pytest

# Perun Imports
from perun.profile import convert
from perun.utils import exceptions
import perun.testing.utils as test_utils


def test_convert_models_to_dataframe():
    """Test conversion of models"""
    # Acquire the models query profile
    models_profile = test_utils.load_profile("postprocess_profiles", "complexity-models.perf")
    assert models_profile is not None

    df = convert.models_to_pandas_dataframe(models_profile)
    assert sorted(list(df)) == sorted(
        [
            "coeffs",
            "coeffs:b0",
            "coeffs:b1",
            "coeffs:b2",
            "method",
            "model",
            "r_square",
            "uid",
            "x_end",
            "x_start",
        ]
    )
    assert len(df) == 12


def test_flame_graph(memory_profiles):
    """Test creation of flame graph format out of the profile of memory type

    Expecting no errors and returned list of lines representing the format by greg.
    """
    for memory_profile in memory_profiles:
        flame_graph = convert.to_flame_graph_format(memory_profile)

        line_no = 0
        for _, snap in memory_profile.all_snapshots():
            line_no += len(list(filter(lambda item: item["subtype"] != "free", snap)))

        for line in flame_graph:
            print(line)

        assert line_no == len(flame_graph)


def test_coefficients_to_points_correct():
    """Test correct conversion from models coefficients to points that can be used for plotting.

    Expecting no errors and updated dictionary
    """
    # Acquire the models query profile
    models_profile = test_utils.load_profile("postprocess_profiles", "complexity-models.perf")
    assert models_profile is not None

    # Get all models and perform the conversion on all of them
    # TODO: add more advanced checks
    models = list(models_profile.all_models())
    for model in models:
        data = convert.plot_data_from_coefficients_of(model[1])
        assert "plot_x" in data
        assert "plot_y" in data


def test_coefficients_to_points_corrupted_model():
    """Test conversion from models coefficients to points on a profile with invalid model.

    Expecting to catch InvalidModelException exception.
    """
    # Acquire the corrupted models query profile with invalid model
    models_profile = test_utils.load_profile(
        "postprocess_profiles", "complexity-models-corrupted-model.perf"
    )
    assert models_profile is not None

    # Get all models and perform the conversion on all of them
    models = list(models_profile.all_models())
    with pytest.raises(exceptions.InvalidModelException) as exc:
        for model in models:
            convert.plot_data_from_coefficients_of(model[1])
    assert "Invalid or unsupported regression model: invalid_model." in str(exc.value)
