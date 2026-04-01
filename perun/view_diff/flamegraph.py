"""A module for generating flame graph difference grids of profiles.

Uses a customized flamegraph.pl script from B. Gregg to generate individual flame graph svgs.
(https://github.com/brendangregg/FlameGraph/blob/master/flamegraph.pl)
"""

from __future__ import annotations

# Standard Imports
from dataclasses import dataclass
from datetime import datetime, timezone
import pathlib
from subprocess import CalledProcessError
from typing import Any
import re

# Third-Party Imports

# Perun Imports
import perun
from perun import profile as profile
from perun.logic import config
from perun.templates import factory as templates
from perun.utils import log, mapping
from perun.utils.common import diff_kit
from perun.utils.structs.common_structs import WebColorPalette
from perun.utils.structs.diff_structs import FG_DEFAULT_MIN_WIDTH
from perun.view.flamegraph import flamegraph as flamegraph_factory

TAGS_TO_INDEX: list[str] = []


@dataclass
class FlameGraphStats:
    """A helper dataclass for storing flamegraph-related stats.

    :ivar dtype: the datatype identifier
    :ivar max_trace: the longest found trace
    :ivar max_filtered_trace: the longest found trace after filtering is applied
    :ivar total_resource: the total consumed dtype resource
    """

    dtype: str
    max_trace: int = 0
    max_filtered_trace: int = 0
    total_resource: int = 0


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
        r"(?<!\w)(reset_search_hover)\(",
        r"(?<!\w)(s)\(",
        r"(?<!\w)(search)\(",
        r"(?<!\w)(search_hover)\(",
        r"(?<!\w)(search_prompt)\(",
        r"(?<!\w)(find_frames)\(",
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
        (r"\"matchedhover\"", f'"{tag}_matchedhover"'),
        (r"details", f"{tag}_details"),
        (r"searchbtn", f"{tag}_searchbtn"),
        (r"unzoombtn", f"{tag}_unzoombtn"),
        (r"currentSearchTerm", f"{tag}_currentSearchTerm"),
        (r"hoverSearchTerm", f"{tag}_hoverSearchTerm"),
        (r"ignorecase", f"{tag}_ignorecase"),
        (r"ignorecaseBtn", f"{tag}_ignorecaseBtn"),
        (r"searching", f"{tag}_searching"),
        (r"matchedtxt", f"{tag}_matchedtxt"),
        (r"matchedHoverTxt", f"{tag}_matchedHoverTxt"),
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
            f"({tag}_(svg|details|searchbtn|matchedtxt|matchedHoverTxt|ignorecaseBtn|unzoombtn)) = {tag}_svg.",
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


def generate_flamegraphs(
    lhs_profile: profile.Profile,
    rhs_profile: profile.Profile,
    data_types: list[str],
    skip_diff: bool = False,
    minimize: bool = False,
    squash_unknown: bool = True,
    **fg_forward_kwargs: Any,
) -> tuple[list[tuple[str, str, str, str, str]], list[FlameGraphStats], list[FlameGraphStats]]:
    """Constructs a list of tuples of flamegraphs for list of data_types

    :param lhs_profile: baseline profile
    :param rhs_profile: target profile
    :param data_types: list of data types (resources)
    :param skip_diff: whether the flamegraph diff should be skipped or not
    :param minimize: whether the flamegraph should be minimized or not
    :param squash_unknown: whether recursive [unknown] frames should be squashed into a single one
    :param fg_forward_kwargs: additional parameters forwarded to the flamegraph scripts

    :return: a collection of (data_type, lhs flamegraph, rhs flamegraph, lhs_rhs_diff_flamegraph,
             rhs_lhs_diff_flamegraph) tuples
    """
    flamegraphs = []
    lhs_stats, rhs_stats = [], []
    for i, dtype in log.progress(enumerate(data_types), description="Generating Flame Graphs"):
        try:
            data_type = mapping.from_readable_key(dtype)
            lhs_flame = profile.to_flame_graph_format(
                lhs_profile, profile_key=data_type, minimize=minimize, squash_unknown=squash_unknown
            )
            rhs_flame = profile.to_flame_graph_format(
                rhs_profile, profile_key=data_type, minimize=minimize, squash_unknown=squash_unknown
            )
            fg_image_width = fg_forward_kwargs["width"]
            fg_minwidth = fg_forward_kwargs.get("minwidth", f"{FG_DEFAULT_MIN_WIDTH}")
            lhs_max_trace, lhs_max_filt_trace, lhs_max_res = flamegraph_factory.compute_max_traces(
                lhs_flame, fg_image_width, fg_minwidth
            )
            rhs_max_trace, rhs_max_filt_trace, rhs_max_res = flamegraph_factory.compute_max_traces(
                rhs_flame, fg_image_width, fg_minwidth
            )
            fg_forward_kwargs["maxtrace"] = max(lhs_max_filt_trace, rhs_max_filt_trace)
            fg_forward_kwargs["total"] = max(lhs_max_res, rhs_max_res)

            lhs_stats.append(
                FlameGraphStats(data_type, lhs_max_trace, lhs_max_filt_trace, lhs_max_res)
            )
            rhs_stats.append(
                FlameGraphStats(data_type, rhs_max_trace, rhs_max_filt_trace, rhs_max_res)
            )

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
    return flamegraphs, lhs_stats, rhs_stats


