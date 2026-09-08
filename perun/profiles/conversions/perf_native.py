"""Functions for importing Perf profiles as native profiles."""

from __future__ import annotations

# Standard Imports
from dataclasses import asdict
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

# Third-Party Imports

# Perun Imports
from perun.profiles import imports, native as profile, stats
from perun.profiles.folded import parser
from perun.logic import config, pcs
from perun.utils import log, streams
from perun.utils.common import script_kit
from perun.utils.external import commands as external_commands
from perun.utils.structs.common_structs import MinorVersion
from perun.vcs import vcs_kit


@vcs_kit.lookup_minor_version
def import_perf_from_record(
    import_entries: list[str],
    stats_headers: str | None,
    minor_version: str,
    with_sudo: bool = False,
    **kwargs: Any,
) -> None:
    """Imports profiles collected by `perf record` command.

    First, the function parses all the perf import entries and stats headers, and then it runs
    the perf script + parser script for each entry to generate the profile.

    :param import_entries: a collection of import entries (profiles or CSV files).
    :param stats_headers: CLI-specified stats headers.
    :param minor_version: minor version corresponding to the imported profiles.
    :param with_sudo: indication whether the data were collected with sudo.
    :param kwargs: rest of the parameters.
    """
    # TODO: tag commands with (platform, system, ...) requirements and have a unified mechanism
    #   to detect failures
    # TODO: can be optimized a lot.
    if sys.platform == "darwin":
        log.error("Import from perf record is not supported on macOS platform.")
    parse_script = script_kit.get_script("stackcollapse-perf.pl")
    import_dir = Path(config.lookup_key_recursively("import.dir", os.getcwd()))
    profiles, prof_stats = imports.parse_import_entries(import_entries, import_dir, stats_headers)
    resources: list[dict[str, str | int]] = []

    for imported_file in profiles:
        perf_script_command = (
            f"{'sudo ' if with_sudo else ''}perf script -i {imported_file.path} | {parse_script}"
        )
        try:
            out, _ = external_commands.run_safely_external_command(perf_script_command)
            log.minor_success(
                f"Raw data from {log.path_style(str(imported_file.path))}", "collected"
            )
        except subprocess.CalledProcessError as err:
            log.minor_fail(
                f"Raw data from {log.path_style(str(imported_file.path))}", "not collected"
            )
            log.error(f"Cannot load data due to: {err}")
        parser.parse_resources_from_stream(out.decode("utf-8").splitlines(), resources)
        log.minor_success(log.path_style(str(imported_file.path)), "imported")
    minor_version_info = pcs.vcs().get_minor_version_info(minor_version)
    _import_perf_profile(
        profiles, prof_stats, resources, minor_version_info, with_sudo=with_sudo, **kwargs
    )


@vcs_kit.lookup_minor_version
def import_perf_from_script(
    import_entries: list[str],
    stats_headers: str | None,
    minor_version: str,
    **kwargs: Any,
) -> None:
    """Imports profiles collected by `perf record | perf script` command.

    First, the function parses all the perf import entries and stats headers, and then it runs
    the parser script for each entry to generate the profile.

    :param import_entries: a collection of import entries (profiles or CSV files).
    :param stats_headers: CLI-specified stats headers.
    :param minor_version: minor version corresponding to the imported profiles.
    :param kwargs: rest of the parameters.
    """
    # TODO: can be optimized a lot.
    parse_script = script_kit.get_script("stackcollapse-perf.pl")
    import_dir = Path(config.lookup_key_recursively("import.dir", os.getcwd()))
    profiles, prof_stats = imports.parse_import_entries(import_entries, import_dir, stats_headers)
    resources: list[dict[str, str | int]] = []

    for imported_file in profiles:
        perf_script_command = f"cat {imported_file.path} | {parse_script}"
        out, _ = external_commands.run_safely_external_command(perf_script_command)
        log.minor_success(f"Raw data from {log.path_style(str(imported_file.path))}", "collected")
        parser.parse_resources_from_stream(out.decode("utf-8").splitlines(), resources)
        log.minor_success(log.path_style(str(imported_file.path)), "imported")
    minor_version_info = pcs.vcs().get_minor_version_info(minor_version)
    _import_perf_profile(profiles, prof_stats, resources, minor_version_info, **kwargs)


@vcs_kit.lookup_minor_version
def import_perf_from_stack(
    import_entries: list[str],
    stats_headers: str | None,
    minor_version: str,
    **kwargs: Any,
) -> None:
    """Imports profiles collected by `perf record | perf script | stackcollapse-perf.pl` command.

    First, the function parses all the perf import entries and stats headers, and then it parses
    each entry to generate the profile.

    :param import_entries: a collection of import entries (profiles or CSV files).
    :param stats_headers: CLI-specified stats headers.
    :param minor_version: minor version corresponding to the imported profiles.
    :param kwargs: rest of the parameters.
    """
    import_dir = Path(config.lookup_key_recursively("import.dir", os.getcwd()))
    profiles, prof_stats = imports.parse_import_entries(import_entries, import_dir, stats_headers)
    resources: list[dict[str, str | int]] = []

    for imported_profile in profiles:
        with streams.open_folded_profile(imported_profile.path) as folded_stream:
            parser.parse_resources_from_stream(folded_stream, resources)
        log.minor_success(log.path_style(str(imported_profile.path)), "imported")
    minor_version_info = pcs.vcs().get_minor_version_info(minor_version)
    _import_perf_profile(profiles, prof_stats, resources, minor_version_info, **kwargs)


def _import_perf_profile(
    profiles: list[imports.ImportProfileSpec],
    prof_stats: list[stats.ProfileStat],
    resources: list[dict[str, Any]],
    minor_version: MinorVersion,
    **kwargs: Any,
) -> None:
    """Constructs the profile for perf-collected data and saves them to jobs or index.

    :param profiles: a collection of specifications of the profiles that are being imported.
    :param prof_stats: a collection of stats that should be associated with the profile.
    :param resources: a collection of parsed resources.
    :param minor_version: minor version corresponding to the imported profiles.
    :param kwargs: rest of the parameters.
    """
    import_dir = Path(config.lookup_key_recursively("import.dir", os.getcwd()))
    prof = profile.Profile(
        {
            "global": {
                "time": "???",
                "resources": resources,
            },
            "origin": minor_version.checksum,
            "machine": imports.parse_machine_info(kwargs.get("machine_info", ""), import_dir),
            "metadata": [
                asdict(data)
                for data in imports.parse_metadata(kwargs.get("metadata", tuple()), import_dir)
            ],
            "stats": [asdict(stat) for stat in prof_stats],
            "header": {
                "type": "time",
                "cmd": kwargs.get("cmd", ""),
                "exitcode": [p.exit_code for p in profiles],
                "workload": kwargs.get("workload", ""),
                "label": kwargs.get("profile_label", ""),
                "units": {"time": "sample"},
            },
            "collector_info": {
                "name": "kperf",
                "params": {
                    "with_sudo": kwargs.get("with_sudo", False),
                    "warmup": kwargs.get("warmup", 0),
                    "repeat": len(profiles),
                },
            },
            "postprocessors": [],
        }
    )
    profile.save_profile(prof, kwargs.get("profile_path"), minor_version)
