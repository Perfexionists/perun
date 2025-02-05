"""Functions for importing Profile from different formats"""

from __future__ import annotations

# Standard Imports
from collections import defaultdict
import csv
from dataclasses import asdict, dataclass
import gzip
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

# Third-Party Imports

# Perun Imports
from perun import profile as profile
from perun.collect.kperf import parser
from perun.logic import commands, config, index, pcs
from perun.utils import log, streams
from perun.utils.common import script_kit, common_kit
from perun.utils.external import commands as external_commands, environment
from perun.utils.structs.common_structs import MinorVersion
from perun.vcs import vcs_kit


@dataclass
class _PerfProfileSpec:
    """A representation of a perf profile record to import.

    :ivar path: the absolute path to the perf
    :ivar exit_code: the exit code of the profile collection process.
    """

    path: Path
    exit_code: int = 0


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
    if sys.platform == "darwin":
        log.error("Import from perf record is not supported on macOS platform.")
    parse_script = script_kit.get_script("stackcollapse-perf.pl")
    profiles, stats = _parse_perf_import_entries(import_entries, stats_headers)
    resources = []

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
        resources.extend(parser.parse_events(out.decode("utf-8").split("\n")))
        log.minor_success(log.path_style(str(imported_file.path)), "imported")
    minor_version_info = pcs.vcs().get_minor_version_info(minor_version)
    import_perf_profile(
        profiles, stats, resources, minor_version_info, with_sudo=with_sudo, **kwargs
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
    parse_script = script_kit.get_script("stackcollapse-perf.pl")
    profiles, stats = _parse_perf_import_entries(import_entries, stats_headers)
    resources = []

    for imported_file in profiles:
        perf_script_command = f"cat {imported_file.path} | {parse_script}"
        out, _ = external_commands.run_safely_external_command(perf_script_command)
        log.minor_success(f"Raw data from {log.path_style(str(imported_file.path))}", "collected")
        resources.extend(parser.parse_events(out.decode("utf-8").split("\n")))
        log.minor_success(log.path_style(str(imported_file.path)), "imported")
    minor_version_info = pcs.vcs().get_minor_version_info(minor_version)
    import_perf_profile(profiles, stats, resources, minor_version_info, **kwargs)


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
    profiles, stats = _parse_perf_import_entries(import_entries, stats_headers)
    resources = []

    for imported_profile in profiles:
        out = load_perf_file(imported_profile.path)
        resources.extend(parser.parse_events(out.split("\n")))
        log.minor_success(log.path_style(str(imported_profile.path)), "imported")
    minor_version_info = pcs.vcs().get_minor_version_info(minor_version)
    import_perf_profile(profiles, stats, resources, minor_version_info, **kwargs)


@vcs_kit.lookup_minor_version
def import_elk_from_json(
    import_entries: list[str],
    metadata: tuple[str, ...],
    minor_version: str,
    **kwargs: Any,
) -> None:
    """Imports the ELK stored data from the json data.

    The loading expects the json files to be in form of `{'queries': []}`.

    :param import_entries: list of filenames with elk data.
    :param metadata: CLI-supplied additional metadata. Metadata specified in JSON take precedence.
    :param minor_version: minor version corresponding to the imported profiles.
    :param kwargs: rest of the parameters.
    """
    import_dir = Path(config.lookup_key_recursively("import.dir", os.getcwd()))
    resources: list[dict[str, Any]] = []
    # Load the CLI-supplied metadata, if any
    elk_metadata: dict[str, profile.ProfileHeaderEntry] = {
        data.name: data for data in _import_metadata(metadata, import_dir)
    }

    for elk_file in import_entries:
        elk_file_path = _massage_import_path(elk_file, import_dir)
        with streams.safely_open_and_log(elk_file_path, "r", fatal_fail=True) as elk_handle:
            imported_json = json.load(elk_handle)
            assert (
                "queries" in imported_json.keys()
            ), "expected the JSON to contain list of dictionaries in 'queries' key"
            r, m = extract_from_elk(imported_json["queries"])
        resources.extend(r)
        # Possibly overwrite CLI-supplied metadata when identical keys are found
        elk_metadata.update(m)
        log.minor_success(log.path_style(str(elk_file_path)), "imported")
    minor_version_info = pcs.vcs().get_minor_version_info(minor_version)
    import_elk_profile(resources, elk_metadata, minor_version_info, **kwargs)


def import_perf_profile(
    profiles: list[_PerfProfileSpec],
    stats: list[profile.ProfileStat],
    resources: list[dict[str, Any]],
    minor_version: MinorVersion,
    **kwargs: Any,
) -> None:
    """Constructs the profile for perf-collected data and saves them to jobs or index.

    :param profiles: a collection of specifications of the profiles that are being imported.
    :param stats: a collection of profiles statistics that should be associated with the profile.
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
            "machine": get_machine_info(kwargs.get("machine_info", ""), import_dir),
            "metadata": [
                asdict(data)
                for data in _import_metadata(kwargs.get("metadata", tuple()), import_dir)
            ],
            "stats": [asdict(stat) for stat in stats],
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
    save_imported_profile(
        prof, kwargs.get("save_to_index", False), minor_version, kwargs.get("profile_name")
    )


def import_elk_profile(
    resources: list[dict[str, Any]],
    metadata: dict[str, profile.ProfileHeaderEntry],
    minor_version: MinorVersion,
    save_to_index: bool = False,
    **kwargs: Any,
) -> None:
    """Constructs the profile for elk-stored data and saves them to jobs or index.

    :param resources: list of parsed resources.
    :param metadata: parts of the profiles that will be stored as metadata in the profile.
    :param minor_version: minor version corresponding to the imported profiles.
    :param save_to_index: indication whether we should save the imported profiles to index.
    :param kwargs: rest of the parameters.
    """
    prof = profile.Profile(
        {
            "global": {
                "time": "???",
                "resources": resources,
            },
            "origin": minor_version.checksum,
            "metadata": [asdict(data) for data in metadata.values()],
            "machine": extract_machine_info_from_elk_metadata(metadata),
            "header": {
                "type": "time",
                "cmd": kwargs.get("cmd", ""),
                "exitcode": "?",
                "workload": kwargs.get("workload", ""),
                "label": kwargs.get("profile_label", ""),
                "units": {"time": "sample"},
            },
            "collector_info": {
                "name": "???",
                "params": {},
            },
            "postprocessors": [],
        }
    )
    save_imported_profile(prof, save_to_index, minor_version, kwargs.get("profile_name"))


def save_imported_profile(
    prof: profile.Profile,
    save_to_index: bool,
    minor_version: MinorVersion,
    profile_name: str | None = None,
) -> None:
    """Saves the imported profile either to index or to pending jobs.

    :param prof: imported profile
    :param minor_version: minor version corresponding to the imported profiles.
    :param save_to_index: indication whether we should save the imported profiles to index.
    :param profile_name: optional custom name of the saved profile
    """
    if not profile_name:
        # No custom profile name provided, generate the name
        profile_name = profile.generate_profile_name(prof)
    elif not profile_name.endswith(".perf"):
        # Make sure the profile name ends with the proper suffix
        profile_name += ".perf"
    profile_directory = pcs.get_job_directory()
    full_profile_path = os.path.join(profile_directory, profile_name)

    streams.store_json(prof.serialize(), full_profile_path)
    log.minor_status(
        "stored generated profile ",
        status=f"{log.path_style(os.path.relpath(full_profile_path))}",
    )
    if save_to_index:
        commands.add([full_profile_path], minor_version.checksum, keep_profile=False)
    else:
        # Else we register the profile in pending index
        index.register_in_pending_index(full_profile_path, prof)


def load_perf_file(filepath: Path) -> str:
    """Tests if the file is packed by gzip and unpacks it, otherwise reads it as a text file.

    :param filepath: path to the perf file.

    :return: the content of the file.
    """
    if filepath.suffix.lower() == ".gz":
        with streams.safely_open_and_log(filepath, "rb", fatal_fail=True) as gz_handle:
            header = gz_handle.read(2)
            gz_handle.seek(0)
            assert header == b"\x1f\x8b"
            with gzip.GzipFile(fileobj=gz_handle) as gz:
                return gz.read().decode("utf-8")
    with streams.safely_open_and_log(
        filepath, "r", fatal_fail=True, encoding="utf-8"
    ) as txt_handle:
        return txt_handle.read()


def extract_from_elk(
    elk_query: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, profile.ProfileHeaderEntry]]:
    """For the given elk query, extracts resources and metadata.

    For metadata, we consider any key that has only single value through the profile,
    and is not linked to keywords `metric` or `benchmarking`.
    For resources, we consider anything that is not identified as metadata.

    :param elk_query: query from the elk in form of list of resource.

    :return: list of resources and metadata.
    """
    res_counter = defaultdict(set)
    for res in elk_query:
        for key, val in res.items():
            res_counter[key].add(val)
    metadata_keys = {
        k
        for (k, v) in res_counter.items()
        if not k.startswith("metric") and not k.startswith("benchmarking") and len(v) == 1
    }

    metadata = {k: profile.ProfileHeaderEntry(k, res_counter[k].pop()) for k in metadata_keys}
    resources = [
        {
            k: common_kit.try_convert(v, [int, float, str])
            for k, v in res.items()
            if k not in metadata_keys
        }
        for res in elk_query
    ]
    # We register uid
    for res in resources:
        res["uid"] = res["metric.name"]
        res["benchmarking.time"] = res["benchmarking.end-ts"] - res["benchmarking.start-ts"]
        res.pop("benchmarking.end-ts")
        res.pop("benchmarking.start-ts")
    return resources, metadata


def get_machine_info(machine_info: str, import_dir: Path) -> dict[str, Any]:
    """Returns machine info either from an input file or constructs it from the environment.

    :param machine_info: relative or absolute path to machine specification JSON file. In case of
           an empty string, the machine info will be constructed from the environment.
    :param import_dir: import directory where to look for the machine info file if the provided
           path is relative.

    :return: parsed or constructed machine specification.
    """
    if machine_info:
        # Some machine info path has been provided.
        info_path = _massage_import_path(machine_info, import_dir)
        with streams.safely_open_and_log(
            info_path, "r", fail_msg="not found, generating info from environment instead"
        ) as info_handle:
            if info_handle is not None:
                json_data = json.load(info_handle)
                log.minor_success(log.path_style(str(info_path)), "parsed")
                return json_data
    # No machine info file might have been provided, or an invalid path was specified.
    # Construct the machine info from the current machine.
    return environment.get_machine_specification()


def extract_machine_info_from_elk_metadata(
    metadata: dict[str, profile.ProfileHeaderEntry],
) -> dict[str, Any]:
    """Extracts the parts of the profile that correspond to machine info.

    Note that not many is collected from the ELK formats, and it can vary greatly,
    hence, most of the machine specification and environment should be in metadata instead.

    :param metadata: metadata extracted from the ELK profiles.

    :return: machine info extracted from the profiles.
    """
    machine_info: dict[str, Any] = {
        "architecture": metadata.get("machine.arch", profile.ProfileHeaderEntry("", "?")).value,
        "system": str(
            metadata.get("machine.os", profile.ProfileHeaderEntry("", "?")).value
        ).capitalize(),
        "release": metadata.get(
            "extra.machine.platform", profile.ProfileHeaderEntry("", "?")
        ).value,
        "host": metadata.get("machine.hostname", profile.ProfileHeaderEntry("", "?")).value,
        "cpu": {
            "physical": "?",
            "total": metadata.get("machine.cpu-cores", profile.ProfileHeaderEntry("", "?")).value,
            "frequency": "?",
        },
        "memory": {
            "total_ram": metadata.get("machine.ram", profile.ProfileHeaderEntry("", "?")).value,
            "swap": "?",
        },
        "boot_info": "?",
        "mem_details": {},
        "cpu_details": [],
    }

    return machine_info


def _import_metadata(
    metadata: tuple[str, ...], import_dir: Path
) -> list[profile.ProfileHeaderEntry]:
    """Parse the metadata entries from CLI and convert them to our internal representation.

    :param import_dir: the import directory to use for relative metadata file paths.
    :param metadata: a collection of metadata entries or JSON files.

    :return: a collection of parsed and converted metadata objects
    """
    p_metadata: list[profile.ProfileHeaderEntry] = []
    # Normalize the metadata string for parsing and/or opening the file
    for metadata_str in map(str.strip, metadata):
        if metadata_str.lower().endswith(".json"):
            # Update the metadata collection with entries from the json file
            p_metadata.extend(_parse_metadata_json(_massage_import_path(metadata_str, import_dir)))
        else:
            # Add a single metadata entry parsed from its string representation
            try:
                p_metadata.append(profile.ProfileHeaderEntry.from_string(metadata_str))
            except TypeError:
                log.warn(f"Ignoring invalid profile metadata string '{metadata_str}'.")
    return p_metadata


def _parse_metadata_json(metadata_path: Path) -> list[profile.ProfileHeaderEntry]:
    """Parse a metadata JSON file into the metadata objects.

    If the JSON file contains nested dictionaries, the hierarchical keys will be flattened.

    :param metadata_path: the path to the metadata JSON.

    :return: a collection of parsed metadata objects.
    """
    with streams.safely_open_and_log(
        metadata_path, "r", fail_msg="not found, skipping"
    ) as metadata_handle:
        if metadata_handle is None:
            return []
        # Make sure we flatten the input
        metadata_list = [
            profile.ProfileHeaderEntry(k, v)
            for k, v in profile.all_items_of(json.load(metadata_handle))
        ]
        log.minor_success(log.path_style(str(metadata_path)), "parsed")
        return metadata_list


def _parse_perf_import_entries(
    import_entries: list[str], cli_stats_headers: str | None
) -> tuple[list[_PerfProfileSpec], list[profile.ProfileStat]]:
    """Parses perf import entries and stats.

    An import entry is either a profile entry

      'profile_path[,<exit code>[,<stat value>]+]'

    where each stat value corresponds to a stats header specified in the cli_stats_headers, or
    a CSV file entry

      'file_path.csv'

    where the CSV file is in the format

      #Profile,Exit_code[,stat-header1]+
      profile_path[,<exit code>[,<stat value>]+]
      ...

    that combines the --stats-headers option and profile entries. Stats specified in a CSV file
    apply only to profile entries in the JSON file. Similarly, CLI-specified stats apply only to
    profile entries specified directly in CLI.

    :param import_entries: the perf import entries to parse.
    :param cli_stats_headers: the stats headers specified in CLI.

    :return: parsed profiles and stats.
    """
    stats = []
    if cli_stats_headers is not None:
        stats = [
            profile.ProfileStat.from_string(*stat.split("|"))
            for stat in cli_stats_headers.split(",")
        ]
    cli_stats_len = len(stats)

    import_dir = Path(config.lookup_key_recursively("import.dir", os.getcwd()))
    profiles: list[_PerfProfileSpec] = []

    for record in import_entries:
        if record.strip().lower().endswith(".csv"):
            # The input is a csv file
            _parse_perf_import_csv(record, import_dir, profiles, stats)
        elif (
            profile_spec := _parse_perf_entry(record.split(","), import_dir, stats[:cli_stats_len])
        ) is not None:
            # The input is a string profile spec
            profiles.append(profile_spec)
    return profiles, stats


def _parse_perf_import_csv(
    csv_file: str,
    import_dir: Path,
    profiles: list[_PerfProfileSpec],
    stats: list[profile.ProfileStat],
) -> None:
    """Parse stats headers and perf import entries in a CSV file.

    :param csv_file: the CSV file to parse.
    :param import_dir: the import directory to use for relative profile file paths.
    :param profiles: profile specifications that will be extended with the parsed profiles.
    :param stats: profile stats that will be merged with the CSV stats.
    """
    csv_path = _massage_import_path(csv_file, import_dir)
    with streams.safely_open_and_log(csv_path, "r", fatal_fail=True) as csvfile:
        csv_reader = csv.reader(csvfile, delimiter=",")
        try:
            header: list[str] = next(csv_reader)
        except StopIteration:
            # Empty CSV file, skip
            log.warn(f"Empty import file {csv_path}. Skipping.")
            return
        # Parse the stats headers
        csv_stats: list[profile.ProfileStat] = [
            profile.ProfileStat.from_string(*stat_definition.split("|"))
            for stat_definition in header[2:]
        ]
        # Parse the remaining rows that represent profile specifications and filter invalid ones
        profiles.extend(
            record
            for row in csv_reader
            if (record := _parse_perf_entry(row, import_dir, csv_stats)) is not None
        )
        # Merge CSV stats with the other stats
        for csv_stat in csv_stats:
            _merge_stats(csv_stat, stats)
        log.minor_success(log.path_style(str(csv_path)), "parsed")


def _parse_perf_entry(
    entry: list[str], import_dir: Path, stats: list[profile.ProfileStat]
) -> _PerfProfileSpec | None:
    """Parse a single perf profile import entry.

    :param entry: the perf import entry to parse.
    :param import_dir: the import directory to use for relative profile file paths.
    :param stats: the profile stats associated with this profile.

    :return: the parsed profile, or None if the import entry is invalid.
    """
    if len(entry) == 0 or not entry[0]:
        # Empty profile specification, warn
        log.warn("Empty import profile specification. Skipping.")
        return None
    # Parse the profile specification
    profile_info = _PerfProfileSpec(
        _massage_import_path(entry[0], import_dir),
        int(entry[1].strip()) if len(entry) >= 2 else _PerfProfileSpec.exit_code,
    )
    # Parse the stat values and add them to respective stats
    for stat_value, stat_obj in zip(map(_massage_stat_value, entry[2:]), stats):
        stat_obj.value.append(stat_value)
    if len(entry[2:]) > len(stats):
        log.warn(
            f"Imported profile {profile_info.path} specifies more stats values than stats headers."
            " Ignoring additional stats."
        )
    if profile_info.exit_code != 0:
        log.warn("Importing a profile with non-zero exit code.")
    return profile_info


def _merge_stats(new_stat: profile.ProfileStat, into_stats: list[profile.ProfileStat]) -> None:
    """Merge a new profile stat values into the current profile stats.

    If an existing stat with the same name exists, the values of both stats are merged. If no such
    stat is found, the new stat is added to the collection of current stats.

    :param new_stat: the new profile stat to merge.
    :param into_stats: the current collection of profile stats.
    """
    for stat in into_stats:
        if new_stat.name == stat.name:
            # We found a stat with a matching name, merge
            stat.merge_with(new_stat)
            return
    # There is no stat to merge with, extend the current collection of stats
    into_stats.append(new_stat)


def _massage_stat_value(stat_value: str) -> str | float:
    """Massages a stat value read from a string to check whether it is numerical or not.

    :param stat_value: the stat value to massage.

    :return: a massaged stat value.
    """
    stat_value = stat_value.strip()
    try:
        return float(stat_value)
    except ValueError:
        return stat_value


def _massage_import_path(path_str: str, import_dir: Path) -> Path:
    """Massages path strings into a unified path format.

    First, the path string is stripped of leading and trailing whitespaces.
    Next, absolute paths are kept as is, while relative paths are prepended with the
    provided import directory.

    :param import_dir: the import directory to use for relative paths.
    :param path_str: the path string to massage.

    :return: the massaged path.
    """
    path: Path = Path(path_str.strip())
    if path.is_absolute():
        return path
    return import_dir / path
