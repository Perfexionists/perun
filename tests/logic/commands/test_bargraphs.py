"""Basic testing for generation of bars"""

import os
import pytest
import bokeh.plotting as plotting

from click.testing import CliRunner

import perun.core.logic.profile as profiles
import perun.view.bargraph.bar_graphs as bargraphs
import perun.view.cli as cli

__author__ = 'Tomas Fiedor'


@pytest.mark.usefixtures('cleandir')
def test_bokeh_bars(memory_profiles):
    """Test creating bokeh bars

    Expecting no error.
    """
    for memory_profile in memory_profiles:
        bargraph = bargraphs.create_from_params(memory_profile, 800, 'sum', 'amount', 'snapshots',
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
        loaded_profile = profiles.load_profile_from_file(valid_profile, is_raw_profile=True)
        if loaded_profile['header']['type'] != 'memory':
            continue
        result = runner.invoke(cli.show, [valid_profile, 'bargraph', '--of=amount', '--stacked',
                                          '--by=uid', '--filename=bars.html'])
        print(result.output)
        assert result.exit_code == 0
        assert 'bars.html' in os.listdir(os.getcwd())
