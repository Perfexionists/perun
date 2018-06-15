"""Simple postprocessor implementing the filter of values."""

import click

import perun.logic.runner as runner
from perun.utils.helpers import PostprocessStatus, pass_profile


__author__ = 'Tomas Fiedor'


def postprocess(**_):
    """Postprocessing phase of the filter

    :param dict profile: dictionary with json profile
    """
    return PostprocessStatus.OK, "", {}


@click.command()
@pass_profile
def filter(profile):
    """Filtering of the resources according ot the given query"""
    runner.run_postprocessor_on_profile(profile, 'filter', {})
