"""Tests for profile/query module.

Contains tests for query results of various valid / invalid profiles.
"""

import pytest
import perun.utils.exceptions as exceptions
import perun.profile.query as query
import tests.logic.commands.conftest as conf

__author__ = "Jiri Pavela"

# number of expected resource fields in memory profile
_MEMORY_RESOURCES_COUNT = 34
_COMPLEXITY_RESOURCES_COUNT = 26
_MODELS_COUNT = 10
_MEMORY_TRACE_IDX = 3
_MEMORY_UID_IDX = 5


def profile_filter(generator, rule):
    # Loop the generator and test the rule
    for profile in generator:
        if rule in profile[0]:
            return profile[1]
    # No match found
    return None


def sort_flattened_structure(structure):
    flattened_values = structure.split(', ')
    new_values = []
    for value in flattened_values:
        new_values.append(':'.join(sorted(value.split(':'))))
    return ', '.join(new_values)


def test_memory_prof_resources(query_profiles):
    # Acquire the memory query profile
    mem_profile = profile_filter(query_profiles, 'memory-2017-08-25-16-03-47.perf')
    assert mem_profile is not None

    # Get all resource fields of the memory profile
    resources = list(query.all_resources_of(mem_profile))
    assert len(resources) == _MEMORY_RESOURCES_COUNT


def test_memory_prof_resources_empty(query_profiles):
    # Acquire the memory query profile with empty resources
    mem_profile = profile_filter(query_profiles, 'memory-empty-resources.perf')
    assert mem_profile is not None

    # Get all resource fields of the memory profile
    resources = list(query.all_resources_of(mem_profile))
    assert len(resources) == 0


def test_complexity_prof_resources(query_profiles):
    # Acquire the complexity query profile
    complexity_profile = profile_filter(query_profiles, 'complexity-2017-08-25-19-19-16.perf')
    assert complexity_profile is not None

    # Get all resource fields of the complexity profile
    resources = list(query.all_resources_of(complexity_profile))
    assert len(resources) == _COMPLEXITY_RESOURCES_COUNT


def test_complexity_prof_resources_empty(query_profiles):
    # Acquire the complexity query profile with empty resources
    complexity_profile = profile_filter(query_profiles, 'complexity-empty-resources.perf')
    assert complexity_profile is not None

    # Get all resource fields of the complexity profile
    resources = list(query.all_resources_of(complexity_profile))
    assert len(resources) == 0


def test_resources_corrupted(query_profiles):
    # TODO: failed, add checks to query?
    # Acquire the query profile with corrupted global section
    corrupted_profile = profile_filter(query_profiles, 'corrupted-global.perf')
    assert corrupted_profile is not None

    # Get all resources in profile that has corrupted structure
    with pytest.raises(exceptions.IncorrectProfileFormatException):
        list(query.all_resources_of(corrupted_profile))


def test_all_models(query_profiles):
    # Acquire the models query profile
    models_profile = profile_filter(query_profiles, 'complexity-models.perf')
    assert models_profile is not None

    # Get all models in profile that contains them
    models = list(query.all_models_of(models_profile))
    assert len(models) == _MODELS_COUNT


def test_all_models_empty(query_profiles):
    # Acquire the complexity query profile
    models_profile = profile_filter(query_profiles, 'complexity-2017-08-25-19-19-16.perf')
    assert models_profile is not None

    # Get all models in profile that has none
    models = list(query.all_models_of(models_profile))
    assert len(models) == 0


def test_all_models_corrupted(query_profiles):
    # Acquire the query profile with corrupted global section
    corrupted_profile = profile_filter(query_profiles, 'corrupted-global.perf')
    assert corrupted_profile is not None

    # Get all models in profile that has corrupted structure
    with pytest.raises(exceptions.IncorrectProfileFormatException):
        list(query.all_models_of(corrupted_profile))


def test_all_items_of_memory_resources(query_profiles):
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


# test_all_items_of_memory_resources(conf.load_all_profiles_in("query_profiles"))
