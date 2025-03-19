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
    result = runner.invoke(cli.showdiff, [baseline_profilename, target_profilename, "short"])
    assert result.exit_code == 0
    assert "Top-9 Record" in result.output
    assert "Top-10 Record" not in result.output

    result = runner.invoke(
        cli.showdiff,
        [
            baseline_profilename,
            target_profilename,
            "short",
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
    baseline_profilename = test_utils.load_profilename(
        "diff_profiles", "kperf-baseline-stats-metadata.perf"
    )
    target_profilename = test_utils.load_profilename(
        "diff_profiles", "kperf-target-stats-metadata.perf"
    )

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


def test_diff_datatables(pcs_with_root):
    """Test creating flame graph out of the memory profile

    Expecting no errors, and created flame.svg graph
    """
    runner = CliRunner()
    baseline_profilename = test_utils.load_profilename(
        "diff_profiles", "kperf-baseline-stats-metadata.perf"
    )
    target_profilename = test_utils.load_profilename(
        "diff_profiles", "kperf-target-stats-metadata.perf"
    )

    # Next try to create it using the click
    result = runner.invoke(
        cli.showdiff, [baseline_profilename, target_profilename, "datatables", "-o", "diff.html"]
    )
    assert result.exit_code == 0

    assert "diff.html" in os.listdir(os.getcwd())

    baseline_profilename = test_utils.load_profilename("diff_profiles", "ktrace-baseline.perf")
    target_profilename = test_utils.load_profilename("diff_profiles", "ktrace-target.perf")

    # Next try to create it using the click
    result = runner.invoke(
        cli.showdiff,
        [baseline_profilename, target_profilename, "datatables", "-o", "diff-ktrace.html"],
    )
    assert result.exit_code == 0

    assert "diff-ktrace.html" in os.listdir(os.getcwd())


def test_diff_sankey(pcs_with_root):
    """Test creating sankey diff graph out of the two profile"""
    runner = CliRunner()
    baseline_profilename = test_utils.load_profilename(
        "diff_profiles", "kperf-baseline-stats-metadata.perf"
    )
    target_profilename = test_utils.load_profilename(
        "diff_profiles", "kperf-target-stats-metadata.perf"
    )

    # Next try to create it using the click
    result = runner.invoke(
        cli.showdiff,
        [
            baseline_profilename,
            target_profilename,
            "sankey",
            "-f",
            "10",
            "-m",
            "-c" "amount",
            "-o",
            "diff.html",
        ],
    )
    assert result.exit_code == 0

    assert "diff.html" in os.listdir(os.getcwd())

    baseline_profilename = test_utils.load_profilename("diff_profiles", "ktrace-baseline.perf")
    target_profilename = test_utils.load_profilename("diff_profiles", "ktrace-target.perf")
    result = runner.invoke(
        cli.showdiff,
        [
            baseline_profilename,
            target_profilename,
            "sankey",
            "-m",
            "-c" "Total Exclusive T [ms]",
            "-o",
            "diff-ktrace.html",
        ],
    )

    assert result.exit_code == 0
    assert "diff-ktrace.html" in os.listdir(os.getcwd())


def test_diff_incremental_sankey_kperf(pcs_with_root):
    """Test creating sankey diff graph out of the two profile"""
    runner = CliRunner()
    baseline_profilename = test_utils.load_profilename(
        "diff_profiles", "kperf-baseline-stats-metadata.perf"
    )
    target_profilename = test_utils.load_profilename(
        "diff_profiles", "kperf-target-stats-metadata.perf"
    )

    # Next try to create it using the click
    result = runner.invoke(
        cli.showdiff,
        [
            "--display-style",
            "diff",
            baseline_profilename,
            target_profilename,
            "report",
            "-o",
            "diff.html",
            "--minimize",
        ],
    )
    assert result.exit_code == 0
    assert "diff.html" in os.listdir(os.getcwd())


def test_diff_report_invalid_forward_param(pcs_with_root):
    runner = CliRunner()
    baseline_profilename = test_utils.load_profilename(
        "diff_profiles", "kperf-baseline-stats-metadata.perf"
    )
    target_profilename = test_utils.load_profilename(
        "diff_profiles", "kperf-target-stats-metadata.perf"
    )

    result = runner.invoke(
        cli.showdiff,
        [
            baseline_profilename,
            target_profilename,
            "report",
            "-o",
            "diff_warn",
            "--flamegraph-width",
            1000,
            "--flamegraph-height",
            15,
            "--flamegraph-minwidth",
            0.1,
            "--flamegraph-fontsize",
            14,
            "--flamegraph-bgcolors",
            "invalid_color",
        ],
    )
    assert result.exit_code == 0
    assert 'Unrecognized bgcolor option "invalid_color"' in result.output
    assert "diff_warn.html" in os.listdir(os.getcwd())


def test_diff_incremental_sankey_ktrace(pcs_with_root):
    """Test creating sankey diff graph out of the two profile"""
    runner = CliRunner()
    baseline_profilename = test_utils.load_profilename("diff_profiles", "ktrace-baseline.perf")
    target_profilename = test_utils.load_profilename("diff_profiles", "ktrace-target.perf")
    result = runner.invoke(
        cli.showdiff,
        [
            baseline_profilename,
            target_profilename,
            "report",
            "-o",
            "diff-ktrace.html",
        ],
    )

    assert result.exit_code == 0
    assert "diff-ktrace.html" in os.listdir(os.getcwd())
