""" Gathers various user defined metrics and stores them in the specified temporary file under
the specified ID.
"""

import time
import atexit

import perun.logic.temp as temp


class MetricsManager:
    """ The metrics structure that keeps the records and all related properties.

    :ivar bool enabled: specifies if metrics are to be collected or not
    :ivar str metrics_id: the name under which the metrics are stored
    :ivar str metrics_filename: the name of the temp file that stores the metrics
    :ivar dict timers: keeps track of running timers
    :ivar dict records: stores the metrics
    """
    def __init__(self):
        """ Initializes the manager. Unless configure is called, the metrics are not recorded.
        """
        self.enabled = False
        self.metrics_id = None
        self.metrics_filename = None
        self.timers = {}
        self.records = {}

    def configure(self, metrics_filename, metrics_id):
        """ Sets the required properties for collecting metrics.

        :param str metrics_filename: the name of the temp file that stores the metrics
        :param str metrics_id: the name under which the metrics are stored
        """
        self.enabled = True
        self.metrics_id = metrics_id
        self.metrics_filename = temp.temp_path(metrics_filename)
        self.records = {'id': metrics_id}


Metrics = MetricsManager()


def is_enabled():
    """ Checks if metrics collection is enabled.

    :return bool: True if metrics are being collected, False otherwise
    """
    return Metrics.enabled


def start_timer(name):
    """ Starts a new timer.

    :param str name: the name of the timer (and also the metric)
    """
    if Metrics.enabled:
        Metrics.timers[name] = time.time()


def end_timer(name):
    """ Stops the specified running timer and stores the resulting time into metrics

    :param str name: the name of the timer
    """
    if Metrics.enabled:
        if name in Metrics.timers:
            Metrics.records[name] = time.time() - Metrics.timers[name]
            del Metrics.timers[name]


# TODO: change to getitem / setitem?
def add_metric(name, value):
    """ Add new metric and its value.

    :param str name: name of the metric
    :param object value: the value of the metric
    """
    if Metrics.enabled:
        Metrics.records[name] = value


def read_metric(name, default=None):
    """ Read the current value of a metric specified by its ID

    :param str name: the ID of the metric to fetch
    :param object default: the default value in case no metric is recorded under the given ID
    :return object: the metric value or default
    """
    if Metrics.enabled:
        return Metrics.records.get(name, default)


def save():
    """ Save the stored metrics into the metrics file.
    """
    if Metrics.enabled:
        stored_metrics = {}
        # Update the metrics file
        if temp.exists_temp_file(Metrics.metrics_filename):
            stored_metrics = temp.read_temp(Metrics.metrics_filename)
        stored_metrics.setdefault(Metrics.metrics_id, {}).update(Metrics.records)
        temp.store_temp(Metrics.metrics_filename, stored_metrics, json_format=True)


def save_separate(temp_name, data):
    temp.store_temp(temp_name, data, json_format=True)


# make sure that the metrics are saved in the end
atexit.register(save)
