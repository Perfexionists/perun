"""
Testing basic functionality of metrics module
"""
from __future__ import annotations

# Standard Imports
import os

# Third-Party Imports
import pytest

# Perun Imports
from perun.utils import metrics


@pytest.mark.usefixtures("cleandir")
def test_metrics(pcs_with_root, capsys):
    prev_enabled = metrics.Metrics.enabled
    metrics.Metrics.enabled = True
    assert metrics.is_enabled()
    assert metrics.Metrics.metrics_id == ""

    # Basic configuration
    metrics.Metrics.configure("some_stats_file", "someid")
    assert metrics.Metrics.metrics_id == "someid"
    assert metrics.Metrics.records == {"someid": {"id": "someid"}}

    # Switching metrics
    metrics.Metrics.switch_id("newid")
    assert metrics.Metrics.metrics_id == "newid"
    assert metrics.Metrics.records == {
        "someid": {"id": "someid"},
        "newid": {"id": "newid"},
    }
    metrics.Metrics.add_sub_id("subid")
    assert metrics.Metrics.metrics_id == "newid.subid"
    assert metrics.Metrics.records == {
        "someid": {"id": "someid"},
        "newid.subid": {"id": "newid.subid"},
    }

    metrics.start_timer("test")
    metrics.end_timer("test")
    assert isinstance(metrics.Metrics.records["newid.subid"]["test"], float)

    metrics.add_metric("metric", 1)
    assert metrics.read_metric("metric") == 1

    metrics.save()
    stats_dir = os.path.join(".perun", "tmp")
    assert "some_stats_file" in os.listdir(stats_dir)

    metrics.Metrics.metrics_filename = None
    with pytest.raises(SystemExit):
        metrics.save()
        _, err = capsys.readouterr()
        assert "cannot save metrics: `metrics_filename` was not specified" in err

    metrics.save_separate("other_stats_file", {})
    assert "other_stats_file" in os.listdir(stats_dir)

    metrics.Metrics.enabled = False
    metrics.add_metric("metric2", 1)
    assert metrics.read_metric("metric2") is None
    metrics.Metrics.enabled = prev_enabled
