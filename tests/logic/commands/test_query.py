"""Tests for profile/query module.

Contains tests for query results of various valid / invalid profiles.
"""

import pytest
import perun.utils.exceptions as exceptions
import perun.profile.query as query


__author__ = "Jiri Pavela"


# number of expected resource fields in memory profile
_MEMORY_RESOURCES_COUNT = 34
# number of expected resource fields in complexity profile
_COMPLEXITY_RESOURCES_COUNT = 26
# number of models expected in models profile
_MODELS_COUNT = 10
# number of resource items in memory profile
_MEMORY_RESOURCE_ITEMS_COUNT = 9
# index of trace record in sorted memory resources
_MEMORY_TRACE_IDX = 3
# index of uid record in sorted memory resources
_MEMORY_UID_IDX = 5

# number of unique values in 'amount' key in memory profile
_MEMORY_AMOUNT_COUNT = 6
# expected 'amount' list of memory profile
_MEMORY_AMOUNT_LIST = [0, 4, 8, 12, 16, 20]
# number of unique values in 'trace::function' key in memory profile
_MEMORY_TRACE_FUNCTION_COUNT = 13
# expected 'trace::function' list of memory profile
_MEMORY_TRACE_FUNCTION_LIST = ['__libc_start_main', '_start', 'calloc', 'factorial', 'foo1', 'foo2',
                           'free', 'main', 'malloc', 'memalign', 'posix_memalign', 'realloc',
                           'valloc']
# number of unique values in 'uid:line' key in memory profile
_MEMORY_UID_LINE_COUNT = 13
# expected 'uid:line' list of memory profile
_MEMORY_UID_LINE_LIST = [23, 25, 31, 36, 37, 45, 49, 53, 55, 59, 63, 67, 71]

# number of unique values in 'model' key in models profile
_MODELS_MODEL_COUNT = 5
# expected 'model' list of models profile
_MODELS_MODEL_LIST = ['exponential', 'linear', 'logarithmic', 'power', 'quadratic']

# number of unique values in 'coeffs::name' key in models profile
_MODELS_COEFFS_NAME_COUNT = 2
# expected 'coeffs::name' list of models profile
_MODELS_COEFFS_NAME_LIST = ['b0', 'b1']


def profile_filter(generator, rule):
    """Finds concrete profile by the rule in profile generator.

    Arguments:
        generator(generator): stream of profiles as tuple: (name, dict)
        rule(str): string to search in the name

    Returns:
        dict: first profile with name containing the rule
    """
    # Loop the generator and test the rule
    for profile in generator:
        if rule in profile[0]:
            return profile[1]
    # No match found
    return None


def sort_flattened_structure(structure):
    """Lexicographically sorts elements (i.e. primitive values) in the flattened structure
    with ':' and ',' symbols.

    Arguments:
        structure(str): the flattened structure

    Returns:
        str: flattened structure with sorted elements separated by the ':' and ','
    """
    # Split list values
    flattened_values = structure.split(',')
    new_values = []
    for value in flattened_values:
        # Sort all ':'-separated values in one list value
        new_values.append(':'.join(sorted(value.split(':'))))
    # Join all values back together
    return ','.join(new_values)


def test_memory_prof_resources(query_profiles):
    """Test 'all_resources_of' on memory profile that has some.

    Expected _MEMORY_RESOURCES_COUNT resources.
    """
    # Acquire the memory query profile
    mem_profile = profile_filter(query_profiles, 'memory-2017-08-25-16-03-47.perf')
    assert mem_profile is not None

    # Get all resource fields of the memory profile
    resources = list(query.all_resources_of(mem_profile))
    assert len(resources) == _MEMORY_RESOURCES_COUNT


def test_memory_prof_resources_empty(query_profiles):
    """Test 'all_resources_of' on memory profile that has none.

    Expected 0 resources.
    """
    # Acquire the memory query profile with empty resources
    mem_profile = profile_filter(query_profiles, 'memory-empty-resources.perf')
    assert mem_profile is not None

    # Get all resource fields of the memory profile
    resources = list(query.all_resources_of(mem_profile))
    assert len(resources) == 0


def test_complexity_prof_resources(query_profiles):
    """Test 'all_resources_of' on complexity profile that has some.

    Expected _COMPLEXITY_RESOURCES_COUNT resources.
    """
    # Acquire the complexity query profile
    complexity_profile = profile_filter(query_profiles, 'complexity-2017-08-25-19-19-16.perf')
    assert complexity_profile is not None

    # Get all resource fields of the complexity profile
    resources = list(query.all_resources_of(complexity_profile))
    assert len(resources) == _COMPLEXITY_RESOURCES_COUNT


def test_complexity_prof_resources_empty(query_profiles):
    """Test 'all_resources_of' on complexity profile that has none.

    Expected 0 resources.
    """
    # Acquire the complexity query profile with empty resources
    complexity_profile = profile_filter(query_profiles, 'complexity-empty-resources.perf')
    assert complexity_profile is not None

    # Get all resource fields of the complexity profile
    resources = list(query.all_resources_of(complexity_profile))
    assert len(resources) == 0


