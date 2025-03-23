"""Flamegraph difference of the profile"""

from __future__ import annotations

# Standard Imports
from collections import defaultdict
from datetime import datetime, timezone
import pathlib
from subprocess import CalledProcessError
from typing import Any
import re

# Third-Party Imports
import click

# Perun Imports
import perun
from perun.templates import factory as templates
from perun.utils import log, mapping
from perun.utils.common import common_kit, diff_kit
from perun.profile import convert, stats as profile_stats
from perun.profile.factory import Profile
from perun.view.flamegraph import flamegraph as flamegraph_factory
from perun.view_diff.short import run as table_run


# Default values of some flamegraph.pl arguments that our code needs as well
FG_DEFAULT_IMAGE_WIDTH: int = 800
FG_DEFAULT_MIN_WIDTH: float = 0.1

TAGS_TO_INDEX: list[str] = []


def escape_content(tag: str, content: str) -> str:
    """Escapes content, so there are no clashes in the files

    :param tag: tag used to prefix all the functions and ids
    :param content: generated svg content
    :return: escaped content
    """
    if tag not in TAGS_TO_INDEX:
        TAGS_TO_INDEX.append(tag)
    functions = [
        r"(?<!\w)(c)\(",
        r"(?<!\w)(get_params)\(",
        r"(?<!\w)(parse_params)\(",
        r"(?<!\w)(find_child)\(",
        r"(?<!\w)(find_group)\(",
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
        r"(?<!\w)(clearzoom)\(",
        r"(?<!\w)(unzoom)\(",
        r"(?<!\w)(update_text)\(",
        r"(?<!\w)(zoom)\(",
        r"(?<!\w)(zoom_child)\(",
        r"(?<!\w)(zoom_parent)\(",
        r"(?<!\w)(zoom_reset)\(",
    ]
    other = [
        (r"\"search\"", f'"{tag}_search"'),
        (r"\"background\"", f'"{tag}_background"'),
        (r"#background", f"#{tag}_background"),
        (r"\"frames\"", f'"{tag}_frames"'),
        (r"#frames", f"#{tag}_frames"),
        (r"\"unzoom\"", f'"{tag}_unzoom"'),
        (r"\"matched\"", f'"{tag}_matched"'),
        (r"details", f"{tag}_details"),
        (r"searchbtn", f"{tag}_searchbtn"),
        (r"unzoombtn", f"{tag}_unzoombtn"),
        (r"currentSearchTerm", f"{tag}_currentSearchTerm"),
        (r"ignorecase", f"{tag}_ignorecase"),
        (r"ignorecaseBtn", f"{tag}_ignorecaseBtn"),
        (r"searching", f"{tag}_searching"),
        (r"matchedtxt", f"{tag}_matchedtxt"),
        (r"svg\.", f"{tag}_svg."),
        (r"svg =", f"{tag}_svg ="),
        (r"svg,", f"{tag}_svg,"),
        (r">\s*\n<", r"><"),
        (
            r"getElementsByTagName\(\"svg\"\)\[0\]",
            f'getElementsByClassName("svg-content")[{TAGS_TO_INDEX.index(tag)}]',
        ),
        (r"document.", f"{tag}_svg."),
        (
            f"({tag}_(svg|details|searchbtn|matchedtxt|ignorecaseBtn|unzoombtn)) = {tag}_svg.",
            "\\1 = document.",
        ),
        # Huge thanks to following article:
        # https://chartio.com/resources/tutorials/how-to-resize-an-svg-when-the-window-is-resized-in-d3-js/
        # Which helped to solve the issue with non-resizable flamegraphs
        (
            '<svg version="1.1" width="[0-9]+" height="[0-9]+"',
            '<svg version="1.1" preserveAspectRatio="xMinYMin meet" class="svg-content"',
        ),
    ]
    for func in functions:
        content = re.sub(func, f"{tag}_\\1(", content)
    for unit, sub in other:
        content = re.sub(unit, sub, content)
    return content


def get_uids(profile: Profile) -> set[str]:
    """For given profile return set of uids

    :param profile: profile
    :return: set of unique uids in profile
    """
    df = convert.resources_to_pandas_dataframe(profile)
    return set(df["uid"].unique())


