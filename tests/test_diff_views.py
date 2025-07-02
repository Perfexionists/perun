"""Basic testing for the diff views"""

from __future__ import annotations

# Standard Imports
from pathlib import Path

# Third-Party Imports
from click.testing import CliRunner

# Perun Imports
from perun.cli_groups.showdiff_cli import showdiff_group as showdiff
from perun.testing import utils as test_utils


def test_diff_tables(pcs_with_root):
    """Test the creation of CLI diff tables out of perf profiles.

    Expecting no errors.
    """
    runner = CliRunner()
    baseline_profilename = test_utils.load_profilename("diff_profiles", "kperf-baseline.perf")
    target_profilename = test_utils.load_profilename("diff_profiles", "kperf-target.perf")

    # Next try to create it using the click
    result = runner.invoke(showdiff, [baseline_profilename, target_profilename, "short"])
    assert result.exit_code == 0
    assert "Top-9 Record" in result.output
    assert "Top-10 Record" not in result.output

    result = runner.invoke(
        showdiff,
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


def test_diff_flamegraphs_basic(pcs_with_root):
    """Test the creation of basic flame graph and icicle graph out of kperf profiles.

    Expecting no errors, and a successful generation of flame graph and icicle graph.
    """
    runner = CliRunner()
    baseline_profilename = test_utils.load_profilename(
        "diff_profiles", "kperf-baseline-stats-metadata.perf"
    )
    target_profilename = test_utils.load_profilename(
        "diff_profiles", "kperf-target-stats-metadata.perf"
    )

    # Create a basic flame graph with no customization
    result = runner.invoke(showdiff, [baseline_profilename, target_profilename, "flamegraph"])
    assert result.exit_code == 0
    assert len(list(Path.cwd().glob("flamegraph-diff-of-kperf*.html"))) == 1

    # Generate icicle graphs with no squashing of [unknown] frames
    result = runner.invoke(
        showdiff,
        [
            baseline_profilename,
            target_profilename,
            "flamegraph",
            "-o",
            "icicle_graph.html",
            "--flamegraph-inverted",
            "--no-squash-unknown",
        ],
    )
    assert result.exit_code == 0
    assert Path.cwd() / "icicle_graph.html" in Path.cwd().iterdir()


def test_diff_flamegraphs_custom(pcs_with_root):
    """Test the creation of configured flame graph out of kperf profiles.

    Expecting no errors, and a successfully generated custom flame graph.
    """
    runner = CliRunner()
    baseline_profilename = test_utils.load_profilename(
        "diff_profiles", "kperf-baseline-stats-metadata.perf"
    )
    target_profilename = test_utils.load_profilename(
        "diff_profiles", "kperf-target-stats-metadata.perf"
    )

    # Manually configure the generated flame graph
    result = runner.invoke(
        showdiff,
        [
            baseline_profilename,
            target_profilename,
            "flamegraph",
            "-o",
            "flamegraph_custom",
            "--minimize",
            "--flamegraph-width",
            1000,
            "--flamegraph-height",
            15,
            "--flamegraph-minwidth",
            0.05,
            "--flamegraph-fonttype",
            "Arial",
            "--flamegraph-fontsize",
            14,
            "--flamegraph-bgcolors",
            "mem",
            "--flamegraph-colors",
            "chain",
        ],
    )
    assert result.exit_code == 0
    assert Path.cwd() / "flamegraph_custom.html" in Path.cwd().iterdir()


def test_diff_flamegraph_invalid_param(pcs_with_root):
    """Test the creation of flame graph with invalid parameter value out of kperf profiles.

    Expecting a warning message and a generated flame graph.
    """
    runner = CliRunner()
    baseline_profilename = test_utils.load_profilename(
        "diff_profiles", "kperf-baseline-stats-metadata.perf"
    )
    target_profilename = test_utils.load_profilename(
        "diff_profiles", "kperf-target-stats-metadata.perf"
    )

    # Supply an 'invalid_color' as a parameter.
    result = runner.invoke(
        showdiff,
        [
            baseline_profilename,
            target_profilename,
            "flamegraph",
            # Test that the name is extended with the .html suffix
            "-o",
            "flamegraph_warn",
            "--flamegraph-bgcolors",
            "invalid_color",
        ],
    )
    assert result.exit_code == 0
    assert 'Unrecognized bgcolor option "invalid_color"' in result.output
    assert Path.cwd() / "flamegraph_warn.html" in Path.cwd().iterdir()


def test_diff_report(pcs_with_root):
    """Test the creation of a comprehensive diff report out of kperf profiles.

    Expecting no errors, and a successfully generated diff report.
    """
    runner = CliRunner()
    baseline_profilename = test_utils.load_profilename(
        "diff_profiles", "kperf-baseline-stats-metadata.perf"
    )
    target_profilename = test_utils.load_profilename(
        "diff_profiles", "kperf-target-stats-metadata.perf"
    )

    # Generate a diff report with some basic configuration
    result = runner.invoke(
        showdiff,
        [
            "--display-style",
            "diff",
            baseline_profilename,
            target_profilename,
            "report",
            "-o",
            "diff_report.html",
            "--filter-by-relative",
            0.05,
            "--top-n",
            5,
            "--minimize",
        ],
    )
    assert result.exit_code == 0
    assert Path.cwd() / "diff_report.html" in Path.cwd().iterdir()
