"""Set of helper functions for working with perun.diff_view"""

from __future__ import annotations

# Standard Imports
import dataclasses
import difflib
import os
from typing import Any, Optional, Iterable, Literal, cast, Union

# Third-Party Imports

# Perun Imports
from perun.logic import config
from perun.profile import helpers
from perun.profile.factory import Profile
from perun.profile import stats as pstats
from perun.utils import log
from perun.utils.common import common_kit
from perun.utils.common.common_kit import ColorVariableType
from perun.utils.structs.diff_structs import HeaderDisplayStyle


def save_diff_view(
    output_file: Optional[str],
    content: str,
    output_type: str,
    lhs_profile: Profile,
    rhs_profile: Profile,
) -> str:
    """Saves the content to the output file; if no output file is stated, then it is automatically
    generated.

    :param output_file: file, where the content will be stored
    :param content: content of the output file
    :param output_type: type of the output
    :param lhs_profile: baseline profile
    :param rhs_profile: target profile
    :return: name of the output file
    """
    if output_file is None:
        lhs_name = os.path.splitext(helpers.generate_profile_name(lhs_profile))[0]
        rhs_name = os.path.splitext(helpers.generate_profile_name(rhs_profile))[0]
        output_file = f"{output_type}-diff-of-{lhs_name}-and-{rhs_name}" + ".html"

    if not output_file.endswith("html"):
        output_file += ".html"

    with open(output_file, "w", encoding="utf-8") as template_out:
        template_out.write(content)

    return output_file


def get_candidate_keys(candidate_keys: Iterable[str]) -> list[str]:
    """Returns list of candidate keys

    :param candidate_keys: list of candidate keys
    :return: list of supported keys
    """
    allowed_keys = [
        "Total Exclusive T [ms]",
        "Total Inclusive T [ms]",
        "amount",
        "ncalls",
        # "E Min",
        # "E Max",
        # "I Min",
        # "I Max",
        # "Callees Mean [#]",
        # "Callees [#]",
        # "Total Inclusive T [%]",
        # "Total Exclusive T [%]",
        # "I Mean",
        # "E Mean",
    ]
    return sorted([candidate for candidate in candidate_keys if candidate in allowed_keys])


def generate_vulnerabilities(profile: Profile) -> list[helpers.ProfileHeaderEntry]:
    """Generates vulnerabilities from the given profile

    :param profile: profile for which we are generating the specification
    :return: vulnerabilities as an entry
    """
    machine_info = profile.get("machine", {})
    return [
        helpers.ProfileHeaderEntry(
            "vulnerabilities",
            "?" if "cpu_vulnerabilities" not in machine_info else "",
            "CPU vulnerabilities summary.",
            machine_info.get("cpu_vulnerabilities", {}),
        )
    ]


def generate_specification(profile: Profile) -> list[helpers.ProfileHeaderEntry]:
    """Generates profile specification from the given profile

    :param profile: profile for which we are generating the specification

    :return: the profile specification as a list of entries
    """
    command = " ".join([profile["header"]["cmd"], profile["header"]["workload"]]).strip()
    exitcode = _format_exit_codes(profile["header"].get("exitcode", "?"))
    machine_info = profile.get("machine", {})
    return [
        helpers.ProfileHeaderEntry(
            "origin",
            profile.get("origin", "?"),
            "The version control version, for which the profile was measured.",
        ),
        helpers.ProfileHeaderEntry(
            "profile label",
            profile["header"].get("label", ""),
            "A label associated with this profile, if any.",
        ),
        helpers.ProfileHeaderEntry(
            "command", command, "The workload / command, for which the profile was measured."
        ),
        helpers.ProfileHeaderEntry(
            "exitcode", exitcode, "The exit code that was returned by the underlying command."
        ),
        helpers.ProfileHeaderEntry(
            "collector command",
            log.collector_to_command(profile.get("collector_info", {})),
            "The collector / profiler, which collected the data.",
        ),
        helpers.ProfileHeaderEntry(
            "kernel",
            machine_info.get("release", "?"),
            "The underlying kernel version, where the results were measured.",
        ),
        helpers.ProfileHeaderEntry(
            "boot info",
            machine_info.get("boot_info", "?"),
            "The contents of `/proc/cmdline` containing boot information about kernel",
        ),
        helpers.ProfileHeaderEntry(
            "host", machine_info["host"], "The hostname, where the results were measured."
        ),
        helpers.ProfileHeaderEntry(
            "cpu (total)",
            machine_info.get("cpu", {"total": "?"}).get("total", "?"),
            "The total number (physical and virtual) of CPUs available on the host.",
        ),
        helpers.ProfileHeaderEntry(
            "memory (total)",
            machine_info.get("memory", {"total_ram": "?"}).get("total_ram", "?"),
            "The total number of RAM available on the host.",
        ),
    ]


