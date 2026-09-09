"""Basic testing for the flame graph generation"""

from __future__ import annotations

# Standard Imports
import os
import pathlib

# Third-Party Imports
from click.testing import CliRunner

# Perun Imports
from perun import cli
from perun.profiles import structs
from perun.profiles.conversions import native_folded
from perun.testing import asserts
import perun.testing.utils as test_utils
from perun.view.flamegraph import core


def test_flame_graph(pcs_with_root, valid_profile_pool):
    """Test creating flame graph out of the memory profile

    Expecting no errors, and created flame.svg graph
    """
    runner = CliRunner()
    valid_profile = test_utils.load_profilename("to_add_profiles", "new-prof-2-memory-basic.perf")
    memory_profile = test_utils.load_profile("to_add_profiles", "new-prof-2-memory-basic.perf")

    # First, try to create the graph using the module API.
    core.generate_flamegraph(
        native_folded.native_to_folded(memory_profile),
        pathlib.Path("flame2.svg"),
        "Test flame graph",
        core.FlameGraphSettings(),
        structs.PostprocessParameters(hide_generics=True, squash=True),
    )
    assert "flame2.svg" in os.listdir(os.getcwd())

    # Next, try to create it using CLI.
    result = runner.invoke(cli.show, [valid_profile, "flamegraph"])

    asserts.predicate_from_cli(result, result.exit_code == 0)
    assert "flame.svg" in os.listdir(os.getcwd())

    # Read the contents and do a partial compare (some stuff are random, so one cannot be sure)
    with open("flame.svg", "r") as f1:
        first_contents = f1.readlines()

    with open("flame2.svg", "r") as f2:
        second_contents = f2.readlines()

    assert len(first_contents) == len(second_contents)
