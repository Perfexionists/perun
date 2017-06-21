"""Basic tests for profile converters module.

Tests basic functionality of creating other representations of profiles, like e.g for
heap and heat map visualizations, etc.
"""
import perun.utils.profile_converters as converters

__author__ = 'Tomas Fiedor'


def test_flame_graph(memory_profiles):
    """Test creation of flame graph format out of the profile of memory type

    Expecting no errors and returned list of lines representing the format by greg.
    """
    for memory_profile in memory_profiles:
        flame_graph = converters.create_flame_graph_format(memory_profile)

        line_no = 0
        for snap in memory_profile['snapshots']:
            line_no += len(list(filter(lambda item: item['subtype'] != 'free', snap['resources'])))

        for line in flame_graph:
            print(line)

        assert line_no == len(flame_graph)


def test_heap_map(memory_profiles):
    """Test creation of heap map out of the profile of memory type

    Expecting no errors and returned dictionary with internal format of the heap map
    """
    for memory_profile in memory_profiles:
        heap_map = converters.create_heap_map(memory_profile)
        assert len(heap_map['snapshots']) == len(memory_profile['snapshots'])


def test_heat_map(memory_profiles):
    """Test generation of the heat map information from the profile

    Expecting no errors and returned dictionary with the internal representation
    """
    for memory_profile in memory_profiles:
        heat_map = converters.create_heat_map(memory_profile)
        number_of_cells = (heat_map['stats']['max_address'] - heat_map['stats']['min_address'])
        assert len(heat_map['map']) == number_of_cells


def test_allocation_table(memory_profiles):
    """Test creation of allocations table

    Expecting no error and returned dictionary with allocation info
    """
    for memory_profile in memory_profiles:
        allocation_info = converters.create_allocations_table(memory_profile)
        assert len(allocation_info['snapshots']) > 0


def test_flow_table(memory_profiles):
    """Test creation of flow table

    Expecting no error and returned dictionary with some flow info
    """
    for memory_profile in memory_profiles:
        flow_info = converters.create_flow_table(memory_profile)
        assert len(flow_info['snapshots']) > 0