def generate_flamegraphs(
    lhs_profile: Profile,
    rhs_profile: Profile,
    data_types: list[str],
    skip_diff: bool = False,
    minimize: bool = False,
    **fg_forward_kwargs: Any,
) -> list[tuple[str, str, str, str, str]]:
    """Constructs a list of tuples of flamegraphs for list of data_types

    :param lhs_profile: baseline profile
    :param rhs_profile: target profile
    :param data_types: list of data types (resources)
    :param skip_diff: whether the flamegraph diff should be skipped or not
    :param minimize: whether the flamegraph should be minimized or not
    :param fg_forward_kwargs: additional parameters forwarded to the flamegraph scripts

    :return: a collection of (data_type, lhs flamegraph, rhs flamegraph, lhs_rhs_diff_flamegraph,
             rhs_lhs_diff_flamegraph) tuples
    """
    flamegraphs = []
    for i, dtype in log.progress(enumerate(data_types), description="Generating Flamegraphs"):
        try:
            data_type = mapping.from_readable_key(dtype)
            lhs_flame = convert.to_flame_graph_format(
                lhs_profile, profile_key=data_type, minimize=minimize
            )
            rhs_flame = convert.to_flame_graph_format(
                rhs_profile, profile_key=data_type, minimize=minimize
            )
            fg_image_width = fg_forward_kwargs["width"]
            fg_minwidth = fg_forward_kwargs.get("minwidth", f"{FG_DEFAULT_MIN_WIDTH}")
            _, lhs_max_trace, lhs_max_res = flamegraph_factory.compute_max_traces(
                lhs_flame, fg_image_width, fg_minwidth
            )
            _, rhs_max_trace, rhs_max_res = flamegraph_factory.compute_max_traces(
                rhs_flame, fg_image_width, fg_minwidth
            )
            fg_forward_kwargs["maxtrace"] = max(lhs_max_trace, rhs_max_trace)
            fg_forward_kwargs["total"] = max(lhs_max_res, rhs_max_res)

            with (
                flamegraph_factory.fg_optional_tempfile(lhs_flame) as lhs_file,
                flamegraph_factory.fg_optional_tempfile(rhs_flame) as rhs_file,
            ):
                lhs_graph = flamegraph_factory.draw_flame_graph(
                    lhs_file,
                    "Baseline Flamegraph",
                    **fg_forward_kwargs,
                )
                escaped_lhs = escape_content(f"lhs_{i}", lhs_graph)
                log.minor_success(f"Baseline flamegraph ({dtype})", "generated")

                rhs_graph = flamegraph_factory.draw_flame_graph(
                    rhs_file,
                    "Target Flamegraph",
                    **fg_forward_kwargs,
                )
                escaped_rhs = escape_content(f"rhs_{i}", rhs_graph)
                log.minor_success(f"Target flamegraph ({dtype})", "generated")

                if skip_diff:
                    lhs_escaped_diff, rhs_escaped_diff = "", ""
                else:
                    lhs_rhs_diff = flamegraph_factory.draw_differential_flame_graph(
                        lhs_file,
                        rhs_file,
                        "Baseline-Target Diff Flamegraph",
                        **fg_forward_kwargs,
                    )
                    lhs_escaped_diff = escape_content(f"lhs_diff_{i}", lhs_rhs_diff)
                    log.minor_success(f"Baseline-target diff flamegraph ({dtype})", "generated")

                    # We add the '--negate' for consistent diff colors in the rhs to lhs
                    # flamegraph diff
                    rhs_lhs_diff = flamegraph_factory.draw_differential_flame_graph(
                        rhs_file,
                        lhs_file,
                        "Target-Baseline Diff Flamegraph",
                        "samples",
                        "negate",
                        **fg_forward_kwargs,
                    )
                    rhs_escaped_diff = escape_content(f"rhs_diff_{i}", rhs_lhs_diff)
                    log.minor_success(f"Target-baseline diff flamegraph ({dtype})", "generated")
            flamegraphs.append(
                (dtype, escaped_lhs, escaped_rhs, lhs_escaped_diff, rhs_escaped_diff)
            )
            # Attempt to remove the leftover temporary 'palette.map' file that is no longer needed
            pathlib.Path("palette.map").unlink(missing_ok=True)
        except CalledProcessError as exc:
            log.warn(
                f"could not generate flamegraphs: {exc}\n"
                f"Error message: {exc.stderr.decode('utf-8')}"
            )
    return flamegraphs


