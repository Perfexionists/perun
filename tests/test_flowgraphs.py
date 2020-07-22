import os

import bokeh.plotting as plotting
import pytest
from click.testing import CliRunner

import perun.cli as cli
import perun.logic.store as store
import perun.view.flow.factory as bokeh_graphs

import tests.testing.asserts as asserts

__author__ = 'Tomas Fiedor'


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

        asserts.predicate_from_cli(result, result.exit_code == 0)
        assert 'flow.html' in os.listdir(os.getcwd())

        # Run without accumulation
        result = runner.invoke(cli.show, [valid_profile, 'flow', '--of=amount', '--by=uid',
                                          '--stacked', '--no-accumulate', '--filename=flow2.html',
                                          '--graph-title=Test'])
        asserts.predicate_from_cli(result, result.exit_code == 0)
        assert 'flow2.html' in os.listdir(os.getcwd())


def test_flow_cli_errors(pcs_full, valid_profile_pool):
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
        asserts.invalid_cli_choice(result, "undefined", 'flow.html')

        # Try some bogus function
        result = runner.invoke(cli.show, [valid_profile, 'flow', 'oracle', '--of=amount',
                                          '--by=uid', '--stacked'])
        asserts.invalid_cli_choice(result, 'oracle', 'flow.html')

        # Try some through key, that is not continuous
        result = runner.invoke(cli.show, [valid_profile, 'flow', '--of=amount', '--by=uid',
                                          '--through=subtype'])
        asserts.invalid_cli_choice(result, 'subtype', 'flow.html')

        # Try some of key, that is not summable
        result = runner.invoke(cli.show, [valid_profile, 'flow', '--of=subtype', '--by=uid',
                                          '--through=snapshots'])
        asserts.invalid_param_choice(result, 'subtype', 'flow.html')

        # Try some of key, that is not summable, but is countable
        for valid_func in ('count', 'nunique'):
            result = runner.invoke(cli.show, [valid_profile, 'flow', valid_func, '--of=subtype',
                                              '--by=uid', '--through=snapshots'])
            asserts.predicate_from_cli(result, result.exit_code == 0)
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
