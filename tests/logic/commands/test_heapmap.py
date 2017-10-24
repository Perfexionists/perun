"""Basic tests for heap and heap map. Tests both logic and outputs to the terminal.

Uses custom mock object for curses, that implements basic stuff.
"""

import curses
from copy import deepcopy

import perun.profile.convert as convert
import perun.view.heapmap.heap_map as heap_map
import perun.view.heapmap.heap_map_colors as heap_colours


def donothing(*_):
    """Helper function for monkeypatching stuff to do nothing"""
    pass


def returnnothing(*_):
    """Helper function for monkeypatching stuff to return nothing"""
    return ''


def test_heat_map(mock_curses_window, monkeypatch, memory_profiles):
    """Test heap map without the logic and anything, hopefully will work

    Expecting no error and some layer of testing
    """
    monkeypatch.setattr(curses, 'curs_set', donothing)
    monkeypatch.setattr(curses, 'color_pair', returnnothing)

    for memory_profile in memory_profiles:
        heat_map_representation = convert.to_heat_map_format(memory_profile)
        hm_visualization = heap_map.HeapMapVisualization(
            mock_curses_window, heat_map_representation, heap_colours.HeapMapColors.NO_COLORS
        )
        hm_visualization.draw_heat_map()

        str_window = str(mock_curses_window)
        assert str(heat_map_representation['stats']['min_address']) in str_window
        # Correctly shows the ticks
        for tick in map(str, range(0, 110, 17)):
            assert tick in str_window
        assert 'HEAT INFO' in str_window
        assert "Number of accesses" in str_window


def test_heap_map(mock_curses_window, monkeypatch, memory_profiles):
    """Test heap map without the logic and anything, according to the mock window

    Expecting no error and some output to the mocked curses window
    """
    monkeypatch.setattr(curses, 'curs_set', donothing)
    monkeypatch.setattr(curses, 'color_pair', returnnothing)

    for memory_profile in memory_profiles:
        heap_map_representation = convert.to_heap_map_format(memory_profile)
        hm_visualization = heap_map.HeapMapVisualization(
            mock_curses_window, heap_map_representation, heap_colours.HeapMapColors.NO_COLORS
        )
        hm_visualization.draw_heap_map()
        hm_visualization.following_snapshot(heap_map.HeapMapVisualization.NEXT_SNAPSHOT)

        str_window = str(mock_curses_window)
        assert str(heap_map_representation['stats']['min_address']) in str_window
        # Correctly shows the ticks
        for tick in map(str, range(0, 110, 17)):
            assert tick in str_window
        assert "1/{}".format(len(memory_profile['snapshots'])) in str_window


def test_heap_and_heat_logic(mock_curses_window, monkeypatch, memory_profiles):
    """Test heap map and heat map together with their logics

    Expecting no error, printed information and everything correct
    """
    monkeypatch.setattr(curses, 'napms', donothing)
    monkeypatch.setattr(curses, 'curs_set', donothing)
    monkeypatch.setattr(curses, 'color_pair', returnnothing)

    for memory_profile in memory_profiles:
        heap_map_repr = convert.to_heap_map_format(deepcopy(memory_profile))
        heat_map_repr = convert.to_heat_map_format(memory_profile)
        colour_mode = heap_colours.HeapMapColors.NO_COLORS
        heap_map.heap_map_logic(mock_curses_window, heap_map_repr, heat_map_repr, colour_mode)
