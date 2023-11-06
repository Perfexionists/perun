import click

import perun.logic.runner as runner


def before(**kwargs):
    """(optional)"""
    return STATUS, STATUS_MSG, dict(kwargs)


def collect(**kwargs):
    """..."""
    return STATUS, STATUS_MSG, dict(kwargs)


def after(**kwargs):
    """(optional)"""
    return STATUS, STATUS_MSG, dict(kwargs)


@click.command()
@click.pass_context
def mycollector(ctx, **kwargs):
    """..."""
    runner.run_collector_from_cli_context(ctx, "mycollector", kwargs)
