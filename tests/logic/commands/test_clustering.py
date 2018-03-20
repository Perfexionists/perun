import os
from click.testing import CliRunner

import perun.cli as cli
import perun.postprocess.clusterizer.run as clusterizer

__author__ = 'Tomas Fiedor'


def test_from_cli(pcs_full):
    """Tests running the clusterization from CLI"""
    object_dir = pcs_full.get_job_directory()
    object_no = len(os.listdir(object_dir))
    runner = CliRunner()
    result = runner.invoke(cli.postprocessby, ["0@i", "clusterizer"])
    assert result.exit_code == 0

    # Test that something was created
    object_no_after = len(os.listdir(object_dir))
    assert object_no_after == object_no + 1


def test_sort_order(full_profiles):
    """Test sort order method"""
    for _, full_profile in full_profiles:
        clusterizer.postprocess(full_profile, 'sort_order')


def test_sliding_window(pcs_full):
    """Tests sliding window method"""
    runner = CliRunner()
    result = runner.invoke(cli.postprocessby, ["0@i", "clusterizer", "-s", "sliding_window"])
    assert result.exit_code == 0
