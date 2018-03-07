"""..."""

import click

from perun.utils.helpers import pass_profile


@click.command()
@pass_profile
def scatter(profile, **kwargs):
    """..."""
    pass
