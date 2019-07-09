"""Basic tests for profile convert module.

Tests basic functionality of creating other representations of profiles, like e.g for
heap and heat map visualizations, etc.
"""
import pytest
import perun.utils.exceptions as exceptions
import perun.profile.convert as convert
import perun.profile.query as query

__author__ = 'Tomas Fiedor'
__coauthored__ = 'Jiri Pavela'


# TODO: duplication, where to store common useful functions for tests?
def profile_filter(generator, rule):
    """Finds concrete profile by the rule in profile generator.

    Arguments:
        generator(generator): stream of profiles as tuple: (name, dict)
        rule(str): string to search in the name

    Returns:
        Profile: first profile with name containing the rule
    """
    # Loop the generator and test the rule
    for profile in generator:
        if rule in profile[0]:
            return profile[1]
    # No match found
    return None


def test_flame_graph(memory_profiles):
    """Test creation of flame graph format out of the profile of memory type

    Expecting no errors and returned list of lines representing the format by greg.
    """
    for memory_profile in memory_profiles:
        flame_graph = convert.to_flame_graph_format(memory_profile)

        line_no = 0
        for _, snap in memory_profile.all_snapshots():
            line_no += len(list(filter(lambda item: item['subtype'] != 'free', snap)))

        for line in flame_graph:
            print(line)

        assert line_no == len(flame_graph)


def test_heap_map(memory_profiles):
    """Test creation of heap map out of the profile of memory type

    Expecting no errors and returned dictionary with internal format of the heap map
    """
    for memory_profile in memory_profiles:
        heap_map = convert.to_heap_map_format(memory_profile)
        assert len(heap_map['snapshots']) == len(list(memory_profile.all_snapshots()))


def test_heat_map(memory_profiles):
    """Test generation of the heat map information from the profile

    Expecting no errors and returned dictionary with the internal representation
    """
    for memory_profile in memory_profiles:
        heat_map = convert.to_heat_map_format(memory_profile)
        number_of_cells = (heat_map['stats']['max_address'] - heat_map['stats']['min_address'])
        assert len(heat_map['map']) == number_of_cells


def test_coefficients_to_points_correct(postprocess_profiles):
    """ Test correct conversion from models coefficients to points that can be used for plotting.

    Expecting no errors and updated dictionary
    """
    # Acquire the models query profile
    models_profile = profile_filter(postprocess_profiles, 'complexity-models.perf')
    assert models_profile is not None

    # Get all models and perform the conversion on all of them
    # TODO: add more advanced checks
    models = list(models_profile.all_models())
    for model in models:
        data = convert.plot_data_from_coefficients_of(model[1])
        assert 'plot_x' in data
        assert 'plot_y' in data


def test_coefficients_to_points_corrupted_model(postprocess_profiles):
    """ Test conversion from models coefficients to points on a profile with invalid model.

    Expecting to catch InvalidModelException exception.
    """
    # Acquire the corrupted models query profile with invalid model
    models_profile = profile_filter(postprocess_profiles, 'complexity-models-corrupted-model.perf')
    assert models_profile is not None

    # Get all models and perform the conversion on all of them
    models = list(models_profile.all_models())
    with pytest.raises(exceptions.InvalidModelException) as exc:
        for model in models:
            convert.plot_data_from_coefficients_of(model[1])
    assert 'Invalid or unsupported regression model: invalid_model.' in str(exc.value)