def generate_diff_of_headers(
    lhs_headers: Iterable[helpers.ProfileHeaderEntry],
    rhs_headers: Iterable[helpers.ProfileHeaderEntry],
) -> tuple[list[helpers.ProfileHeaderTuple], list[helpers.ProfileHeaderTuple]]:
    """Generates diffed headers for lhs (baseline) and rhs (target) profiles.

    Based on the configuration parameter 'display_style', either all or only different header
    entries will be generated.

    :param lhs_headers: baseline header entries
    :param rhs_headers: target header entries

    :return: pair of diffed baseline and target header entries
    """
    lhs_diff, rhs_diff = [], []
    # Match the LHS and RHS records by entry name
    lhs_dict = {header.name: header for header in lhs_headers}
    rhs_dict = {header.name: header for header in rhs_headers}
    header_map = common_kit.match_dicts_by_keys(lhs_dict, rhs_dict)
    # Check if we should include all entries or just the diff ones
    display_style = HeaderDisplayStyle(config.lookup_key_recursively("showdiff.display_style"))
    only_diff = display_style == HeaderDisplayStyle.DIFF
    for header_key in sorted(header_map.keys()):
        is_diff: bool = False
        lhs_data, rhs_data = _generate_missing_entry(*header_map[header_key])
        if lhs_data.details or rhs_data.details:
            # There are details in this entry, compare them one by one
            is_diff, lhs_details, rhs_details = _generate_diff_of_details(
                lhs_data.details, rhs_data.details, only_diff
            )
            # We need to work around Dict invariance
            lhs_data.details = cast(dict[str, Union[str, float]], lhs_details)
            rhs_data.details = cast(dict[str, Union[str, float]], rhs_details)
        is_diff, key, lhs_data.value, rhs_data.value = _generate_diff_of_values(
            lhs_data.name, lhs_data.value, rhs_data.value, is_diff
        )
        lhs_data.name = rhs_data.name = key
        # Add this entry if applicable
        if not only_diff or is_diff:
            lhs_diff.append(lhs_data.as_tuple())
            rhs_diff.append(rhs_data.as_tuple())
    return lhs_diff, rhs_diff


def generate_diff_of_stats(
    lhs_stats: Iterable[pstats.ProfileStat], rhs_stats: Iterable[pstats.ProfileStat]
) -> tuple[list[tuple[str, str, str, dict[str, Any]]], list[tuple[str, str, str, dict[str, Any]]]]:
    """Generates the profile stats with HTML diff styles suitable for an output.

    :param lhs_stats: stats from the baseline
    :param rhs_stats: stats from the target
    :return: collection of LHS and RHS stats (stat-name, stat-value, stat-description, stat-details)
             with HTML styles that reflect the stat diffs.
    """
    # Get all the stats that occur in either lhs or rhs and match those that exist in both
    stats_map = common_kit.match_dicts_by_keys(
        {stats.name: stats for stats in lhs_stats}, {stats.name: stats for stats in rhs_stats}
    )
    # Iterate the stats and format them according to their diffs
    lhs_diff, rhs_diff = [], []
    for stat_key in sorted(stats_map.keys()):
        lhs_stat: pstats.ProfileStat | None
        rhs_stat: pstats.ProfileStat | None
        lhs_stat, rhs_stat = stats_map[stat_key]
        lhs_info, rhs_info = _generate_diff_of_stats_record(lhs_stat, rhs_stat)
        lhs_diff.append(lhs_info)
        rhs_diff.append(rhs_info)
    return lhs_diff, rhs_diff


def _generate_missing_entry(
    lhs_data: helpers.ProfileHeaderEntry | None, rhs_data: helpers.ProfileHeaderEntry | None
) -> tuple[helpers.ProfileHeaderEntry, helpers.ProfileHeaderEntry]:
    """Check if both header entries exist and if not, generate the missing one.

    The missing header entry is generated using the values from the existing one.

    :param lhs_data: baseline header entry
    :param rhs_data: target header entry

    :return: both baseline and target header entries
    """
    # Both lhs and rhs must not be None
    assert lhs_data is not None or rhs_data is not None
    if lhs_data is not None and rhs_data is not None:
        return lhs_data, rhs_data
    if lhs_data is not None:
        # Note: rhs data must be None
        return lhs_data, helpers.ProfileHeaderEntry(lhs_data.name, "-", "missing header info", {})
    else:
        # Note: lhs data must be None
        assert rhs_data is not None
        return helpers.ProfileHeaderEntry(rhs_data.name, "-", "missing header info", {}), rhs_data


