"""Basic testing for the diff views"""
from __future__ import annotations

# Standard Imports
import os

# Third-Party Imports
from click.testing import CliRunner

# Perun Imports
from perun import cli
from perun.testing import utils as test_utils


def test_diff_tables(pcs_with_root):
    """Test creating flame graph out of the memory profile

    Expecting no errors, and created flame.svg graph
    """
    runner = CliRunner()
    baseline_profilename = test_utils.load_profilename("diff_profiles", "kperf-baseline.perf")
    target_profilename = test_utils.load_profilename("diff_profiles", "kperf-target.perf")

    # Next try to create it using the click
    result = runner.invoke(cli.showdiff, [baseline_profilename, target_profilename, "table"])
    assert result.exit_code == 0
    assert "Top-9 Record" in result.output
    assert "Top-10 Record" not in result.output

    result = runner.invoke(
        cli.showdiff,
        [
            baseline_profilename,
            target_profilename,
            "table",
            "-f",
            "uid",
            "__intel_pmu_enable_all.isra.0",
            "-f",
            "uid",
            "__raw_callee_save___pv_queued_spin_unlock",
        ],
    )
    assert result.exit_code == 0
    assert "Top-6 Record" in result.output
    assert "Top-7 Record" not in result.output


def test_diff_flamegraphs(pcs_with_root):
    """Test creating flame graph out of the memory profile

    Expecting no errors, and created flame.svg graph
    """
    runner = CliRunner()
    baseline_profilename = test_utils.load_profilename("diff_profiles", "kperf-baseline.perf")
    target_profilename = test_utils.load_profilename("diff_profiles", "kperf-target.perf")

    # Next try to create it using the click
    result = runner.invoke(
        cli.showdiff, [baseline_profilename, target_profilename, "flamegraph", "-o", "diff"]
    )
    assert result.exit_code == 0

    assert "diff.html" in os.listdir(os.getcwd())

    # Try no output-file specified
    prev = len([a for a in os.listdir(os.getcwd()) if a.endswith(".html")])
    result = runner.invoke(cli.showdiff, [baseline_profilename, target_profilename, "flamegraph"])
    assert len([a for a in os.listdir(os.getcwd()) if a.endswith(".html")]) == (prev + 1)
    assert result.exit_code == 0


def test_diff_reports(pcs_with_root):
    """Test creating flame graph out of the memory profile

    Expecting no errors, and created flame.svg graph
    """
    runner = CliRunner()
    baseline_profilename = test_utils.load_profilename("diff_profiles", "kperf-baseline.perf")
    target_profilename = test_utils.load_profilename("diff_profiles", "kperf-target.perf")

    # Next try to create it using the click
    result = runner.invoke(
        cli.showdiff, [baseline_profilename, target_profilename, "report", "-o", "diff.html"]
    )
    assert result.exit_code == 0

    assert "diff.html" in os.listdir(os.getcwd())
