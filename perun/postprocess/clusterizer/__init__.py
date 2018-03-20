"""Clusterization postprocessing module"""

SUPPORTED_PROFILES = ["memory", "mixed", "time"]

SUPPORTED_STRATEGIES = [
    'sort_order',
    'sliding_window'
]
DEFAULT_STRATEGY = SUPPORTED_STRATEGIES[0]

__author__ = 'Tomas Fiedor'
