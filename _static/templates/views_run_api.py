"""..."""

import click

from perun.utils.common.common_kit import pass_profile


@click.command()
@pass_profile
def scatter(profile, **kwargs):
    """..."""
    pass