def process_maxima(
    maxima_per_resources: dict[str, float], stats: list[profile_stats.ProfileStat], profile: Profile
) -> int:
    """Processes maxima for each profile

    :param maxima_per_resources: dictionary that maps resources to their maxima
    :param stats: list of profile stats to extend
    :param profile: input profile

    :return: the length of the maximum trace
    """
    is_inclusive = profile.get("collector_info", {}).get("name") == "kperf"
    counts: dict[str, float] = defaultdict(float)
    max_trace = 0
    for _, resource in log.progress(
        profile.all_resources(), description="Processing Resource Maxima"
    ):
        max_trace = max(max_trace, len(resource["trace"]) + 1)
        if is_inclusive:
            for key in resource:
                amount = common_kit.try_convert(resource[key], [float])
                if amount is None or key in ("time", "command", "uid"):
                    continue
                counts[key] += amount
    for key in counts.keys():
        maxima_per_resources[key] = max(maxima_per_resources[key], counts[key])
        stats.append(
            profile_stats.ProfileStat(
                f"Overall {key}",
                profile_stats.ProfileStatComparison.LOWER,
                description=f"The overall value of the {key} for the root value",
                value=[int(counts[key])],
            )
        )
    stats.append(
        profile_stats.ProfileStat(
            "Maximum Trace Length",
            profile_stats.ProfileStatComparison.LOWER,
            description="Maximum length of the trace in the profile",
            value=[max_trace],
        )
    )
    return max_trace


def generate_flamegraph_difference(
    lhs_profile: Profile, rhs_profile: Profile, **kwargs: Any
) -> None:
    """Generates differences of two profiles as two side-by-side flamegraphs

    :param lhs_profile: baseline profile
    :param rhs_profile: target profile
    :param kwargs: additional arguments
    """
    maxima_per_resource: dict[str, float] = defaultdict(float)
    lhs_stats: list[profile_stats.ProfileStat] = []
    rhs_stats: list[profile_stats.ProfileStat] = []
    lhs_types = list(lhs_profile.all_resource_fields())
    rhs_types = list(rhs_profile.all_resource_fields())
    data_types = diff_kit.get_candidate_keys(set(lhs_types).union(set(rhs_types)))
    data_type = list(data_types)[0]
    process_maxima(maxima_per_resource, lhs_stats, lhs_profile)
    process_maxima(maxima_per_resource, rhs_stats, rhs_profile)
    lhs_stats += list(lhs_profile.all_stats())
    rhs_stats += list(rhs_profile.all_stats())
    lhs_final_stats, rhs_final_stats = diff_kit.generate_diff_of_stats(lhs_stats, rhs_stats)

    log.major_info("Generating Flamegraph Difference")
    flamegraphs = generate_flamegraphs(lhs_profile, rhs_profile, data_types, width=kwargs["width"])
    lhs_header, rhs_header = diff_kit.generate_diff_of_headers(
        diff_kit.generate_specification(lhs_profile), diff_kit.generate_specification(rhs_profile)
    )
    lhs_meta, rhs_meta = diff_kit.generate_diff_of_headers(
        lhs_profile.all_metadata(), rhs_profile.all_metadata()
    )

    template = templates.get_template("diff_view_flamegraph.html.jinja2")
    content = template.render(
        flamegraphs=flamegraphs,
        perun_version=perun.__version__,
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + " UTC",
        lhs_header=lhs_header,
        lhs_tag="Baseline (base)",
        lhs_top=table_run.get_top_n_records(lhs_profile, top_n=10, aggregated_key=data_type),
        lhs_stats=lhs_final_stats,
        lhs_metadata=lhs_meta,
        lhs_uids=get_uids(lhs_profile),
        rhs_header=rhs_header,
        rhs_tag="Target (tgt)",
        rhs_top=table_run.get_top_n_records(rhs_profile, top_n=10, aggregated_key=data_type),
        rhs_stats=rhs_final_stats,
        rhs_metadata=rhs_meta,
        rhs_uids=get_uids(rhs_profile),
        title="Differences of profiles (with flamegraphs)",
        data_types=data_types,
    )
    log.minor_success("Difference report", "generated")
    output_file = diff_kit.save_diff_view(
        kwargs.get("output_file"), content, "flamegraph", lhs_profile, rhs_profile
    )
    log.minor_status("Output saved", log.path_style(output_file))


@click.command()
@click.pass_context
@click.option(
    "--width",
    "-w",
    type=click.INT,
    default=FG_DEFAULT_IMAGE_WIDTH,
    help=f"Sets the width of the flamegraph (default={FG_DEFAULT_IMAGE_WIDTH}px).",
)
@click.option("--output-file", "-o", help="Sets the output file (default=automatically generated).")
def flamegraph(ctx: click.Context, *_: Any, **kwargs: Any) -> None:
    """ """
    assert ctx.parent is not None and f"impossible happened: {ctx} has no parent"
    profile_list = ctx.parent.params["profile_list"]
    generate_flamegraph_difference(profile_list[0], profile_list[1], **kwargs)
