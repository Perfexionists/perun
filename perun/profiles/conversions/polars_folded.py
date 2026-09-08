"""Functions for converting Polars profiles to folded profiles."""

from __future__ import annotations

# Standard Imports
from typing import TextIO, TYPE_CHECKING

# Third-Party Imports

# Perun Imports

if TYPE_CHECKING:
    from perun.profiles.polars import structs
    from perun.utils.type_hints import TempTextIO


def store_polars_as_folded_profile(
    trace_profile: structs.PolarsTraceProfile,
    folded_file: TextIO | TempTextIO,
    min_width_threshold: float = 0.0,
) -> int:
    """Store a Polars trace profile into a folded profile.

    As a by-product, we also compute the maximum length of traces that will be rendered in
    flamegraphs of this profile given the input width threshold.

    :param trace_profile: a Polars trace profile
    :param folded_file: a handle to the output file
    :param min_width_threshold: the rendering threshold for flamegraphs

    :return: the maximum trace length w.r.t. the filtering threshold
    """
    # Optimize dot operator access
    str_split = str.split
    str_join = str.join
    func_id_reverse_map = trace_profile.maps.func_id_reverse_map

    max_filtered_len: int = 0

    # Only keep the relevant columns
    for trace_str, exclusive, inclusive in trace_profile.profile.select(
        ["trace", "exclusive", "inclusive"]
    ).iter_rows():
        trace_parts = str_split(trace_str, ";")
        if exclusive:
            # Translate compact trace format to the verbose one, e.g., "1;2;10" -> "main;foo;bar"
            translated = str_join(
                ";", (func_id_reverse_map[int(func_id)] for func_id in trace_parts)
            )
            folded_file.write(f"{translated} {exclusive}\n")
        # Update the maximum trace length
        if inclusive >= min_width_threshold:
            max_filtered_len = max(max_filtered_len, len(trace_parts))
    folded_file.flush()
    return max_filtered_len
