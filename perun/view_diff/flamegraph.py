"""A module for generating flame graph difference grids of profiles.

Uses a customized flamegraph.pl script from B. Gregg to generate individual flame graph svgs.
(https://github.com/brendangregg/FlameGraph/blob/master/flamegraph.pl)
"""

from __future__ import annotations

# Standard Imports
from datetime import datetime, timezone
from pathlib import Path
import tempfile
from typing import Any, TYPE_CHECKING

# Third-Party Imports

# Perun Imports
import perun
from perun.profiles import structs, stats
from perun.profiles.polars import convert, structs as pl_structs
from perun.profiles.conversions import native_polars, polars_folded
from perun.logic import config
from perun.templates import factory as templates
from perun.utils import log
from perun.utils.common import diff_kit
from perun.utils.structs.view_structs import FlameGraphSettings
from perun.utils.structs.common_structs import WebColorPalette
from perun.view.flamegraph import grid as fg_grid
from perun.view_diff import chatbot

if TYPE_CHECKING:
    from perun.profiles.native import Profile


def generate_flamegraph_difference(
    baseline_profile: Profile, target_profile: Profile, **cli_kwargs: Any
) -> None:
    """Generates differences of two profiles as two side-by-side flamegraphs

    :param baseline_profile: a baseline Perun profile.
    :param target_profile: a target Perun profile.
    :param cli_kwargs: additional CLI arguments.
    """
    # Parse the input native profiles into aggregated baseline and target LazyFrames, and create
    # their Polars representation.
    log.major_info("Parsing Input Perun Profiles")
    postprocess_params = structs.PostprocessParameters(**cli_kwargs)
    func_maps = pl_structs.FunctionMaps()
    baseline_lf, baseline_features = native_polars.native_to_polars_lf(
        baseline_profile, postprocess_params, func_maps
    )
    target_lf, target_features = native_polars.native_to_polars_lf(
        target_profile, postprocess_params, func_maps
    )
    func_maps.finalize()

    pair_profile: pl_structs.PolarsTraceProfilePair = convert.create_polars_pair_profile(
        baseline_lf, baseline_features, target_lf, target_features, func_maps
    )
    log.minor_success("Parsing Input Perun Profiles")

    fg_settings = FlameGraphSettings.from_cli(
        **cli_kwargs,
        countname=list(baseline_profile["header"]["units"].values())[0],
        rootnode="Maximum (Baseline, Target)",
        subrootnode="Profile Total",
        total=max(
            pair_profile.baseline.features.total_resources,
            pair_profile.target.features.total_resources,
        ),
    )
    minwidth_threshold = fg_settings.compute_minwidth_threshold()

    # Dump the parsed and post-processed profiles back into a folded format for flamegraph scripts.
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
            lhs_diff_stats, rhs_diff_stats = diff_kit.generate_diff_of_stats(
                baseline_profile.all_stats(), target_profile.all_stats()
            )
            lhs_fg_diff_stats, rhs_fg_diff_stats = diff_kit.generate_diff_of_stats(
                stats.features_to_stats(pair_profile.baseline.features, fg_settings.countname),
                stats.features_to_stats(pair_profile.target.features, fg_settings.countname),
            )

            prompt_ctx = chatbot.generate_initial_prompt(
                cli_kwargs["chatbot_url"] is not None,
                cli_kwargs.get("chatbot_prompt_context", None),
            )

            template = templates.get_template("diff_views/flamegraph.html.jinja2")

            is_offline = config.lookup_key_recursively("showdiff.offline", False)
            utc_time_now = datetime.now(timezone.utc)
            creation_time = utc_time_now.strftime("%d %b %Y, %H:%M:%S") + " UTC"

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

    content = template.render(
        title="Perun Flame Graphs",
        perun_version=perun.__version__,
        timestamp=creation_time,
        chatbot=cli_kwargs["chatbot_url"],
        chatbot_prompt_context=prompt_ctx,
        lhs_tag="Baseline",
        lhs_fg_stats=lhs_fg_diff_stats,
        lhs_user_stats=lhs_diff_stats,
        rhs_tag="Target",
        rhs_user_stats=rhs_diff_stats,
        rhs_fg_stats=rhs_fg_diff_stats,
        flamegraphs=flamegraphs,
        palette=WebColorPalette,
        offline=is_offline,
        notes_enabled=False,
        default_theme=cli_kwargs.get("default_theme", "dark"),
    )

    output_path = diff_kit.generate_output_filepath(
        cli_kwargs["output_path"], "flamegraph", baseline_profile, target_profile
    )
    diff_kit.save_diff_view(output_path, content)

    log.minor_status("Flamegraph diff view saved", log.path_style(str(output_path)))