def process_flamegraph_stats(fg_stats: list[FlameGraphStats]) -> list[profile.ProfileStat]:
    profile_stats: list[profile.ProfileStat] = []
    max_trace, max_filtered_trace = 0, 0

    for stat in fg_stats:
        # TODO: This is a bit of a hack since the readable_key already contains the unit
        name, unit = mapping.get_readable_key(stat.dtype).split("[", maxsplit=1)
        name.rstrip()
        unit = unit.rsplit("]", maxsplit=1)[0]
        profile_stats.append(
            profile.ProfileStat(
                f"Total {name}",
                profile.ProfileStatComparison.LOWER,
                unit,
                description=f"The total value of the {stat.dtype}",
                value=[stat.total_resource],
            )
        )
        max_trace = max(max_trace, stat.max_trace)
        max_filtered_trace = max(max_filtered_trace, stat.max_filtered_trace)

    profile_stats.append(
        profile.ProfileStat(
            "Longest Profile Trace",
            profile.ProfileStatComparison.LOWER,
            "#",
            description="The longest trace recorded in the profile",
            value=[max_trace],
        )
    )
    profile_stats.append(
        profile.ProfileStat(
            "Longest Flame Graph Trace",
            profile.ProfileStatComparison.LOWER,
            "#",
            description=(
                "The longest trace in the Flame Graph, which might be shorter than the longest "
                "trace in the profile due to filtering."
            ),
            value=[max_filtered_trace],
        )
    )
    return profile_stats


def generate_flamegraph_difference(
    lhs_profile: profile.Profile, rhs_profile: profile.Profile, **kwargs: Any
) -> None:
    """Generates differences of two profiles as two side-by-side flamegraphs

    :param lhs_profile: baseline profile
    :param rhs_profile: target profile
    :param kwargs: additional arguments
    """
    fg_forward_kwargs = {
        arg.replace("flamegraph_", ""): val
        for arg, val in kwargs.items()
        if arg.startswith("flamegraph_")
    }
    # FIXME: temporary solution before refactoring to FlameGraphSettings.
    del fg_forward_kwargs["parallelize"]

    lhs_stats: list[profile.ProfileStat] = list(lhs_profile.all_stats())
    rhs_stats: list[profile.ProfileStat] = list(rhs_profile.all_stats())
    data_types = [
        mapping.get_readable_key(key)
        for key in diff_kit.get_candidate_keys(
            set(lhs_profile.all_resource_fields()).union(set(rhs_profile.all_resource_fields()))
        )
    ]

    log.major_info("Generating Flamegraph Grid")
    flamegraphs, lhs_fg_stats, rhs_fg_stats = generate_flamegraphs(
        lhs_profile,
        rhs_profile,
        data_types,
        skip_diff=False,
        minimize=kwargs.get("minimize", False),
        squash_unknown=not kwargs.get("no_squash_unknown", False),
        **fg_forward_kwargs,
    )
    lhs_diff_stats, rhs_diff_stats = diff_kit.generate_diff_of_stats(lhs_stats, rhs_stats)
    lhs_fg_diff_stats, rhs_fg_diff_stats = diff_kit.generate_diff_of_stats(
        process_flamegraph_stats(lhs_fg_stats), process_flamegraph_stats(rhs_fg_stats)
    )

    template = templates.get_template("diff_views/flamegraph.html.jinja2")
    content = template.render(
        title="Perun Flame Graphs",
        perun_version=perun.__version__,
        timestamp=datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M:%S") + " UTC",
        lhs_tag="Baseline (base)",
        lhs_fg_stats=lhs_fg_diff_stats,
        lhs_user_stats=lhs_diff_stats,
        rhs_tag="Target (tgt)",
        rhs_user_stats=rhs_diff_stats,
        rhs_fg_stats=rhs_fg_diff_stats,
        flamegraphs=flamegraphs,
        palette=WebColorPalette,
        offline=config.lookup_key_recursively("showdiff.offline", False),
        notes_enabled=False,
    )
    log.minor_success("Flame Graph grid template", "rendered")
    output_file = diff_kit.save_diff_view(
        kwargs.get("output_path"), content, "flamegraph", lhs_profile, rhs_profile
    )
    log.minor_status("Output saved", log.path_style(output_file))
