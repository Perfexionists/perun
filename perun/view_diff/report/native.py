"""A module for generating reports from Perun-native profiles."""

from __future__ import annotations

# Standard Imports
from typing import Any, TYPE_CHECKING

# Third-Party Imports

# Perun Imports
from perun.profiles import structs
from perun.profiles.conversions import native_polars
from perun.profiles.polars import convert, structs as pl_structs
from perun.utils import log
from perun.utils.common import diff_kit
from perun.view_diff.report import core

if TYPE_CHECKING:
    from perun.profiles.native import Profile


def _extract_vulnerabilities(prof: Profile) -> list[structs.ProfileMetadataEntry]:
    """Generates vulnerabilities from the given profile

    :param prof: profile for which we are generating the specification
    :return: vulnerabilities as an entry
    """
    machine_info = prof.get("machine", {})
    return [
        structs.ProfileMetadataEntry(
            "vulnerabilities",
            "?" if "cpu_vulnerabilities" not in machine_info else "",
            "CPU vulnerabilities summary.",
            machine_info.get("cpu_vulnerabilities", {}),
        )
    ]


def _extract_environment_spec(prof: Profile) -> list[structs.ProfileMetadataEntry]:
    """Generates profile specification from the given profile

    :param prof: profile for which we are generating the specification

    :return: the profile specification as a list of entries
    """
    command = " ".join([prof["header"]["cmd"], prof["header"]["workload"]]).strip()
    exitcode = diff_kit.format_exit_codes(prof["header"].get("exitcode", "?"))
    machine_info = prof.get("machine", {})
    return [
        structs.ProfileMetadataEntry(
            "origin",
            prof.get("origin", "?"),
            "The version control version, for which the profile was measured.",
        ),
        structs.ProfileMetadataEntry(
            "profile label",
            prof["header"].get("label", "-"),
            "A label associated with this profile, if any.",
        ),
        structs.ProfileMetadataEntry(
            "command", command, "The workload / command, for which the profile was measured."
        ),
        structs.ProfileMetadataEntry(
            "exitcode", exitcode, "The exit code that was returned by the underlying command."
        ),
        structs.ProfileMetadataEntry(
            "collector command",
            log.collector_to_command(prof.get("collector_info", {})),
            "The collector / profiler, which collected the data.",
        ),
        structs.ProfileMetadataEntry(
            "kernel",
            machine_info.get("release", "?"),
            "The underlying kernel version, where the results were measured.",
        ),
        structs.ProfileMetadataEntry(
            "boot info",
            machine_info.get("boot_info", "?"),
            "The contents of `/proc/cmdline` containing boot information about kernel",
        ),
        structs.ProfileMetadataEntry(
            "host", machine_info["host"], "The hostname, where the results were measured."
        ),
        structs.ProfileMetadataEntry(
            "cpu (total)",
            machine_info.get("cpu", {"total": "?"}).get("total", "?"),
            "The total number (physical and virtual) of CPUs available on the host.",
        ),
        structs.ProfileMetadataEntry(
            "memory (total)",
            machine_info.get("memory", {"total_ram": "?"}).get("total_ram", "?"),
            "The total number of RAM available on the host.",
        ),
    ]


def generate_report_from_native_profiles(
    baseline_profile: Profile, target_profile: Profile, **cli_kwargs: Any
) -> None:
    """Generate an interactive report from Perun profiles.

    :param baseline_profile: the baseline Perun profile.
    :param target_profile: the target Perun profile.
    :param cli_kwargs: additional CLI parameters.
    """

    baseline = core.ProfileMisc(
        _extract_environment_spec(baseline_profile),
        baseline_profile.all_metadata(),
        _extract_vulnerabilities(baseline_profile),
        baseline_profile.all_stats(),
    )
    target = core.ProfileMisc(
        _extract_environment_spec(target_profile),
        target_profile.all_metadata(),
        _extract_vulnerabilities(target_profile),
        target_profile.all_stats(),
    )

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

    diff_html, creation_time = core.generate_report_view(
        pair_profile,
        baseline,
        target,
        list(baseline_profile["header"]["units"].values())[0],
        **cli_kwargs,
    )
    output_path = diff_kit.generate_output_filepath(
        cli_kwargs["output_path"], "report", baseline_profile, target_profile
    )
    diff_kit.save_diff_view(output_path, diff_html)

    log.minor_status("Report saved", log.path_style(str(output_path)))
