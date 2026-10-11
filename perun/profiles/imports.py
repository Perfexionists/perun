"""Structures and helper functions for importing profiles."""

from __future__ import annotations

# Standard Imports
import dataclasses
import json
from pathlib import Path
from typing import Any, Sequence

# Third-Party Imports
import polars as pl  # Used for advanced CSV parsing compared to the stdlib csv.

# Perun Imports
from perun.profiles import stats, structs
from perun.profiles.native import query
from perun.utils import log, streams
from perun.utils.common import common_kit
from perun.utils.external import environment


@dataclasses.dataclass
class ImportProfileSpec:
    """A representation of a profile record to import.

    :ivar path: an absolute path to the profile.
    :ivar exit_code: the exit code of the profile collection process.
    """

    path: Path
    exit_code: str = "?"


def parse_metadata(
    metadata: tuple[str, ...], import_dir: Path
) -> list[structs.ProfileMetadataEntry]:
    """Parse metadata entries from CLI and convert them to our internal representation.

    :param import_dir: the import directory to use for relative metadata file paths.
    :param metadata: a collection of metadata entries or JSON files.

    :return: a collection of parsed and converted metadata objects.
    """
    p_metadata: list[structs.ProfileMetadataEntry] = []
    # Normalize the metadata string for parsing and/or opening the file
    for metadata_str in map(str.strip, metadata):
        if metadata_str.lower().endswith(".json"):
            # Update the metadata collection with entries from the json file
            p_metadata.extend(_parse_metadata_json(massage_import_path(metadata_str, import_dir)))
        else:
            # Add a single metadata entry parsed from its string representation
            try:
                p_metadata.append(structs.ProfileMetadataEntry.from_string(metadata_str))
            except TypeError:
                log.warn(f"Ignoring invalid profile metadata string '{metadata_str}'.")
    return p_metadata


def parse_machine_info(machine_info: str, import_dir: Path) -> dict[str, Any]:
    """Returns machine info either from an input file or constructs it from the environment.

    :param machine_info: relative or absolute path to machine specification JSON file. In case of
           an empty string, the machine info will be constructed from the environment.
    :param import_dir: import directory where to look for the machine info file if the provided
           path is relative.

    :return: parsed or constructed machine specification.
    """
    if machine_info:
        # Some machine info path has been provided.
        info_path = massage_import_path(machine_info, import_dir)
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


def massage_import_path(path_str: str, import_dir: Path) -> Path:
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


def parse_import_entries(
    import_entries: list[str], import_dir: Path, cli_stats_headers: str | None
) -> tuple[list[ImportProfileSpec], list[stats.ProfileStat]]:
    """Parses import entries and stats.

    An import entry is either a profile entry

      'profile_path[,<exit code>[,<stat value>]+]'

    where each stat value corresponds to a stats header specified in the cli_stats_headers, or
    a CSV file entry

      'file_path.csv'

    where the CSV file is in the format

      Profile,Exit_code[,stat-header1]+
      profile_path[,<exit code>[,<stat value>]+]
      ...

    that combines the --stats-headers option and profile entries. Stats specified in a CSV file
    apply only to profile entries in the JSON file. Similarly, CLI-specified stats apply only to
    profile entries specified directly in CLI.

    :param import_entries: the import entries to parse.
    :param import_dir: the import directory to use for relative profile paths.
    :param cli_stats_headers: the stats headers specified in CLI.

    :return: parsed profiles and stats.
    """
    prof_stats = []
    if cli_stats_headers is not None:
        prof_stats = [
            stats.ProfileStat.from_string(*stat.split("|")) for stat in cli_stats_headers.split(",")
        ]
    cli_stats_len = len(prof_stats)
    profiles: list[ImportProfileSpec] = []

    for record in import_entries:
        if record.strip().lower().endswith(".csv"):
            # The input is a csv file
            _parse_import_csv(record, import_dir, profiles, prof_stats)
        elif (
            profile_spec := _parse_import_entry(
                record.split(","), import_dir, prof_stats[:cli_stats_len]
            )
        ) is not None:
            # The input is a string profile spec
            profiles.append(profile_spec)
    return profiles, prof_stats


