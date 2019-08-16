import curses
import os

import bokeh.plotting as plotting
import pytest
from click.testing import CliRunner

import perun.cli as cli
import perun.profile.convert as convert
import perun.logic.store as store
import perun.view.flow.bokeh_factory as bokeh_graphs
import perun.view.flow.ncurses_factory as curses_graphs

__author__ = 'Tomas Fiedor'


def donothing(*_):
    """Helper function for monkeypatching stuff to do nothing"""
    pass


def test_flow_cli(pcs_full, valid_profile_pool):
    """Test runing and creating bokeh flow from the cli

    Expecting no errors and created flow file
    """
    runner = CliRunner()
    for valid_profile in valid_profile_pool:
        loaded_profile = store.load_profile_from_file(valid_profile, is_raw_profile=True)
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


def test_flow_cli_errors(helpers, pcs_full, valid_profile_pool):
    """Test running and creating bokeh flow from the cli with error simulations

    Expecting errors, but nothing destructive
    """
    runner = CliRunner()
    for valid_profile in valid_profile_pool:
        loaded_profile = store.load_profile_from_file(valid_profile, is_raw_profile=True)
        if loaded_profile['header']['type'] != 'memory':
            continue

        result = runner.invoke(cli.show, [valid_profile, 'flow', '--of=undefined', '--by=uid',
                                          '--stacked'])
        helpers.assert_invalid_cli_choice(result, "undefined", 'flow.html')

        # Try some bogus function
        result = runner.invoke(cli.show, [valid_profile, 'flow', 'oracle', '--of=amount',
                                          '--by=uid', '--stacked'])
        helpers.assert_invalid_cli_choice(result, 'oracle', 'flow.html')

        # Try some through key, that is not continuous
        result = runner.invoke(cli.show, [valid_profile, 'flow', '--of=amount', '--by=uid',
                                          '--through=subtype'])
        helpers.assert_invalid_cli_choice(result, 'subtype', 'flow.html')

        # Try some of key, that is not summable
        result = runner.invoke(cli.show, [valid_profile, 'flow', '--of=subtype', '--by=uid',
                                          '--through=snapshots'])
        helpers.assert_invalid_param_choice(result, 'subtype', 'flow.html')

        # Try some of key, that is not summable, but is countable
        for valid_func in ('count', 'nunique'):
            result = runner.invoke(cli.show, [valid_profile, 'flow', valid_func, '--of=subtype',
                                              '--by=uid', '--through=snapshots'])
            assert result.exit_code == 0
            assert 'flow.html' in os.listdir(os.getcwd())


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
    monkeypatch.setattr(curses, 'color_pair', donothing)
    monkeypatch.setattr(curses, 'start_color', donothing)
    monkeypatch.setattr(curses, 'use_default_colors', donothing)
    monkeypatch.setattr(curses, 'napms', donothing)

    for memory_profile in memory_profiles:
        heap_map = convert.to_heap_map_format(memory_profile)
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
    monkeypatch.setattr(curses, 'color_pair', donothing)
    monkeypatch.setattr(curses, 'start_color', donothing)
    monkeypatch.setattr(curses, 'use_default_colors', donothing)
    monkeypatch.setattr(curses, 'napms', donothing)

    # Rewrite the sequence of the mock window
    mock_curses_window.character_stream = iter([
        ord('i'), ord('i'), curses.KEY_RIGHT, ord('q'), ord('q')
    ])

    for memory_profile in memory_profiles:
        heap_map = convert.to_heap_map_format(memory_profile)
        curses_graphs.flow_graph_logic(mock_curses_window, heap_map)
