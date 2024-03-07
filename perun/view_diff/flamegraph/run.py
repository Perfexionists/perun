"""Flamegraph difference of the profile"""
from __future__ import annotations

# Standard Imports
from typing import Any
import re

# Third-Party Imports
import click
import jinja2

# Perun Imports
from perun.profile.factory import Profile
from perun.view.flamegraph import flamegraph as flamegraph_factory


def escape_content(tag: str, content: str) -> str:
    """Escapes content, so there are no clashes in the files

    :param tag: tag used to prefix all the functions and ids
    :param content: generated svg content
    :return: escaped content
    """
    functions = [
        r"(?<!\w)(c)\(",
        r"(?<!\w)(find_child)\(",
        r"(?<!\w)(g_to_func)\(",
        r"(?<!\w)(g_to_text)\(",
        r"(?<!\w)(init)\(",
        r"(?<!\w)(orig_load)\(",
        r"(?<!\w)(orig_save)\(",
        r"(?<!\w)(reset_search)\(",
        r"(?<!\w)(s)\(",
        r"(?<!\w)(search)\(",
        r"(?<!\w)(search_prompt)\(",
        r"(?<!\w)(searchout)\(",
        r"(?<!\w)(searchover)\(",
        r"(?<!\w)(unzoom)\(",
        r"(?<!\w)(update_text)\(",
        r"(?<!\w)(zoom)\(",
        r"(?<!\w)(zoom_child)\(",
        r"(?<!\w)(zoom_parent)\(",
        r"(?<!\w)(zoom_reset)\(",
    ]
    other = [
        (r"func_g", f"{tag}_func_g"),
        (r"\"unzoom\"", f'"{tag}_unzoom"'),
        (r"\"search\"", f'"{tag}_search"'),
        (r"\"matched\"", f'"{tag}_matched"'),
        (r"details", f"{tag}_details"),
        (r"searchbtn", f"{tag}_searchbtn"),
        (r"searching", f"{tag}_searching"),
        (r"matchedtxt", f"{tag}_matchedtxt"),
        (r"svg\.", f"{tag}_svg."),
        (r"svg =", f"{tag}_svg ="),
        (r"svg;", f"{tag}_svg;"),
        (r"\[0\]", "[1]" if tag == "rhs" else "[0]"),
        (r"document.", f"{tag}_svg."),
        (f"({tag}_(svg|details|searchbtn|matchedtxt)) = {tag}_svg\.", f"\\1 = document."),
    ]
    for func in functions:
        content = re.sub(func, f"{tag}_\\1(", content)
    for unit, sub in other:
        content = re.sub(unit, sub, content)
    return content


def generate_flamegraph_diffrence(lhs_profile: Profile, rhs_profile: Profile, **kwargs: Any):
    """Generates differences of two profiles as two side-by-side flamegraphs

    :param lhs_profile: baseline profile
    :param rhs_profile: target profile
    :param kwargs: additional arguments
    """
    lhs_graph = flamegraph_factory.draw_flame_graph(lhs_profile, 20, 600)
    rhs_graph = flamegraph_factory.draw_flame_graph(rhs_profile, 20, 600)

    env = jinja2.Environment(loader=jinja2.PackageLoader("perun.view_diff.flamegraph", "templates"))
    template = env.get_template("flamegraph.html.jinja2")
    content = template.render(
        lhs_flamegraph=escape_content("lhs", lhs_graph),
        rhs_flamegraph=escape_content("rhs", rhs_graph),
        title="Flamegraph",
    )

    with open("test.html", "w", encoding="utf-8") as template_out:
        template_out.write(content)


@click.command()
@click.pass_context
def flamegraph(ctx: click.Context, *_, **kwargs: Any) -> None:
    """ """
    profile_list = ctx.parent.params["profile_list"]
    generate_flamegraph_diffrence(profile_list[0], profile_list[1], **kwargs)