def _parse_metadata_json(metadata_path: Path) -> list[structs.ProfileMetadataEntry]:
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
            structs.ProfileMetadataEntry(k, v)
            for k, v in query.all_items_of(json.load(metadata_handle))
        ]
        log.minor_success(log.path_style(str(metadata_path)), "parsed")
        return metadata_list


def _parse_import_csv(
    csv_file: str,
    import_dir: Path,
    profiles: list[ImportProfileSpec],
    prof_stats: list[stats.ProfileStat],
) -> None:
    """Parse stats headers and import entries in a CSV file.

    :param csv_file: the CSV file to parse.
    :param import_dir: the import directory to use for relative profile file paths.
    :param profiles: profile specifications that will be extended with the parsed profiles.
    :param prof_stats: profile stats that will be merged with the CSV stats.
    """
    csv_path = massage_import_path(csv_file, import_dir)
    with streams.safely_open_and_log(csv_path, "r", fatal_fail=True) as csvfile_handle:
        try:
            import_csv = pl.read_csv(csvfile_handle, comment_prefix="#")
        except pl.exceptions.NoDataError:
            # Empty CSV file, skip
            log.warn(f"Empty file {csv_path}. Skipping.")
            return
        except pl.exceptions.ComputeError as e:
            # The CSV file contains spurious columns, or is otherwise weirdly formatted.
            # We log the issue so the user is aware of it, and we retry parsing it less strictly.
            log.warn(
                f"Encountered error when processing {csv_path}: {str(e).splitlines()[0]}."
                " Attempting recovery."
            )
            import_csv = pl.read_csv(csvfile_handle, comment_prefix="#", truncate_ragged_lines=True)
        # Parse the stats headers
        csv_stats: list[stats.ProfileStat] = [
            stats.ProfileStat.from_string(*stat_definition.split("|"))
            for stat_definition in import_csv.columns[2:]
        ]
        # Parse the remaining rows that represent profile specifications and filter invalid ones
        profiles.extend(
            record
            for row in import_csv.iter_rows()
            if (record := _parse_import_entry(row, import_dir, csv_stats)) is not None
        )
        # Merge CSV stats with the other stats
        for csv_stat in csv_stats:
            stats.merge_stats(csv_stat, prof_stats)
        log.minor_success(log.path_style(str(csv_path)), "parsed")


def _parse_import_entry(
    entry: Sequence[str | float], import_dir: Path, prof_stats: list[stats.ProfileStat]
) -> ImportProfileSpec | None:
    """Parse a single profile import entry.

    :param entry: the import entry to parse.
    :param import_dir: the import directory to use for relative profile file paths.
    :param prof_stats: the profile stats associated with this profile.

    :return: the parsed profile, or None if the import entry is invalid.
    """
    # Attempt to parse the profile specification.
    if len(entry) == 0 or entry[0] is None or str(entry[0]).strip() == "":
        # Empty profile specification, warn and skip.
        log.warn("Empty profile specification. Skipping.")
        return None
    profile_path = massage_import_path(str(entry[0]), import_dir)
    # Attempt to parse the exit code, if provided.
    exit_code = ImportProfileSpec.exit_code
    try:
        exit_code = str(entry[1])
    except (IndexError, TypeError):
        # No exit code was provided. Either there is no value, or the value is None.
        log.warn(
            f"No exit code provided for profile '{profile_path}', using the default code "
            f"'{exit_code}'."
        )
    if exit_code != "0":
        log.warn("Loading a profile with non-zero exit code.")
    profile_info = ImportProfileSpec(profile_path, exit_code)

    # Parse the stat values and add them to respective stats
    for stat_value, stat_obj in zip(entry[2:], prof_stats):
        # Filter out missing values; supported values are floats and strings.
        if stat_value:
            stat_obj.value.append(common_kit.try_convert(stat_value, (float, str)))
    return profile_info
