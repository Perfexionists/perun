"""The core logic that generates the HTML report from Polars profiles."""

from __future__ import annotations

# Standard Imports
from collections.abc import Iterable, Iterator, Mapping
import dataclasses
from datetime import datetime, timezone
from pathlib import Path
import tempfile
from typing import Any, Literal

# Third-Party Imports
import polars as pl

# Perun Imports
import perun
from perun.logic import config
from perun.profiles import stats as p_stats, structs
from perun.profiles.conversions import polars_folded
from perun.profiles.polars import convert, structs as pl_structs
from perun.templates import factory as templates
from perun.utils import log
from perun.utils.common import common_kit, diff_kit
from perun.utils.structs.common_structs import WebColorPalette
from perun.utils.structs.view_structs import FlameGraphSettings
from perun.view.flamegraph import grid as fg_grid
from perun.view_diff import chatbot
from perun.view_diff.report import diffs


@dataclasses.dataclass
class ProfileMisc:
    """Miscellaneous data associated with a profile.

    :ivar environment: machine properties of the machine where the profile was measured.
    :ivar metadata: user-specified profile metadata.
    :ivar vulnerabilities: CPU vulnerabilities mitigations.
    :ivar stats: profile stats.
    """

    environment: Iterable[structs.ProfileMetadataEntry]
    metadata: Iterable[structs.ProfileMetadataEntry]
    vulnerabilities: Iterable[structs.ProfileMetadataEntry]
    stats: Iterable[p_stats.ProfileStat]


@dataclasses.dataclass
class SelectionRow:
    """Helper dataclass for displaying selection of data

    :ivar uid: uid of the selected graph
    :ivar index: index in the sorted list of data
    :ivar fresh: the state of the uid - 1) not in baseline (added in target),
        2) not in target (removed in target), or 3) possibly unchanged
    :ivar stats: overview of all stat values
    :ivar trace_stats: a collection of stats for traces
    """

    __slots__ = [
        "uid",
        "index",
        "fresh",
        "main_stat",
        "stats",
        "trace_stats",
    ]

    def __init__(
        self,
        uid: str,
        index: int,
        fresh: Literal["not in baseline", "not in target", "in both"],
        stats: list[tuple[int, float, float, float, float, float]],
        trace_stats: list[
            tuple[
                str, int, float, float, float, float, float, float, float, float, float, float, str
            ]
        ],
    ) -> None:
        """Initializes the selection row."""
        self.uid: str = uid
        self.index: int = index
        self.fresh: Literal["not in baseline", "not in target", "in both"] = fresh
        # stat_type, baseline_abs, target_abs, prop_rel_delta, abs_delta, rel_delta
        self.stats: list[tuple[int, float, float, float, float, float]] = [
            (
                stat[0],
                common_kit.to_compact_num(stat[1]),
                common_kit.to_compact_num(stat[2]),
                common_kit.to_compact_num(stat[3]),
                common_kit.to_compact_num(stat[4]),
                common_kit.to_compact_num(stat[5]),
            )
            for stat in stats
        ]
        # trace, stat_t, baseline_abs_incl, baseline_abs_excl, target_abs_incl, target_abs_excl,
        # prop_rel_delta_incl, prop_rel_delta_excl, abs_delta_incl, abs_delta_excl,
        # rel_delta_incl, rel_delta_excl, long_trace
        self.trace_stats: list[
            tuple[
                str, int, float, float, float, float, float, float, float, float, float, float, str
            ]
        ] = [
            (
                t[0],
                t[1],
                common_kit.to_compact_num(t[2]),
                common_kit.to_compact_num(t[3]),
                common_kit.to_compact_num(t[4]),
                common_kit.to_compact_num(t[5]),
                common_kit.to_compact_num(t[6]),
                common_kit.to_compact_num(t[7]),
                common_kit.to_compact_num(t[8]),
                common_kit.to_compact_num(t[9]),
                common_kit.to_compact_num(t[10]),
                common_kit.to_compact_num(t[11]),
                t[12],
            )
            for t in trace_stats
        ]


