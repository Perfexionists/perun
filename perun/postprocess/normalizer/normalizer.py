"""Normalizer is a simple postprocessor that normalizes the values."""

from perun.utils.helpers import PostprocessStatus

__author__ = 'Tomas Fiedor'


def before(**kwargs):
    """Phase for initialization of normalizer before postprocessing"""
    print("Before running the normalizer postprocessor with ".format(kwargs))
    return PostprocessStatus.OK, ""


def postprocess(**kwargs):
    """
    Arguments:
        kwargs(dict): keyword arguments
    """
    print("Postprocessing the profile with {}".format(kwargs))
    return PostprocessStatus.OK, ""


def after(**kwargs):
    """Phase after the postprocessing"""
    print("After postprocessing with normalizer")
    return PostprocessStatus.OK, ""
