"""Basic testing for the flame graph generation"""

import os

from click.testing import CliRunner

import perun.cli as cli
import perun.logic.store as store
import perun.view.flamegraph.flamegraph as flamegraphs

import perun.testing.asserts as asserts

__author__ = 'Tomas Fiedor'


def test_flame_graph(pcs_full, valid_profile_pool):
    """Test creating flame graph out of the memory profile

    Expecting no errors, and created flame.svg graph
    """
    runner = CliRunner()

    for valid_profile in valid_profile_pool:
        memory_profile = store.load_profile_from_file(valid_profile, is_raw_profile=True)
        if memory_profile['header']['type'] != 'memory':
            continue

        # First try to create the graph using the convential matters
        flamegraphs.draw_flame_graph(memory_profile, 'flame2.svg', 20)
        assert 'flame2.svg' in os.listdir(os.getcwd())

        # Next try to create it using the click
        result = runner.invoke(cli.show, [valid_profile, 'flamegraph'])

        asserts.predicate_from_cli(result, result.exit_code == 0)
        assert 'flame.svg' in os.listdir(os.getcwd())

        # Read the contents and do a partial compare (some stuff are random, so one cannot be sure)
        with open('flame.svg', 'r') as f1:
            first_contents = f1.readlines()

        with open('flame2.svg', 'r') as f2:
            second_contents = f2.readlines()

        assert len(first_contents) == len(second_contents)