def test_resources_corrupted(query_profiles):
    """Test 'all_resources_of' on corrupted profiles.

    Expected IncorrectProfileFormatException-s.
    """
    # Acquire the query profile with corrupted global section
    corrupted_profile = profile_filter(query_profiles, 'corrupted-global.perf')
    assert corrupted_profile is not None

    # Get all resources in profile that has corrupted global structure
    with pytest.raises(exceptions.IncorrectProfileFormatException):
        list(query.all_resources_of(corrupted_profile))

    # Acquire the query profile with corrupted global section
    corrupted_profile = profile_filter(query_profiles, 'corrupted-snapshots.perf')
    assert corrupted_profile is not None

    # Get all resources in profile that has corrupted snapshots structure
    with pytest.raises(exceptions.IncorrectProfileFormatException):
        list(query.all_resources_of(corrupted_profile))


def test_all_models(query_profiles):
    """Test 'all_models_of' on profile with models.

    Expected _MODELS_COUNT models.
    """
    # Acquire the models query profile
    models_profile = profile_filter(query_profiles, 'complexity-models.perf')
    assert models_profile is not None

    # Get all models in profile that contains them
    models = list(query.all_models_of(models_profile))
    assert len(models) == _MODELS_COUNT


def test_all_models_empty(query_profiles):
    """Test 'all_models_of' on profile without models.

    Expected 0 models.
    """
    # Acquire the complexity query profile
    models_profile = profile_filter(query_profiles, 'complexity-2017-08-25-19-19-16.perf')
    assert models_profile is not None

    # Get all models in profile that has none
    models = list(query.all_models_of(models_profile))
    assert len(models) == 0


def test_all_models_corrupted(query_profiles):
    """Test 'all_models_of' on corrupted profile.

    Expected IncorrectProfileFormatException.
    """
    # Acquire the query profile with corrupted global section
    corrupted_profile = profile_filter(query_profiles, 'corrupted-global.perf')
    assert corrupted_profile is not None

    # Get all models in profile that has corrupted structure
    with pytest.raises(exceptions.IncorrectProfileFormatException):
        list(query.all_models_of(corrupted_profile))


def test_all_items_of_memory_resources(query_profiles):
    """Test 'all_items_of' on profile with resources.

    Expected _MEMORY_RESOURCE_ITEMS_COUNT items and content match.
    """
    # Acquire the memory query profile
    mem_profile = profile_filter(query_profiles, 'memory-2017-08-25-16-03-47.perf')
    assert mem_profile is not None

    # Get the first resource in the profile
    _, resources = next(query.all_resources_of(mem_profile))
    items = list(query.all_items_of(resources))

    # Sort the resources and flattened key to allow comparison
    items.sort()
    items[_MEMORY_TRACE_IDX] = (items[_MEMORY_TRACE_IDX][0],
                                sort_flattened_structure(items[_MEMORY_TRACE_IDX][1]))
    items[_MEMORY_UID_IDX] = (items[_MEMORY_UID_IDX][0],
                              sort_flattened_structure(items[_MEMORY_UID_IDX][1]))
    # TODO: compare
    assert len(items) == _MEMORY_RESOURCE_ITEMS_COUNT


# TODO: Speed up the pull request, add more advanced tests later


def test_unique_resource_values(query_profiles):
    """Test 'unique_resource_values_of' on resource.

    Expected no exception, all assertions passed.
    """
    # Acquire the memory query profile
    mem_profile = profile_filter(query_profiles, 'memory-2017-08-25-16-03-47.perf')
    assert mem_profile is not None

    # Test the searching in first level of hierarchy
    unique_values = list(query.unique_resource_values_of(mem_profile, 'amount'))
    unique_values.sort()
    assert len(unique_values) == _MEMORY_AMOUNT_COUNT
    assert unique_values == _MEMORY_AMOUNT_LIST

    # Test the searching in dictionary -> list hierarchy
    unique_values = list(query.unique_resource_values_of(mem_profile, 'trace::function'))
    unique_values.sort()
    assert len(unique_values) == _MEMORY_TRACE_FUNCTION_COUNT
    assert unique_values == _MEMORY_TRACE_FUNCTION_LIST

    # Test the searching in dictionaries hierarchy
    unique_values = list(query.unique_resource_values_of(mem_profile, 'uid:line'))
    unique_values.sort()
    assert len(unique_values) == _MEMORY_UID_LINE_COUNT
    assert unique_values == _MEMORY_UID_LINE_LIST

    # Test key that is not in the resources
    unique_values = list(query.unique_resource_values_of(mem_profile, 'test:testing::test'))
    assert len(unique_values) == 0


def test_unique_model_values(query_profiles):
    """Test 'unique_model_values_of' on model.

    Expected no exception, all assertions passed.
    """
    # Acquire the models query profile
    models_profile = profile_filter(query_profiles, 'complexity-models.perf')
    assert models_profile is not None

    # Test the searching in first level of hierarchy
    unique_values = list(query.unique_model_values_of(models_profile, 'model'))
    unique_values.sort()
    assert len(unique_values) == _MODELS_MODEL_COUNT
    assert unique_values == _MODELS_MODEL_LIST

    # Test the searching in dictionary -> list hierarchy
    unique_values = list(query.unique_model_values_of(models_profile, 'coeffs::name'))
    unique_values.sort()
    assert len(unique_values) == _MODELS_COEFFS_NAME_COUNT
    assert unique_values == _MODELS_COEFFS_NAME_LIST

    # Test key that is not in the models
    unique_values = list(query.unique_resource_values_of(models_profile, 'test'))
    assert len(unique_values) == 0