def generate_report_view(
    pair_profile: pl_structs.PolarsTraceProfilePair,
    baseline: ProfileMisc,
    target: ProfileMisc,
    units: str,
    **cli_kwargs: Any,
) -> tuple[str, datetime]:
    """Generate an interactive HTML report from baseline-target profiles.

    :param pair_profile: a baseline-target Polars pair profile.
    :param baseline: miscellaneous data associated with the baseline profile.
    :param target: miscellaneous data associated with the target profile.
    :param units: the name of the resource units stored in the profiles.
    :param cli_kwargs: additional CLI parameters.

    :return: a generated HTML report and the time of its creation.
    """
    fg_settings = FlameGraphSettings.from_cli(
        **cli_kwargs,
        countname=units,
        rootnode="Maximum (Baseline, Target)",
        subrootnode="Profile Total",
        total=max(
            pair_profile.baseline.features.total_resources,
            pair_profile.target.features.total_resources,
        ),
    )
    minwidth_threshold = fg_settings.compute_minwidth_threshold()

    log.minor_info(f"Units: {fg_settings.countname}")
    # Dump the profiles back into a folded format for flamegraph scripts.
    grid = fg_grid.FlameGraphGrid()
    log.minor_info("Saving post-processed profiles in temporary files.")
    with (
        tempfile.NamedTemporaryFile(mode="w+") as baseline_folded,
        tempfile.NamedTemporaryFile(mode="w+") as target_folded,
    ):
        base_maxtrace = polars_folded.store_polars_as_folded_profile(
            pair_profile.baseline, baseline_folded, minwidth_threshold
        )
        tar_maxtrace = polars_folded.store_polars_as_folded_profile(
            pair_profile.target, target_folded, minwidth_threshold
        )
        fg_settings.maxtrace = max(base_maxtrace, tar_maxtrace)
        log.minor_success("Saving post-processed profiles in temporary files")

        # Build the flamegraph grid. The grid may be built serially or in parallel background
        # processes.
        grid_commands = fg_grid.build_flamegraph_grid_commands(
            Path(baseline_folded.name), Path(target_folded.name), fg_settings, escape_svgs=True
        )
        with fg_grid.build_flamegraph_grid(grid, grid_commands, fg_settings.parallelize):
            # If we build the flamegraphs in the background, we can analyze and further postprocess
            # the profiles in the meantime.
            log.minor_info("Analyzing and comparing profiles.")

            # Merge the baseline and target profiles and obtain the top differences in traces and
            # functions between the two profiles.
            filter_params = structs.FilterParameters(**cli_kwargs)
            merged = convert.merge_and_filter_polars_profiles(
                pair_profile.baseline, pair_profile.target, filter_params
            )
            trace_top_diffs = diffs.compute_top_diffs(
                merged.traces.lazy(),
                pair_profile.common_traces.lazy(),
                "trace",
                "prop_diff_incl",
                "prop_diff_excl",
                filter_params.top_diffs,
            )
            func_top_diffs = diffs.compute_top_diffs(
                merged.funcs.lazy(),
                pair_profile.common_funcs.lazy(),
                "func",
                "prop_diff_incl",
                "prop_diff_excl",
                filter_params.top_diffs,
            )

            # Extend the profiles with new difference metrics and transform them such that they
            # are suitable for building the traces table.
            tabular_profile = convert.polars_merged_to_tabular_profiles(
                merged, filter_params.max_function_traces
            )

            # Generate diffs of environments, stats, metadata, vulnerabilities, etc.
            lhs_header, rhs_header = diff_kit.generate_diff_of_headers(
                baseline.environment, target.environment
            )
            lhs_vulnerabilities, rhs_vulnerabilities = diff_kit.generate_diff_of_headers(
                baseline.vulnerabilities, target.vulnerabilities
            )
            lhs_diff_stats, rhs_diff_stats = diff_kit.generate_diff_of_stats(
                baseline.stats, target.stats
            )
            lhs_fg_diff_stats, rhs_fg_diff_stats = diff_kit.generate_diff_of_stats(
                p_stats.features_to_stats(pair_profile.baseline.features, fg_settings.countname),
                p_stats.features_to_stats(pair_profile.target.features, fg_settings.countname),
            )
            lhs_meta, rhs_meta = diff_kit.generate_diff_of_headers(
                baseline.metadata, target.metadata
            )

            log.minor_success("Analyzing and comparing profiles")

            # Generate chatbot-related data.
            prompt_ctx = chatbot.generate_initial_prompt(
                cli_kwargs["chatbot_url"] is not None,
                cli_kwargs.get("chatbot_prompt_context", None),
            )

            template = templates.get_template("diff_views/report.html.jinja2")

            utc_time_now = datetime.now(timezone.utc)
            report_time = utc_time_now.strftime("%d %b %Y, %H:%M:%S") + " UTC"
            is_report_offline = config.lookup_key_recursively("showdiff.offline", False)
            report_links = list(cli_kwargs.get("link", []))
    # Transform the flamegraph grid into the format expected by the report template.
    flamegraphs = [
        (
            f"Inclusive {fg_settings.countname} [#]",
            grid.baseline,
            grid.target,
            grid.baseline_target_diff,
            grid.target_baseline_diff,
        )
    ]

    log.major_info("Rendering HTML Report")

    content = template.render(
        title="Perun Report - Profiles Comparison",
        perun_version=perun.__version__,
        timestamp=report_time,
        chatbot=cli_kwargs["chatbot_url"],
        chatbot_prompt_context=prompt_ctx,
        lhs_tag="Baseline",
        lhs_header=lhs_header,
        lhs_vulnerabilities=lhs_vulnerabilities,
        lhs_user_stats=lhs_diff_stats,
        lhs_fg_stats=lhs_fg_diff_stats,
        lhs_metadata=lhs_meta,
        rhs_tag="Target",
        rhs_header=rhs_header,
        rhs_vulnerabilities=rhs_vulnerabilities,
        rhs_user_stats=rhs_diff_stats,
        rhs_fg_stats=rhs_fg_diff_stats,
        rhs_metadata=rhs_meta,
        palette=WebColorPalette,
        stat_list=[flamegraphs[0][0]],
        units=[fg_settings.countname],
        nodes=iter(pair_profile.baseline.maps.func_id_reverse_map.values()),
        flamegraphs=flamegraphs,
        selection_table=_iterate_polars_tabular(
            tabular_profile,
            pair_profile.common_funcs,
            pair_profile.baseline.maps.func_id_reverse_map,
        ),
        max_traces_per_func=filter_params.max_function_traces,
        offline=is_report_offline,
        notes_enabled=True,
        links=report_links,
        default_theme=cli_kwargs.get("default_theme", "dark"),
        top_diffs_trace_inclusive=diffs.iterate_top_diffs(trace_top_diffs[0]),
        top_diffs_trace_exclusive=diffs.iterate_top_diffs(trace_top_diffs[1]),
        top_diffs_func_inclusive=diffs.iterate_top_diffs(func_top_diffs[0]),
        top_diffs_func_exclusive=diffs.iterate_top_diffs(func_top_diffs[1]),
        total_baseline=pair_profile.baseline.features.total_resources,
        total_target=pair_profile.target.features.total_resources,
    )
    log.minor_success("HTML report", "rendered")
    return content, utc_time_now


