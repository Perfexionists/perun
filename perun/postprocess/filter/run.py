"""Simple postprocessor implementing the filter of values."""

import click

import perun.logic.runner as runner
from perun.profile.factory import pass_profile
from perun.utils.structs import PostprocessStatus


__author__ = 'Tomas Fiedor'


def postprocess(**_):
    """Postprocessing phase of the filter"""
    return PostprocessStatus.OK, "", {}


@click.command()
@pass_profile
def filter(profile):
    """Filtering of the resources according ot the given query"""
    runner.run_postprocessor_on_profile(profile, 'filter', {})
