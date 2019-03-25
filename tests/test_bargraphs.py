"""Basic testing for generation of bars"""

import os

import bokeh.plotting as plotting
import pytest
from click.testing import CliRunner

import perun.cli as cli
import perun.logic.store as store
import perun.view.bars.factory as bargraphs

__author__ = 'Tomas Fiedor'


@pytest.mark.usefixtures('cleandir')
def test_bokeh_bars(memory_profiles):
    """Test creating bokeh bars

    Expecting no error.
    """
    for memory_profile in memory_profiles:
        bargraph = bargraphs.create_from_params(memory_profile, 'sum', 'amount', 'snapshots',
                                                'uid', 'stacked', 'snapshot', 'amount [B]', 'test')
        plotting.output_file('bars.html')
        plotting.save(bargraph, 'bars.html')
        assert 'bars.html' in os.listdir(os.getcwd())


def test_bars_cli(pcs_full, valid_profile_pool):
    """Test running and creating bokeh bar from the cli

    Expecting no errors and created bars.html file
    """
    runner = CliRunner()
    for valid_profile in valid_profile_pool:
        loaded_profile = store.load_profile_from_file(valid_profile, is_raw_profile=True)
        if loaded_profile['header']['type'] != 'memory':
            continue

        # Test correct stacked
        result = runner.invoke(cli.show, [valid_profile, 'bars', '--of=amount', '--stacked',
                                          '--by=uid', '--filename=bars.html'])
        assert result.exit_code == 0
        assert 'bars.html' in os.listdir(os.getcwd())

        # Test correct grouped
        result = runner.invoke(cli.show, [valid_profile, 'bars', '--of=amount', '--grouped',
                                          '--by=uid', '--filename=bars.html'])
        assert result.exit_code == 0
        assert 'bars.html' in os.listdir(os.getcwd())


def test_bars_cli_errors(helpers, pcs_full, valid_profile_pool):
    """Test running and creating bokeh bars from the cli with error simulations

    Expecting errors, but nothing destructive
    """
    runner = CliRunner()
    for valid_profile in valid_profile_pool:
        loaded_profile = store.load_profile_from_file(valid_profile, is_raw_profile=True)
        if loaded_profile['header']['type'] != 'memory':
            continue

        # Try some bogus of parameter
        result = runner.invoke(cli.show, [valid_profile, 'bars', '--of=undefined', '--by=uid',
                                          '--stacked'])
        helpers.assert_invalid_cli_choice(result, 'undefined', 'bars.html')

        # Try some bogus function
        result = runner.invoke(cli.show, [valid_profile, 'bars', 'f', '--of=subtype', '--by=uid',
                                          '--stacked'])
        helpers.assert_invalid_cli_choice(result, 'f', 'bars.html')

        # Try some bogus per key
        result = runner.invoke(cli.show, [valid_profile, 'bars', '--of=subtype', '--by=uid',
                                          '--stacked', '--per=dolan'])
        helpers.assert_invalid_cli_choice(result, 'dolan', 'bars.html')

        # Try some bogus by key
        result = runner.invoke(cli.show, [valid_profile, 'bars', '--of=subtype', '--by=everything',
                                          '--stacked'])
        helpers.assert_invalid_cli_choice(result, 'everything', 'bars.html')

        # Try some of key, that is not summable
        result = runner.invoke(cli.show, [valid_profile, 'bars', '--of=subtype', '--by=uid',
                                          '--stacked'])
        helpers.assert_invalid_param_choice(result, 'subtype', 'bars.html')

        # Try some of key, that is not summable, but is countable
        for valid_func in ('count', 'nunique'):
            result = runner.invoke(cli.show, [valid_profile, 'bars', valid_func, '--of=subtype',
                                              '--by=uid', '--per=snapshots'])
            assert result.exit_code == 0
            assert 'bars.html' in os.listdir(os.getcwd())
