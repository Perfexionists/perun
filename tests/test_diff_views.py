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
    result = runner.invoke(showdiff, ["short", baseline_profilename, target_profilename])
    assert result.exit_code == 0
    assert "Top-9 Record" in result.output
    assert "Top-10 Record" not in result.output

    result = runner.invoke(
        showdiff,
        [
            "short",
            baseline_profilename,
            target_profilename,
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
    result = runner.invoke(showdiff, ["flamegraph", baseline_profilename, target_profilename])
    assert result.exit_code == 0
    assert len(list(Path.cwd().glob("flamegraph-diff-of-kperf*.html"))) == 1

    # Generate icicle graphs with no squashing of [unknown] frames
    result = runner.invoke(
        showdiff,
        [
            "flamegraph",
            baseline_profilename,
            target_profilename,
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
            "flamegraph",
            baseline_profilename,
            target_profilename,
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
            "flamegraph",
            baseline_profilename,
            target_profilename,
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


def test_diff_report_native(pcs_with_root):
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

    chatbot_prompt_file = Path(__file__).parent / "sources" / "showdiff" / "chatbot_ctx.prompt"

    # Generate a diff report with some basic configuration
    result = runner.invoke(
        showdiff,
        [
            "report",
            # General report options.
            "--display-style",
            "diff",
            "-o",
            "diff_report.html",
            "--filter-by-relative",
            0.05,
            "--top-n",
            5,
            "--minimize",
            "--link",
            "https://perfexionists.github.io/perun/",
            "Perun documentation",
            "--chatbot-url",
            "https://invalid-chatbot.com",
            "-p",
            "If a performance difference is smaller than 5% we consider it a statistical fluke.",
            "-p",
            chatbot_prompt_file,
            # Report-native args.
            "native",
            baseline_profilename,
            target_profilename,
        ],
    )
    assert result.exit_code == 0
    assert Path.cwd() / "diff_report.html" in Path.cwd().iterdir()


def test_diff_report_folded(pcs_with_svs):
    """Test the creation of a comprehensive diff report out of kperf profiles.

    Expecting no errors, and a successfully generated diff report.
    """
    pool_path = Path(__file__).parent / "sources" / "imports"
    baseline_profiles = "import.csv"
    target_profile = "import.stack.gz,0,12511.0948"
    chatbot_prompt_file = Path(__file__).parent / "sources" / "showdiff" / "chatbot_ctx.prompt"

    runner = CliRunner()

    # Generate a diff report with some basic configuration
    result = runner.invoke(
        showdiff,
        [
            "report",
            # General report options.
            "-o",
            "diff_report_folded",
            "--offline",
            "--squash-regex",
            "\\[unknown\\]",
            "--hide-generics",
            "--link",
            "https://perfexionists.github.io/perun/",
            "Perun documentation",
            "--chatbot-url",
            "https://invalid-chatbot.com",
            "-p",
            "If a performance difference is smaller than 5% we consider it a statistical fluke.",
            "-p",
            chatbot_prompt_file,
            # Report-folded-specific options.
            "folded",
            baseline_profiles,
            target_profile,
            "--baseline-dir",
            pool_path,
            "--target-dir",
            pool_path,
            "--profiled-resource",
            "CPU Cycles",
            "--baseline-machine-info",
            "machine_info.json",
            "--target-machine-info",
            "machine_info.json",
            "--target-stats-headers",
            "bogo-ops-per-second-real-time| higher_is_better|bogo-ops-per-second |min",
            "--baseline-metadata",
            "metadata.json",
            "--target-metadata",
            "gcc|v10.0.0|gcc version",
            "--baseline-label",
            "performance-tuned",
            "--target-label",
            "energy-tuned",
            "--baseline-collector-cmd",
            "perf",
            "--target-collector-cmd",
            "perf",
            "--baseline-cmd",
            "ls -la",
            "--target-cmd",
            "ls -la",
        ],
    )
    assert result.exit_code == 0
    assert Path.cwd() / "diff_report_folded.html" in Path.cwd().iterdir()

    result = runner.invoke(
        showdiff,
        [
            "report",
            # General report options.
            "--flamegraph-minwidth",
            "0.1%",
            "--no-squash",
            "--flamegraph-no-parallelize",
            "--flamegraph-inverted",
            "--hide-generics",
            # Report-folded-specific options.
            "folded",
            baseline_profiles,
            "import-stressng.stack",  # "import-empty.csv",
            "--baseline-dir",
            pool_path,
            "--target-dir",
            pool_path,
        ],
    )
    assert result.exit_code == 0
    assert len(list(Path.cwd().glob("report-folded_*"))) == 1

    # Test empty profile specifications, i.e., no baseline or target profile supplied at all.
    result = runner.invoke(
        showdiff,
        [
            "report",
            "folded",
            "import-empty.csv",
            target_profile,
            "--baseline-dir",
            pool_path,
            "--target-dir",
            pool_path,
        ],
    )
    assert result.exit_code == 1
    assert "No valid baseline" in result.output

    result = runner.invoke(
        showdiff,
        [
            "report",
            "folded",
            baseline_profiles,
            "import-empty.csv",
            "--baseline-dir",
            pool_path,
            "--target-dir",
            pool_path,
        ],
    )
    assert result.exit_code == 1
    assert "No valid target" in result.output

    # Test that empty profiles (no traces) are correctly detected and terminate the report.
    # Empty profiles do not generate valid flamegraph grids.
    result = runner.invoke(
        showdiff,
        [
            "report",
            "folded",
            "import-empty.stack",
            target_profile,
            "--baseline-dir",
            pool_path,
            "--target-dir",
            pool_path,
        ],
    )
    assert result.exit_code == 1
    assert "Baseline profile is empty" in result.output

    result = runner.invoke(
        showdiff,
        [
            "report",
            "folded",
            baseline_profiles,
            "import-empty.stack",
            "--baseline-dir",
            pool_path,
            "--target-dir",
            pool_path,
        ],
    )
    assert result.exit_code == 1
    assert "Target profile is empty" in result.output

    # Test that parsing a fake gzip file fails as expected.
    result = runner.invoke(
        showdiff,
        [
            "report",
            "folded",
            "not-an-actual-gzip.gz",
            target_profile,
            "--baseline-dir",
            pool_path,
            "--target-dir",
            pool_path,
        ],
    )
    assert result.exit_code == 1
    assert "Not a gzipped file" in result.output
