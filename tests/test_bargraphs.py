"""Basic testing for generation of bars"""
# Standard Imports
import os

# Third-Party Imports
from click.testing import CliRunner
import bokeh.plotting as bk_plot
import holoviews as hv
import pytest

# Perun Imports
from perun import cli
from perun.testing import asserts
from perun.utils.common import view_kit
import perun.testing.utils as test_utils
import perun.view.bars.factory as bars_factory


@pytest.mark.usefixtures("cleandir")
def test_bokeh_bars(memory_profiles):
    """Test creating bokeh bars

    Expecting no error.
    """
    for memory_profile in memory_profiles:
        bargraph = bars_factory.create_from_params(
            memory_profile,
            "sum",
            "amount",
            "snapshots",
            "uid",
            "stacked",
            "snapshot",
            "amount [B]",
            "test",
        )
        view_kit.save_view_graph(bargraph, "bars.html", False)
        assert "bars.html" in os.listdir(os.getcwd())


def test_bars_cli(pcs_with_root, valid_profile_pool, monkeypatch):
    """Test running and creating bokeh bar from the cli

    Expecting no errors and created bars.html file
    """
    # We monkeypatch outputting and omit generation of html files
    monkeypatch.setattr(bk_plot, "output_file", lambda x: x)
    monkeypatch.setattr(bk_plot, "show", lambda x: x)
    monkeypatch.setattr(hv, "render", lambda x: x)

    runner = CliRunner()
    valid_profile = test_utils.load_profilename("to_add_profiles", "new-prof-2-memory-basic.perf")

    # Test correct stacked
    result = runner.invoke(
        cli.show,
        [
            valid_profile,
            "bars",
            "--of=amount",
            "--stacked",
            "--by=uid",
            "--filename=bars.html",
        ],
    )
    asserts.predicate_from_cli(result, result.exit_code == 0)
    assert "bars.html" in os.listdir(os.getcwd())

    # Test correct grouped
    result = runner.invoke(
        cli.show,
        [
            valid_profile,
            "bars",
            "--of=amount",
            "--grouped",
            "--by=uid",
            "--filename=bars.html",
            "--view-in-browser",
        ],
    )
    asserts.predicate_from_cli(result, result.exit_code == 0)


def test_bars_cli_errors(pcs_with_root, valid_profile_pool, monkeypatch):
    """Test running and creating bokeh bars from the cli with error simulations

    Expecting errors, but nothing destructive
    """
    # We monkeypatch outputting and omit generation of html files
    monkeypatch.setattr(bk_plot, "output_file", lambda x: x)
    monkeypatch.setattr(bk_plot, "show", lambda x: x)
    monkeypatch.setattr(hv, "render", lambda x: x)

    runner = CliRunner()
    valid_profile = test_utils.load_profilename("to_add_profiles", "new-prof-2-memory-basic.perf")

    # Try some bogus of parameter
    result = runner.invoke(
        cli.show, [valid_profile, "bars", "--of=undefined", "--by=uid", "--stacked"]
    )
    asserts.invalid_cli_choice(result, "undefined", "bars.html")

    # Try some bogus function
    result = runner.invoke(
        cli.show, [valid_profile, "bars", "f", "--of=subtype", "--by=uid", "--stacked"]
    )
    asserts.invalid_cli_choice(result, "f", "bars.html")

    # Try some bogus per key
    result = runner.invoke(
        cli.show,
        [valid_profile, "bars", "--of=subtype", "--by=uid", "--stacked", "--per=dolan"],
    )
    asserts.invalid_cli_choice(result, "dolan", "bars.html")

    # Try some bogus by key
    result = runner.invoke(
        cli.show,
        [valid_profile, "bars", "--of=subtype", "--by=everything", "--stacked"],
    )
    asserts.invalid_cli_choice(result, "everything", "bars.html")

    # Try some of key, that is not summable
    result = runner.invoke(
        cli.show, [valid_profile, "bars", "--of=subtype", "--by=uid", "--stacked"]
    )
    asserts.invalid_param_choice(result, "subtype", "bars.html")

    # Try some of key, that is not summable, but is countable
    for valid_func in ("count", "nunique"):
        result = runner.invoke(
            cli.show,
            [
                valid_profile,
                "bars",
                valid_func,
                "--of=subtype",
                "--by=uid",
                "--per=snapshots",
                "--view-in-browser",
            ],
        )
        asserts.predicate_from_cli(result, result.exit_code == 0)
