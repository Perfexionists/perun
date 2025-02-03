"""Basic tests for scatter plot visualization"""

from __future__ import annotations

# Standard Imports
import os

# Third-Party Imports
from click.testing import CliRunner

# Perun Imports
from perun import cli
import perun.view.scatter.factory as scatter
import perun.testing.utils as test_utils

from perun.testing import asserts


def test_scatter_plot_regression_models(postprocess_profiles_regression_analysis):
    """Test the scatter plot on complexity profiles with regression models.

    Expecting no errors or exceptions.
    """
    # Filter the postprocess profiles with regression models
    tested_profiles = list(postprocess_profiles_regression_analysis)
    assert len(tested_profiles) == 5

    for profile in tested_profiles:
        # Create graphs from one profile
        graphs = scatter.create_from_params(
            profile[1],
            "amount",
            "structure-unit-size",
            "structure-unit-size",
            "amount [us]",
            "Plot of 'amount' per 'structure-unit-size'",
        )
        results = list(graphs)

        # Check if scatter plot generated expected amount of graphs for each profile
        if (
            "full_computation.perf" in profile[0]
            or "initial_guess_computation.perf" in profile[0]
            or "iterative_computation.perf" in profile[0]
        ):
            assert len(results) == 2
        elif "bisection_computation.perf" in profile[0]:
            assert len(results) == 4
        elif "interval_computation.perf" in profile[0]:
            assert len(results) == 6


def test_scatter_plot_non_param_methods(postprocess_profiles_advanced):
    """Test the scatter plot on complexity profiles with regressogram.

    Expecting no errors or exceptions.
    """
    # Filter the postprocess profiles with regressogram
    tested_profiles = list(postprocess_profiles_advanced)
    assert len(tested_profiles) == 3

    for profile in tested_profiles:
        # Create graphs from one profile
        graphs = scatter.create_from_params(
            profile[1],
            "amount",
            "structure-unit-size",
            "structure-unit-size",
            "amount [us]",
            'Plot of "amount" per "structure-unit-size"',
        )
        results = list(graphs)

        # Check if scatter plot generated expected amount of graphs for each profile
        if (
            "exp_datapoints_rg_ma_kr.perf" in profile[0]
            or "pow_datapoints_rg_ma_kr.perf" in profile[0]
        ):
            assert len(results) == 3
        elif "lin_datapoints_rg_ma_kr.perf" in profile[0]:
            assert len(results) == 2


def test_scatter_plot_no_models():
    """Test the scatter plot on complexity profiles without models.

    Expecting no errors or exceptions.
    """
    # Filter the full profiles, only the complexity one is needed
    complexity_prof = test_utils.load_profile(
        "full_profiles", "prof-2-complexity-2017-03-20-21-40-42.perf"
    )

    # Create graphs from one profile without models
    graphs = scatter.create_from_params(
        complexity_prof,
        "amount",
        "structure-unit-size",
        "structure-unit-size",
        "amount [us]",
        "Plot of 'amount' per 'structure-unit-size'",
    )
    # Graphs for two functions should be generated
    assert len(list(graphs)) == 2


def test_scatter_plot_cli(pcs_with_root):
    """Test creating bokeh scatter plot from the cli

    Expecting no errors and created scatter_plot_result0.html, scatter_plot_result1.html files
    """
    # Filter the postprocess profiles, test only on the full computation
    profile = test_utils.load_profilename("postprocess_profiles", "full_computation.perf")

    # Run the cli on the given profile
    runner = CliRunner()
    result = runner.invoke(
        cli.show,
        [
            profile,
            "scatter",
            "--of=amount",
            "--per=structure-unit-size",
            "--filename=scatter",
            "-xl=structure-unit-size",
            "-yl=amount [us]",
        ],
    )

    asserts.predicate_from_cli(result, result.exit_code == 0)
    assert "scatter_SLList_insert(SLList_,_int).html" in os.listdir(os.getcwd())
    assert "scatter_SLListcls__Insert(int).html" in os.listdir(os.getcwd())


def test_scatter_plot_cli_errors(pcs_with_root):
    """Test creating bokeh scatter plot from the cli with invalid inputs

    Expecting to fail all commands and not create any graph files.
    """
    # Filter the postprocess profiles, test only on the full computation
    profile = test_utils.load_profilename("postprocess_profiles", "full_computation.perf")

    runner = CliRunner()
    # Try invalid view argument
    result = runner.invoke(
        cli.show, [profile, "scatterr", "--of=amount", "--per=structure-unit-size"]
    )
    asserts.predicate_from_cli(result, result.exit_code == 2)
    asserts.predicate_from_cli(result, "No such command" in result.output)
    asserts.predicate_from_cli(result, "scatterr" in result.output)

    # Try invalid --of value
    result = runner.invoke(cli.show, [profile, "scatter", "--of=amou", "--per=structure-unit-size"])
    asserts.invalid_cli_choice(result, "amou")

    # Try invalid --per value
    result = runner.invoke(cli.show, [profile, "scatter", "--of=amount", "--per=struct"])
    asserts.invalid_cli_choice(result, "struct")
