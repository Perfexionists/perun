"""Functions for importing ELK profiles."""

from __future__ import annotations

# Standard Imports
from collections import defaultdict
from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

# Third-Party Imports

# Perun Imports
from perun.logic import config, pcs
from perun.profiles import imports, native as profile, structs
from perun.utils import log, streams
from perun.utils.common import common_kit
from perun.utils.structs import common_structs
from perun.vcs import vcs_kit


@vcs_kit.lookup_minor_version
def import_elk_from_json(
    import_entries: list[str],
    metadata: tuple[str, ...],
    minor_version: str,
    **kwargs: Any,
) -> None:
    """Imports the ELK stored data from JSON data.

    The loading expects the JSON files to be in form of `{'queries': []}`.

    :param import_entries: list of filenames with elk data.
    :param metadata: CLI-supplied additional metadata. Metadata specified in JSON take precedence.
    :param minor_version: minor version corresponding to the imported profiles.
    :param kwargs: rest of the parameters.
    """
    import_dir = Path(config.lookup_key_recursively("import.dir", Path.cwd()))
    resources: list[dict[str, Any]] = []
    # Load the CLI-supplied metadata, if any
    elk_metadata: dict[str, structs.ProfileMetadataEntry] = {
        data.name: data for data in imports.parse_metadata(metadata, import_dir)
    }

    for elk_file in import_entries:
        elk_file_path = imports.massage_import_path(elk_file, import_dir)
        with streams.safely_open_and_log(elk_file_path, "r", fatal_fail=True) as elk_handle:
            imported_json = json.load(elk_handle)
            assert (
                "queries" in imported_json.keys()
            ), "expected the JSON to contain list of dictionaries in 'queries' key"
            r, m = _extract_from_elk(imported_json["queries"])
        resources.extend(r)
        # Possibly overwrite CLI-supplied metadata when identical keys are found
        elk_metadata.update(m)
        log.minor_success(log.path_style(str(elk_file_path)), "imported")
    minor_version_info = pcs.vcs().get_minor_version_info(minor_version)
    _import_elk_profile(resources, elk_metadata, minor_version_info, **kwargs)


def _import_elk_profile(
    resources: list[dict[str, Any]],
    metadata: dict[str, structs.ProfileMetadataEntry],
    minor_version: common_structs.MinorVersion,
    **kwargs: Any,
) -> None:
    """Constructs the profile for elk-stored data and saves them to jobs or index.

    :param resources: list of parsed resources.
    :param metadata: parts of the profiles that will be stored as metadata in the profile.
    :param minor_version: minor version corresponding to the imported profiles.
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
            "machine": _extract_machine_info_from_elk_metadata(metadata),
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
    profile.save_profile(prof, kwargs.get("profile_path"), minor_version)


def _extract_from_elk(
    elk_query: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, structs.ProfileMetadataEntry]]:
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

    metadata = {k: structs.ProfileMetadataEntry(k, res_counter[k].pop()) for k in metadata_keys}
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


def _extract_machine_info_from_elk_metadata(
    metadata: dict[str, structs.ProfileMetadataEntry],
) -> dict[str, Any]:
    """Extracts the parts of the profile that correspond to machine info.

    Note that not many is collected from the ELK formats, and it can vary greatly,
    hence, most of the machine specification and environment should be in metadata instead.

    :param metadata: metadata extracted from the ELK profiles.

    :return: machine info extracted from the profiles.
    """
    machine_info: dict[str, Any] = {
        "architecture": metadata.get("machine.arch", structs.ProfileMetadataEntry("", "?")).value,
        "system": str(
            metadata.get("machine.os", structs.ProfileMetadataEntry("", "?")).value
        ).capitalize(),
        "release": metadata.get(
            "extra.machine.platform", structs.ProfileMetadataEntry("", "?")
        ).value,
        "host": metadata.get("machine.hostname", structs.ProfileMetadataEntry("", "?")).value,
        "cpu": {
            "physical": "?",
            "total": metadata.get("machine.cpu-cores", structs.ProfileMetadataEntry("", "?")).value,
            "frequency": "?",
        },
        "memory": {
            "total_ram": metadata.get("machine.ram", structs.ProfileMetadataEntry("", "?")).value,
            "swap": "?",
        },
        "boot_info": "?",
        "mem_details": {},
        "cpu_details": [],
    }
    return machine_info
