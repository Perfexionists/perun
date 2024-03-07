"""Flamegraph difference of the profile"""
from __future__ import annotations

# Standard Imports
from typing import Any

# Third-Party Imports
import click
import jinja2

# Perun Imports
from perun.profile.factory import Profile
from perun.profile import convert


def generate_flamegraph_diffrence(lhs_profile: Profile, rhs_profile: Profile, **kwargs: Any):
    env = jinja2.Environment(loader=jinja2.PackageLoader("perun.view_diff.flamegraph", "templates"))
    template = env.get_template("flamegraph.html.jinja2")
    content = template.render()

    with open("test.html", "w", encoding="utf-8") as template_out:
        template_out.write(content)


@click.command()
@click.pass_context
def flamegraph(ctx: click.Context, *_, **kwargs: Any) -> None:
    profile_list = ctx.parent.params["profile_list"]
    generate_flamegraph_diffrence(profile_list[0], profile_list[1], **kwargs)
