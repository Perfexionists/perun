import click

import perun.logic.runner as runner


def before(**kwargs):
    """(optional)"""
    return STATUS, STATUS_MSG, dict(kwargs)


def postprocess(profile, **configuration):
    """..."""
    return STATUS, STATUS_MSG, dict(kwargs)


def after(**kwargs):
    """(optional)"""
    return STATUS, STATUS_MSG, dict(kwargs)


@click.command()
@pass_profile
def regression_analysis(profile, **kwargs):
    """..."""
    runner.run_postprocessor_on_profile(profile, "mypostprocessor", kwargs)
