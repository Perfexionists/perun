"""Flamegraph difference of the profile"""
from __future__ import annotations

# Standard Imports
from typing import Any
import os
import re

# Third-Party Imports
import click
import jinja2

# Perun Imports
from perun.utils import log
from perun.profile.factory import Profile
from perun.profile import helpers
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


def generate_header(profile: Profile) -> list[tuple[str, str]]:
    """

    :param profile: profile for which we are generating the header
    :return: list of tuples (key and value)
    """
    command = " ".join([profile["header"]["cmd"], profile["header"]["workload"]]).strip()
    return [
        ("origin", profile.get("origin")),
        ("command", command),
        ("collector command", log.collector_to_command(profile.get("collector_info"))),
    ]


def generate_flamegraph_diffrence(lhs_profile: Profile, rhs_profile: Profile, **kwargs: Any):
    """Generates differences of two profiles as two side-by-side flamegraphs

    :param lhs_profile: baseline profile
    :param rhs_profile: target profile
    :param kwargs: additional arguments
    """
    log.major_info("Generating Flamegraph Difference")
    lhs_graph = flamegraph_factory.draw_flame_graph(
        lhs_profile, kwargs.get("height"), kwargs.get("width"), no_title=True
    )
    log.minor_success("Baseline flamegraph", "generated")
    rhs_graph = flamegraph_factory.draw_flame_graph(
        rhs_profile, kwargs.get("height"), kwargs.get("width"), no_title=True
    )
    log.minor_success("Target flamegraph", "generated")

    env = jinja2.Environment(loader=jinja2.PackageLoader("perun.view_diff.flamegraph", "templates"))
    template = env.get_template("flamegraph.html.jinja2")
    content = template.render(
        lhs_flamegraph=escape_content("lhs", lhs_graph),
        lhs_header=generate_header(lhs_profile),
        lhs_tag="Baseline",
        rhs_flamegraph=escape_content("rhs", rhs_graph),
        rhs_header=generate_header(rhs_profile),
        rhs_tag="Target",
        title="Flamegraph",
    )
    log.minor_success("Difference report", "generated")

    if (output_file := kwargs.get("output_file")) is None:
        lhs_name = os.path.splitext(helpers.generate_profile_name(lhs_profile))[0]
        rhs_name = os.path.splitext(helpers.generate_profile_name(rhs_profile))[0]
        output_file = f"flamegraph-diff-of-{lhs_name}-and-{rhs_name}" + ".html"

    if not output_file.endswith("html"):
        output_file += ".html"

    with open(output_file, "w", encoding="utf-8") as template_out:
        template_out.write(content)

    log.minor_status("Output saved", log.path_style(output_file))


@click.command()
@click.pass_context
@click.option(
    "-w",
    "--width",
    type=click.INT,
    default=600,
    help="Sets the width of the flamegraph (default=600px).",
)
@click.option(
    "-h",
    "--height",
    type=click.INT,
    default=14,
    help="Sets the height of the flamegraph (default=14).",
)
@click.option("-o", "--output-file", help="Sets the output file (default=automatically generated).")
def flamegraph(ctx: click.Context, *_, **kwargs: Any) -> None:
    """ """
    profile_list = ctx.parent.params["profile_list"]
    generate_flamegraph_diffrence(profile_list[0], profile_list[1], **kwargs)
