import curses
import os
import bokeh.plotting as plotting

from click.testing import CliRunner
import pytest

import perun.core.profile.converters as converters
import perun.core.profile.factory as profiles
import perun.view.cli as cli
import perun.view.flow.ncurses_factory as curses_graphs
import perun.view.flow.bokeh_factory as bokeh_graphs

__author__ = 'Tomas Fiedor'


def donothing(*_):
    """Helper function for monkeypatching stuff to do nothing"""
    pass


def returnnothing(*_):
    """Helper function for monkeypatching stuff to do nothing"""
    return ''


def test_flow_cli(pcs_full, valid_profile_pool):
    """Test runing and creating bokeh flow from the cli

    Expecting no errors and created flow file
    """
    runner = CliRunner()
    for valid_profile in valid_profile_pool:
        loaded_profile = profiles.load_profile_from_file(valid_profile, is_raw_profile=True)
        if loaded_profile['header']['type'] != 'memory':
            continue

        # Classical run --- will accumulate the values
        assert 'flow.html' not in os.listdir(os.getcwd())
        result = runner.invoke(cli.show, [valid_profile, 'flow', '--of=amount', '--by=uid',
                                          '--stacked', '--filename=flow.html'])

        assert result.exit_code == 0
        assert 'flow.html' in os.listdir(os.getcwd())

        # Run without accumulation
        result = runner.invoke(cli.show, [valid_profile, 'flow', '--of=amount', '--by=uid',
                                          '--stacked', '--no-accumulate', '--filename=flow2.html',
                                          '--graph-title=Test'])
        assert result.exit_code == 0
        assert 'flow2.html' in os.listdir(os.getcwd())


def test_flow_cli_errors(pcs_full, valid_profile_pool):
    """Test running and creating bokeh flow from the cli with error simulations

    Expecting errors, but nothing destructive
    """
    runner = CliRunner()
    for valid_profile in valid_profile_pool:
        loaded_profile = profiles.load_profile_from_file(valid_profile, is_raw_profile=True)
        if loaded_profile['header']['type'] != 'memory':
            continue

        result = runner.invoke(cli.show, [valid_profile, 'flow', '--of=undefined', '--by=uid',
                                          '--stacked', '--filename=flow.html'])
        assert result.exit_code == 2
        assert "invalid choice" in result.output
        assert "choose from" in result.output


@pytest.mark.usefixtures('cleandir')
def test_bokeh_flow(memory_profiles):
    """Test creating bokeh flow graph

    Expecting no errors
    """
    for memory_profile in memory_profiles:
        bargraph = bokeh_graphs.create_from_params(memory_profile, 'sum', 'amount', 'snapshots',
                                                   'uid', True, True, 'snapshot', 'amount [B]', '?')
        plotting.output_file('flow.html')
        plotting.save(bargraph, 'flow.html')
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
    monkeypatch.setattr(curses, 'napms', donothing)

    for memory_profile in memory_profiles:
        heap_map = converters.create_heap_map(memory_profile)
        vis_obj = curses_graphs.FlowGraphVisualization(mock_curses_window, heap_map)
        vis_obj.print_intro()
        vis_obj.print_resize_req()
        vis_obj.print_global_view()
        str_window = str(mock_curses_window)
        assert 'MEMORY' in str_window
        y, x = mock_curses_window.getmaxyx()
        assert ('|' + ' '*x + '|') not in str_window


@pytest.mark.usefixtures('cleandir')
def test_curses_logic(monkeypatch, mock_curses_window, memory_profiles):
    """Test logic of the flow visualization

    Expecting no errors, eventually the visualization should end.
    """
    monkeypatch.setattr(curses, 'curs_set', donothing)
    monkeypatch.setattr(curses, 'color_pair', returnnothing)
    monkeypatch.setattr(curses, 'start_color', donothing)
    monkeypatch.setattr(curses, 'use_default_colors', donothing)
    monkeypatch.setattr(curses, 'napms', donothing)

    # Rewrite the sequence of the mock window
    mock_curses_window.character_stream = iter([
        ord('i'), ord('i'), curses.KEY_RIGHT, ord('q'), ord('q')
    ])

    for memory_profile in memory_profiles:
        heap_map = converters.create_heap_map(memory_profile)
        curses_graphs.flow_graph_logic(mock_curses_window, heap_map)
