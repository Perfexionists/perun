"""Simple postprocessor implementing the filter of values."""

from perun.utils.helpers import PostprocessStatus


__author__ = 'Tomas Fiedor'


def postprocess(**kwargs):
    """Postprocessing phase of the filter"""
    print("Filtering the values of the profile")
    return PostprocessStatus.OK, "", {}
