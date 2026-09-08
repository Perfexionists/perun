"""A module that generates reports from external folded profiles."""

from __future__ import annotations

# Standard Imports
import dataclasses
from pathlib import Path
from typing import Any, Optional

# Third-Party Imports

# Perun Imports
from perun.profiles import imports, structs
from perun.profiles.conversions import folded_polars
from perun.profiles.polars import convert, structs as pl_structs
from perun.utils import log
from perun.utils.common import diff_kit
from perun.view_diff.report import core


def _extract_environment_spec(
    machine_info: dict[str, Any],
    exitcodes: str | list[str] | list[int],
    collector_command: str,
    command: str,
    label: str,
) -> list[structs.ProfileMetadataEntry]:
    """Generate profile header specification.

    :param machine_info: the machine specification
    :param exitcodes: possibly a collection of exit codes of profiling processes for each input
           profile
    :param collector_command: the name of the profiler that collected the profiles
    :param command: the profiled command and its input parameters
    :param label: a user-defined profile label

    :return: a collection of profile header entries corresponding to the profile specification
    """
    return [
        structs.ProfileMetadataEntry(
            "profile label",
            label if label else "?",
            "A label associated with this profile, if any.",
        ),
        structs.ProfileMetadataEntry(
            "command",
            command if command else "?",
            "The profiled command and its input parameters.",
        ),
        structs.ProfileMetadataEntry(
            "exitcode",
            diff_kit.format_exit_codes(exitcodes),
            "The exit code(s) that were returned by the profiling processes of each input profile.",
        ),
        structs.ProfileMetadataEntry(
            "collector command",
            collector_command,
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


def _extract_vulnerabilities(
    vulnerabilities: dict[str, str | float],
) -> list[structs.ProfileMetadataEntry]:
    """Generate vulnerabilities profile header from the machine info sub-dictionary.

    :param vulnerabilities: the machine info sub-dictionary containing CPU vulnerabilities
           specification

    :return: CPU vulnerabilities as a profile header entry
    """
    return [
        structs.ProfileMetadataEntry(
            "vulnerabilities",
            "?" if not vulnerabilities else "",
            "CPU vulnerabilities summary.",
            vulnerabilities,
        )
    ]


def generate_report_from_folded_profiles(
    baseline_profiles: str, target_profiles: str, **cli_kwargs: Any
) -> None:
    """Generate an interactive report from external folded profiles.

    :param baseline_profiles: the specification of baseline profiles from CLI; either a CSV file
           path, or a profile path with possibly an exit code and stat values
    :param target_profiles: the specification of target profiles from CLI; either a CSV file path,
           or a profile path with possibly an exit code and stat values
    :param cli_kwargs: additional parameters from the CLI
    """
    # Parse the profile specifications.
    base_dir = Path(cli_kwargs.get("baseline_dir", Path.cwd()))
    tar_dir = Path(cli_kwargs.get("target_dir", Path.cwd()))
    baseline_specs, baseline_stats = imports.parse_import_entries(
        [baseline_profiles], base_dir, cli_kwargs.get("baseline_stats_headers", None)
    )
    target_specs, target_stats = imports.parse_import_entries(
        [target_profiles], tar_dir, cli_kwargs.get("target_stats_headers", None)
    )
    if not baseline_specs:
        log.error("No valid baseline profiles specified. Terminating.")
    elif not target_specs:
        log.error("No valid target profiles specified. Terminating.")

    # Generate diffs of headers, stats, metadata, vulnerabilities, etc.
    baseline_metadata = imports.parse_metadata(
        cli_kwargs.get("baseline_metadata", tuple()), base_dir
    )
    target_metadata = imports.parse_metadata(cli_kwargs.get("target_metadata", tuple()), tar_dir)
    baseline_machine_info = imports.parse_machine_info(
        cli_kwargs.get("baseline_machine_info", ""), base_dir
    )
    target_machine_info = imports.parse_machine_info(
        cli_kwargs.get("target_machine_info", ""), tar_dir
    )

    baseline_env = _extract_environment_spec(
        baseline_machine_info,
        [prof.exit_code for prof in baseline_specs],
        cli_kwargs["baseline_collector_cmd"],
        cli_kwargs["baseline_cmd"],
        cli_kwargs["baseline_label"],
    )

    target_env = _extract_environment_spec(
        target_machine_info,
        [prof.exit_code for prof in target_specs],
        cli_kwargs["target_collector_cmd"],
        cli_kwargs["target_cmd"],
        cli_kwargs["target_label"],
    )

    baseline_vuln = _extract_vulnerabilities(baseline_machine_info.get("cpu_vulnerabilities", {}))
    target_vuln = _extract_vulnerabilities(target_machine_info.get("cpu_vulnerabilities", {}))

    baseline = core.ProfileMisc(baseline_env, baseline_metadata, baseline_vuln, baseline_stats)
    target = core.ProfileMisc(target_env, target_metadata, target_vuln, target_stats)

    # Parse the input folded profiles into aggregated baseline and target LazyFrames, and create
    # their Polars representation.
    log.major_info("Parsing Input Folded Profiles")
    postprocess_params = structs.PostprocessParameters(**cli_kwargs)
    func_maps = pl_structs.FunctionMaps()
    baseline_lf, baseline_features = folded_polars.folded_profiles_to_polars_lf(
        [prof.path for prof in baseline_specs], postprocess_params, func_maps
    )
    target_lf, target_features = folded_polars.folded_profiles_to_polars_lf(
        [prof.path for prof in target_specs], postprocess_params, func_maps
    )
    func_maps.finalize()

    pair_profile: pl_structs.PolarsTraceProfilePair = convert.create_polars_pair_profile(
        baseline_lf, baseline_features, target_lf, target_features, func_maps
    )
    log.minor_success("Parsing Input Folded Profiles")

    diff_html, creation_time = core.generate_report_view(
        pair_profile, baseline, target, cli_kwargs["profiled_resource"], **cli_kwargs
    )
    # FIXME: we do not have Perun profile objects that are necessary to automatically generate
    #  report names. Instead, we generate names with hopefully unique timestamps that should avoid
    #  overwriting other existing reports.
    output_filename: Optional[str] = cli_kwargs.get("output_path")
    if output_filename is None:
        file_timestamp = creation_time.isoformat(sep="-", timespec="milliseconds").replace(":", "-")
        output_path: Path = Path(f"report-folded_{file_timestamp}.html")
    else:
        output_path = Path(output_filename)
    diff_kit.save_diff_view(output_path, diff_html)

    log.minor_status("Report saved", log.path_style(str(output_path)))
