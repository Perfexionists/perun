import os

import pytest
from click.testing import CliRunner

import perun.view.flow.factory as flow_factory
import perun.testing.utils as test_utils
from perun import cli
from perun.logic import store
from perun.utils import view_helpers
from perun.testing import asserts


def test_flow_cli(pcs_full_no_prof):
    """Test runing and creating bokeh flow from the cli

    Expecting no errors and created flow file
    """
    runner = CliRunner()
    valid_profile = test_utils.load_profilename('to_add_profiles', 'new-prof-2-memory-basic.perf')

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


def test_flow_cli_errors(pcs_full_no_prof):
    """Test running and creating bokeh flow from the cli with error simulations

    Expecting errors, but nothing destructive
    """
    runner = CliRunner()
    valid_profile = test_utils.load_profilename('to_add_profiles', 'new-prof-2-memory-basic.perf')

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
def test_holoviews_flow(memory_profiles):
    """Test creating bokeh flow graph

    Expecting no errors
    """
    for memory_profile in memory_profiles:
        bargraph = flow_factory.create_from_params(memory_profile, 'sum', 'amount', 'snapshots',
                                                   'uid', True, True, 'snapshot', 'amount [B]', '?')
        view_helpers.save_view_graph(bargraph, "flow.html", False)
        assert 'flow.html' in os.listdir(os.getcwd())
