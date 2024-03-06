"""Table difference of the profiles"""
from __future__ import annotations

# Standard Imports
from typing import Any

# Third-Party Imports
import click

# Perun Imports


@click.command()
@click.pass_context
def table(ctx: click.Context, *_, **kwargs: Any) -> None:
    pass