def _iterate_polars_tabular(
    tabular_profile: pl_structs.PolarsTabularTraceProfiles,
    common_functions: pl.DataFrame,
    func_id_reverse_map: Mapping[int, str],
) -> Iterator[SelectionRow]:
    """Iterates over the tabular profiles and generates records for the report table.

    :param tabular_profile: the polars tabular profiles.
    :param common_functions: the set of function IDs common to both baseline and target profiles.
    :param func_id_reverse_map: a function ID -> function name mapping.

    :return: a generator of the report table records.
    """
    # Optimize dot operator access where it matters
    str_split = str.split
    str_rsplit = str.rsplit
    str_count = str.count
    tabular_funcs = tabular_profile.funcs
    df_row = pl.DataFrame.row
    df_iter_rows = pl.DataFrame.iter_rows

    common_funcs: set[int] = set(common_functions["func"].to_list())

    group_df: pl.DataFrame
    # Iterate over groups of traces belonging to individual functions from the lowest to the
    # highest function IDs.
    for idx, (_, group_df) in enumerate(
        tabular_profile.traces.group_by("func", maintain_order=True)
    ):
        # Obtain a row corresponding to the function from the function profile. We can access it
        # using an index thanks to the profile being sorted.
        row = df_row(tabular_funcs, idx)
        # Determine the state of the function. If it is not in the set of common functions, then we
        # look at the 'inclusive' and 'inclusive_target' values to determine wheter it is
        # a baseline-only or target-only function.
        state: Literal["not in baseline", "not in target", "in both"] = "in both"
        # row[0]: Function ID
        if row[0] not in common_funcs:
            # row[1]: inclusive
            if row[1] == 0:
                state = "not in baseline"
            # row[3]: inclusive_target
            elif row[3] == 0:
                state = "not in target"

        # Format the top traces according to the SelectionRow requirements.
        top_traces = [
            (
                # Short trace: 'firstID;lastID'
                f"{str_split(r[1], ';', maxsplit=1)[0]};{str_rsplit(r[1], ';', maxsplit=1)[-1]}",
                # Resource type, TODO: remove
                0,
                # inclusive
                r[2],
                # exclusive
                r[3],
                # inclusive_target
                r[4],
                # exclusive_target
                r[5],
                # prop_diff_incl
                r[6],
                # prop_diff_excl
                r[7],
                # abs_diff_incl
                r[8],
                # abs_diff_excl
                r[9],
                # rel_diff_incl
                r[10],
                # rel_diff_excl
                r[11],
                # Full trace: 'firstID;...;lastID#base1;...;baseN#target1;...;targetN'
                # FIXME: the part of the trace after the first '#' is not used, but the report
                #  still expects it. We will remove it later.
                f'{r[1]}#0{";0" * str_count(r[1], ";")}#0{";0" * str_count(r[1], ";")}',
            )
            for r in df_iter_rows(group_df)
        ]
        # Build the SelectionRow record.
        # FIXME: Remove the dependency on SelectionRow. We should ideally pass the records as tuples
        #  directly to improve performance.
        yield SelectionRow(
            # Function name
            func_id_reverse_map[row[0]],
            # Function ID
            row[0],
            state,
            # Inclusive and exclusive function stats:
            [
                # resource type index, inclusive (baseline), inclusive_target,
                #  prop_diff_incl, abs_diff_incl, rel_diff_incl
                (0, row[1], row[3], row[5], row[7], row[9]),
                # resource type index, exclusive (baseline), exclusive_target,
                #  prop_diff_excl, abs_diff_excl, rel_diff_excl
                (1, row[2], row[4], row[6], row[8], row[10]),
            ],
            top_traces,
        )
