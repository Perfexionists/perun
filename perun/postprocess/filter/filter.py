"""Simple postprocessor implementing the filter of values."""

from perun.utils.helpers import PostprocessStatus


__author__ = 'Tomas Fiedor'


def postprocess(profile, **kwargs):
    """Postprocessing phase of the filter

    Arguments:
        profile(dict): dictionary with json profile
    """
    return PostprocessStatus.OK, "", {}
