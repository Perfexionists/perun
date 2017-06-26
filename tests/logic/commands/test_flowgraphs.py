
import curses
import os
import pytest

from copy import deepcopy

import perun.view.flowgraph.run as flowgraphs
import perun.view.flowgraph.ncurses_flow_graph as curses_graphs
import perun.utils.profile_converters as converters

__author__ = 'Tomas Fiedor'


def donothing(*_):
    """Helper function for monkeypatching stuff to do nothing"""
    pass


def returnnothing(*_):
    """Helper function for monkeypatching stuff to do nothing"""
    return ''


@pytest.mark.usefixtures('cleandir')
def test_bokeh_flow(memory_profiles):
    """Test creating bokeh flow graph

    Expecting no errors
    """
    for memory_profile in memory_profiles:
        flowgraphs._call_flow(deepcopy(memory_profile), "flow.html", 1200, False)
        assert 'flow.html' in os.listdir(os.getcwd())


@pytest.mark.usefixtures('cleandir')
def test_curses_flow(monkeypatch, mock_curses_window, memory_profiles):
    """Test creating showing curses graph

    Expecting no errors
    """
    monkeypatch.setattr(curses, 'curs_set', donothing)
    monkeypatch.setattr(curses, 'color_pair', returnnothing)
    monkeypatch.setattr(curses, 'start_color', donothing)
    monkeypatch.setattr(curses, 'use_default_colors', donothing)

    for memory_profile in memory_profiles:
        heap_map = converters.create_heap_map(memory_profile)
        vis_obj = curses_graphs.FlowGraphVisualization(mock_curses_window, heap_map)
        vis_obj.print_global_view()
        str_window = str(mock_curses_window)
        print(str_window)
        assert 'MEMORY' in str_window
        y, x = mock_curses_window.getmaxyx()
        assert ('|' + ' '*x + '|') not in str_window