def _generate_diff_of_details(
    lhs_records: dict[str, str | float], rhs_records: dict[str, str | float], only_diffs: bool
) -> tuple[bool, dict[str, str], dict[str, str]]:
    """Generates diffed nested headers for baseline and target header entry.

    :param lhs_records: nested headers of a baseline header entry
    :param rhs_records: nested headers of a target header entry
    :param only_diffs: if True, only diffed nested headers will be generated.

    :return: a flag indicating whether the nested headers are different or not, and a pair of
             diffed baseline and target nested headers
    """
    lhs_diff, rhs_diff, has_differences = {}, {}, False
    header_map = common_kit.match_dicts_by_keys(lhs_records, rhs_records)
    for header_key in sorted(header_map.keys()):
        lhs_detail, rhs_detail = header_map[header_key]
        is_diff, key, lhs_data, rhs_data = _generate_diff_of_values(
            header_key, lhs_detail, rhs_detail
        )
        has_differences = has_differences or is_diff
        # Check whether we should include this detail
        if not only_diffs or is_diff:
            lhs_diff[key] = lhs_data
            rhs_diff[key] = rhs_data
    return has_differences, lhs_diff, rhs_diff


def _generate_diff_of_values(
    header_key: str,
    lhs_value: str | float | None,
    rhs_value: str | float | None,
    is_diff: bool = False,
) -> tuple[bool, str, str, str]:
    """Generates diff of a single LHS and RHS entry pair.

    :param header_key: name of the header entry
    :param lhs_value: the LHS (baseline) value
    :param rhs_value: the RHS (target) value
    :param is_diff: an override mechanism indicating that the values are different

    :return: different flag, updated header key, diffed lhs value, and diffed rhs value
    """
    lhs_value = "-" if lhs_value is None else str(lhs_value)
    rhs_value = "-" if rhs_value is None else str(rhs_value)
    if lhs_value != rhs_value or is_diff:
        diff = list(difflib.ndiff(str(lhs_value).split(), str(rhs_value).split()))
        header_key = _emphasize(header_key, "primary")
        lhs_value = _diff_to_html(diff, "-")
        rhs_value = _diff_to_html(diff, "+")
        is_diff = True
    return is_diff, header_key, lhs_value, rhs_value


def _generate_diff_of_stats_record(
    lhs_stat: pstats.ProfileStat | None, rhs_stat: pstats.ProfileStat | None
) -> tuple[tuple[str, str, str, dict[str, Any]], tuple[str, str, str, dict[str, Any]]]:
    """Generates a single diffed LHS and RHS profile stats entry.

    :param lhs_stat: the LHS (baseline) stats entry
    :param rhs_stat: the RHS (target) stats entry

    :return: pair of a single diffed LHS (baseline) and RHS (target) stats entry
    """
    lhs_diff = _StatsDiffRecord.from_stat(lhs_stat, rhs_stat)
    rhs_diff = _StatsDiffRecord.from_stat(rhs_stat, lhs_stat)
    if lhs_diff.stat_agg is not None and rhs_diff.stat_agg is not None:
        assert lhs_stat is not None
        lhs_diff.value, rhs_diff.value = _color_stat_record_diff(
            lhs_diff.stat_agg,
            rhs_diff.stat_agg,
            lhs_stat.aggregate_by,
            lhs_diff.stat_agg.infer_auto_comparison(lhs_stat.cmp),
        )
    return lhs_diff.to_tuple(), rhs_diff.to_tuple()


def _diff_to_html(diff: list[str], start_tag: Literal["+", "-"]) -> str:
    """Create a html tag with differences for either + or - changes

    :param diff: diff computed by difflib.ndiff
    :param start_tag: starting point of the tag
    """
    tag_to_color: dict[str, ColorVariableType] = {
        "+": "correct",
        "-": "wrong",
    }
    result = []
    for chunk in diff:
        if chunk.startswith("  "):
            result.append(chunk[2:])
        if chunk.startswith(start_tag):
            result.append(_emphasize(chunk[2:], tag_to_color.get(start_tag, "primary")))
    return " ".join(result)


def _stat_description_to_tooltip(description: str, comparison: pstats.ProfileStatComparison) -> str:
    """Transform a stat description into a tooltip by including the comparison type as well.

    :param description: the original stat description
    :param comparison: the comparison type of the stat

    :return: the generated tooltip
    """
    comparison_str: str = f'[{comparison.value.replace("_", " ")}]'
    return f"{description} {comparison_str}"


def _emphasize(value: str, color: ColorVariableType) -> str:
    """Emphasize a string with a HTML color.

    :param value: the string to emphasize
    :param color: the color to use

    :return: the emphasized string
    """
    return f'<span style="color: var(--color-{color}); font-weight: bold">{value}</span>'


