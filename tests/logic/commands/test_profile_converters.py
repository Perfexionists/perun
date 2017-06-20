
import perun.core.logic.profile as profiles
import perun.utils.profile_converters as converters

__author__ = 'Tomas Fiedor'


def test_flame_graph(valid_profile_pool):
    """Test creation of flame graph format out of the profile of memory type

    Expecting no errors and returned list of lines representing the format by greg.
    """
    for valid_profile in valid_profile_pool:
        loaded_profile = profiles.load_profile_from_file(valid_profile, is_raw_profile=True)

        if loaded_profile['header']['type'] != 'memory':
            continue

        flame_graph = converters.create_flame_graph_format(loaded_profile)

        line_no = 0
        for snap in loaded_profile['snapshots']:
            line_no += len(list(filter(lambda alloc: alloc['subtype'] != 'free', snap['resources'])))

        for line in flame_graph:
            print(line)

        assert line_no == len(flame_graph)


def test_heap_map(valid_profile_pool):
    """Test creation of heap map out of the profile of memory type

    Expecting no errors and returned dictionary with internal format of the heap map
    """
    for valid_profile in valid_profile_pool:
        loaded_profile = profiles.load_profile_from_file(valid_profile, is_raw_profile=True)

        if loaded_profile['header']['type'] != 'memory':
            continue

        heap_map = converters.create_heap_map(loaded_profile)
        assert len(heap_map['snapshots']) == len(loaded_profile['snapshots'])


def test_heat_map(valid_profile_pool):
    """Test generation of the heat map information from the profile

    Expecting no errors and returned dictionary with the internal representation
    """
    for valid_profile in valid_profile_pool:
        loaded_profile = profiles.load_profile_from_file(valid_profile, is_raw_profile=True)

        if loaded_profile['header']['type'] != 'memory':
            continue

        heat_map = converters.create_heat_map(loaded_profile)
        print(heat_map)
        number_of_cells = (heat_map['stats']['max_address'] - heat_map['stats']['min_address'])
        assert len(heat_map['map']) == number_of_cells


def test_allocation_table(valid_profile_pool):
    """Test creation of allocations table

    Expecting no error and returned dictionary with allocation info
    """
    for valid_profile in valid_profile_pool:
        loaded_profile = profiles.load_profile_from_file(valid_profile, is_raw_profile=True)

        if loaded_profile['header']['type'] != 'memory':
            continue

        allocation_info = converters.create_allocations_table(loaded_profile)
        assert len(allocation_info['snapshots']) > 0


def test_flow_table(valid_profile_pool):
    """Test creation of flow table

    Expecting no error and returned dictionary with some flow info
    """
    for valid_profile in valid_profile_pool:
        loaded_profile = profiles.load_profile_from_file(valid_profile, is_raw_profile=True)

        if loaded_profile['header']['type'] != 'memory':
            continue

        flow_info = converters.create_flow_table(loaded_profile)
        assert len(flow_info['snapshots']) > 0
