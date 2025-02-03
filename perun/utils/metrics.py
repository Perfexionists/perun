"""Gathers various user defined metrics and stores them in the specified temporary file under
the specified ID.
"""

from __future__ import annotations

# Standard Imports
from typing import Any, Optional
import atexit
import time

# Third-Party Imports

# Perun Imports
from perun.logic import temp
from perun.utils import log


class MetricsManager:
    """The metrics structure that keeps the records and all related properties.

    :ivar enabled: specifies if metrics are to be collected or not
    :ivar metrics_id: the name under which the metrics are stored
    :ivar metrics_filename: the name of the temp file that stores the metrics
    :ivar timers: keeps track of running timers
    :ivar records: stores the metrics
    """

    __slots__ = ["enabled", "id_base", "metrics_id", "metrics_filename", "timers", "records"]

    def __init__(self) -> None:
        """Initializes the manager. Unless configure is called, the metrics are not recorded."""
        self.enabled: bool = False
        self.id_base: str = ""
        self.metrics_id: str = ""
        self.metrics_filename: Optional[str] = None
        self.timers: dict[str, float] = {}
        self.records: dict[str, dict[str, Any]] = {}

    def configure(self, metrics_filename: str, metrics_id: str) -> None:
        """Sets the required properties for collecting metrics.

        :param metrics_filename: the name of the temp file that stores the metrics
        :param metrics_id: the name under which the metrics are stored
        """
        self.enabled = True
        self.id_base = metrics_id
        self.metrics_id = metrics_id
        self.metrics_filename = temp.temp_path(metrics_filename)
        self.records = {metrics_id: {"id": metrics_id}}

    def switch_id(self, new_id: str) -> None:
        """Assigns new active ID.

        :param new_id: the name under which the metrics are stored
        """
        self.timers = {}
        self.id_base = new_id
        self.metrics_id = new_id
        self.records[new_id] = {"id": new_id}

    def add_sub_id(self, sub_id: str) -> None:
        """Creates a new ID in the metrics file in format <base_id>.<sub_id>

        :param sub_id: a suffix to the current base ID.
        """
        new_id = f"{self.id_base}.{sub_id}"
        self.records[new_id] = self.records.pop(self.id_base, {})
        self.records[new_id]["id"] = new_id
        self.metrics_id = new_id


Metrics = MetricsManager()


def is_enabled() -> bool:
    """Checks if metrics collection is enabled.

    :return: True if metrics are being collected, False otherwise
    """
    return Metrics.enabled


def start_timer(name: str) -> None:
    """Starts a new timer.

    :param name: the name of the timer (and also the metric)
    """
    if Metrics.enabled:
        Metrics.timers[name] = time.time()


def end_timer(name: str) -> None:
    """Stops the specified running timer and stores the resulting time into metrics

    :param name: the name of the timer
    """
    if Metrics.enabled:
        if name in Metrics.timers:
            Metrics.records[Metrics.metrics_id][name] = time.time() - Metrics.timers[name]
            del Metrics.timers[name]


# TODO: change to getitem / setitem?
def add_metric(name: str, value: Any) -> None:
    """Add new metric and its value.

    :param name: name of the metric
    :param value: the value of the metric
    """
    if Metrics.enabled:
        Metrics.records[Metrics.metrics_id][name] = value


def read_metric(name: str, default: Optional[Any] = None) -> Optional[Any]:
    """Read the current value of a metric specified by its ID

    :param name: the ID of the metric to fetch
    :param default: the default value in case no metric is recorded under the given ID
    :return: the metric value or default
    """
    if Metrics.enabled:
        return Metrics.records[Metrics.metrics_id].get(name, default)
    return None


def save() -> None:
    """Save the stored metrics into the metrics file."""
    if Metrics.enabled:
        if Metrics.metrics_filename is not None:
            stored_metrics: dict[str, dict[str, Any]] = {}
            # Update the metrics file
            if temp.exists_temp_file(Metrics.metrics_filename):
                stored_metrics = temp.read_temp(Metrics.metrics_filename)
            stored_metrics.update(Metrics.records)
            temp.store_temp(Metrics.metrics_filename, stored_metrics, json_format=True)
        else:
            log.error("cannot save metrics: `metrics_filename` was not specified")


def save_separate(temp_name: str, data: Any) -> None:
    temp.store_temp(temp_name, data, json_format=True)


# make sure that the metrics are saved in the end
atexit.register(save)