def _format_exit_codes(exit_code: str | list[str] | list[int]) -> str:
    """Format (a collection of) exit code(s) for HTML output.

    Exit codes that are non-zero will be emphasized with a color.

    :param exit_code: the exit code(s)

    :return: the formatted exit codes
    """
    # Unify the exit code types
    exit_codes: list[str] = []
    if isinstance(exit_code, (str, int)):
        exit_codes.append(str(exit_code))
    else:
        exit_codes = list(map(str, exit_code))
    # Color exit codes that are not zero
    return ", ".join(code if code == "0" else _emphasize(code, "wrong") for code in exit_codes)


def _color_stat_record_diff(
    lhs_stat_agg: pstats.ProfileStatAggregation,
    rhs_stat_agg: pstats.ProfileStatAggregation,
    compare_key: str,
    comparison: pstats.ProfileStatComparison,
) -> tuple[str, str]:
    """Color the stats values on the LHS and RHS according to their difference.

    The color is determined by the stat comparison type and the comparison result.

    :param lhs_stat_agg: a baseline stat aggregation
    :param rhs_stat_agg: a target stat aggregation
    :param compare_key: the key by which to compare the stats
    :param comparison: the comparison type of the stat

    :return: colored LHS and RHS stat values
    """
    # Build a color map for different comparison results
    color_map: dict[pstats.StatComparisonResult, tuple[ColorVariableType, ColorVariableType]] = {
        pstats.StatComparisonResult.INVALID: ("wrong", "wrong"),
        pstats.StatComparisonResult.UNEQUAL: ("wrong", "wrong"),
        pstats.StatComparisonResult.EQUAL: ("primary", "primary"),
        pstats.StatComparisonResult.BASELINE_BETTER: ("correct", "wrong"),
        pstats.StatComparisonResult.TARGET_BETTER: ("wrong", "correct"),
    }
    # Compare and color the stat entry
    comparison_result = pstats.compare_stats(lhs_stat_agg, rhs_stat_agg, compare_key, comparison)
    baseline_color, target_color = color_map[comparison_result]
    if comparison_result == pstats.StatComparisonResult.INVALID:
        baseline_value, target_value = "invalid comparison", "invalid comparison"
    else:
        baseline_value = _format_stat_value(lhs_stat_agg.as_table(compare_key)[0])
        target_value = _format_stat_value(rhs_stat_agg.as_table(compare_key)[0])
    return _emphasize(baseline_value, baseline_color), _emphasize(target_value, target_color)


def _format_stat_value(value: str | float | tuple[str, int]) -> str:
    """Formats float stat values to have a fixed number of decimal digits.

    Non-float stat values are kept as is.

    :param value: the value to format.

    :return: the formatted value.
    """
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


@dataclasses.dataclass
class _StatsDiffRecord:
    """A helper struct for storing a difference entry of baseline/target stats.

    :ivar name: name of the stats entry
    :ivar value: the value of the stats entry
    :ivar tooltip: the tooltip of the stats entry
    :ivar stat_agg: the stats aggregation
    """

    name: str = ""
    value: str = "-"
    tooltip: str = "missing stat info"
    stat_agg: pstats.ProfileStatAggregation | None = None
    details: dict[str, Any] = dataclasses.field(default_factory=dict)

    @classmethod
    def from_stat(
        cls, stat: pstats.ProfileStat | None, other_stat: pstats.ProfileStat | None
    ) -> _StatsDiffRecord:
        """Construct a difference record from a baseline/target profile stat.

        If the baseline/target profile stat is not available, we use the other
        (i.e., target/baseline) stat to construct a stub entry to indicate a missing stat.

        :param stat: the baseline/target profile stat to construct from, if available
        :param other_stat: the other profile stat to use for construction as a fallback

        :return: the constructed difference record
        """
        if stat is None:
            # Fallback construction from the other stat
            assert other_stat is not None
            unit = f" [{other_stat.unit}]" if other_stat.unit else ""
            return cls(f"{other_stat.name}{unit}")
        # The standard construction
        stat_agg = pstats.aggregate_stats(stat)
        unit = f" [{stat.unit}]" if stat.unit else ""
        agg_key = stat_agg.normalize_aggregate_key(stat.aggregate_by)
        name = f"{stat.name}{unit} " f"({agg_key})"
        value, details = stat_agg.as_table(agg_key)
        tooltip = _stat_description_to_tooltip(
            stat.description, stat_agg.infer_auto_comparison(stat.cmp)
        )
        return cls(name, str(value), tooltip, stat_agg, details)

    def to_tuple(self) -> tuple[str, str, str, dict[str, Any]]:
        """Convert the difference record to a tuple.

        :return: the tuple representation of the difference record
        """
        return self.name, self.value, self.tooltip, self.details
