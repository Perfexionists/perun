"""A collection of parsing functions.

The functions transform, and optionally postprocess, a stream of folded-like record
`(stack_trace, consumed_resources)` into a Polars LazyFrame.
"""

from __future__ import annotations

# Standard Imports
from collections import defaultdict
from collections.abc import Iterator, KeysView, Mapping
import re
from typing import Optional

# Third-Party Imports
import polars as pl

# Perun Imports
from perun.profiles import structs, utils
from perun.profiles.polars import structs as pl_structs


def parse_polars_no_squash(
    record_stream: Iterator[tuple[str, int]],
    maps: pl_structs.FunctionMaps,
    params: structs.PostprocessParameters,
    profile_features: structs.ProfileFeatures,
) -> pl.LazyFrame:
    """Parse a folded profile into a polars frame without squashing recursive calls.

    We implement two separate parsing functions for squash/no-squash variants. The no-squash
    variant is simpler, and we want to keep it as fast as possible.

    :param record_stream: a stream of folded-like records to process
    :param maps: function name and ID maps
    :param params: parsing parameters
    :param profile_features: profile features that describe the parsed profile

    :return: a parsed profile lazyframe with 'func', 'trace', 'inclusive', and 'exclusive' columns
    """
    # trace -> inclusive resource consumption.
    inclusive: defaultdict[str, int] = defaultdict(int)
    # trace -> exclusive resource consumption.
    exclusive: defaultdict[str, int] = defaultdict(int)
    max_trace_len = 0
    total = 0

    # Optimize dot operator access.
    str_split = str.split
    hide_generics_func = utils.hide_uid_generics
    func_id_map = maps.func_id_map
    hide_generics_flag = params.hide_generics

    for trace, count in record_stream:
        # Split the trace into individual frames.
        frames: list[str] = str_split(trace, ";")
        max_trace_len = max(max_trace_len, len(frames))
        total += count

        # Process the first frame of the trace.
        trace = str(func_id_map[frames[0]])
        inclusive[trace] += count
        # Process the rest of the trace.
        for frame in frames[1:]:
            if hide_generics_flag:
                frame = hide_generics_func(frame)
            trace += f";{func_id_map[frame]}"
            inclusive[trace] += count
        exclusive[trace] += count
    # Update the profile features.
    profile_features.total_resources += total
    profile_features.max_trace_len = max(max_trace_len, profile_features.max_trace_len)
    return _build_trace_profile(inclusive, exclusive, None)


def parse_polars_squash(
    record_stream: Iterator[tuple[str, int]],
    maps: pl_structs.FunctionMaps,
    params: structs.PostprocessParameters,
    profile_features: structs.ProfileFeatures,
) -> pl.LazyFrame:
    """Parse a folded profile into a polars frame while squashing recursive calls.

    We implement two separate parsing functions for squash/no-squash variants. The squash variant
    is more complicated and expensive, so we keep it separately to not slow down the no-squash
    implementation.

    :param record_stream: a stream of folded-like records to process
    :param maps: a collection of parsing maps
    :param params: parsing parameters
    :param profile_features: profile features that describe the parsed profile

    :return: a parsed profile lazyframe with 'func', 'trace', 'inclusive', and 'exclusive' columns
    """
    # trace -> inclusive resource consumption.
    inclusive: defaultdict[str, int] = defaultdict(int)
    # trace -> exclusive resource consumption.
    exclusive: defaultdict[str, int] = defaultdict(int)
    max_trace_len = 0
    total = 0

    # Optimize dot operator access.
    re_search = re.search
    str_split = str.split
    hide_generics_func = utils.hide_uid_generics
    func_id_map = maps.func_id_map
    squashed_id_map = maps.squashed_id_map
    squash_pattern = params.squash_pattern
    hide_generics = params.hide_generics

    for trace, count in record_stream:
        # Split the trace into individual frames.
        frames: list[str] = str_split(trace, ";")
        max_trace_len = max(max_trace_len, len(frames))
        total += count

        # The algorithm does not immediately write the processed frame into the compact trace
        # string. Instead, it remembers the last processed frame and either writes it in the
        # next step, or merges it with the successor if squash conditions are satisfied.
        last_frame = func_id_map[frames[0]]
        trace = ""
        recursive_count = 1
        for idx, frame in enumerate(frames[1:]):
            if hide_generics:
                frame = hide_generics_func(frame)
            func_id = func_id_map[frame]

            # We want to merge the frames if they represent the same function, and they match
            # the squash pattern. Regex matching is done only once for each sequence of
            # identical frames, and only for non-default patterns (default pattern matches
            # everything).
            if func_id == last_frame and (
                squash_pattern is None or (recursive_count > 1 or re_search(squash_pattern, frame))
            ):
                # This frame is part of a recursive call chain.
                recursive_count += 1
            elif recursive_count == 1:
                # The previous frame was not part of a recursive call chain; write it.
                if trace:
                    trace += f";{last_frame}"
                else:
                    trace = str(last_frame)
                inclusive[trace] += count
                last_frame = func_id
            else:
                # A recursive call chain has ended. We create a new ID for the squashed
                # function with the number of recursive calls.
                squashed_id = func_id_map[f"{frames[idx]}{{x{recursive_count}}}"]
                trace += f";{squashed_id}"
                squashed_id_map[squashed_id] = last_frame
                inclusive[trace] += count
                last_frame = func_id
                recursive_count = 1
        # We must still process the last frame.
        if recursive_count > 1:
            squashed_id = func_id_map[f"{frames[-1]}{{x{recursive_count}}}"]
            trace += f";{squashed_id}"
            squashed_id_map[squashed_id] = last_frame
        elif trace:
            trace += f";{last_frame}"
        else:
            trace = str(last_frame)
        inclusive[trace] += count
        exclusive[trace] += count
    # Update the profile features.
    profile_features.total_resources += total
    profile_features.max_trace_len = max(max_trace_len, profile_features.max_trace_len)
    return _build_trace_profile(inclusive, exclusive, squashed_id_map)


def _build_trace_profile(
    inclusive: defaultdict[str, int],
    exclusive: defaultdict[str, int],
    squashed_id_map: Optional[Mapping[int, int]],
) -> pl.LazyFrame:
    """Build a per-trace profile from inclusive and exclusive resource consumption records.

    No filtering takes place at this point; although we could, e.g., filter records with no
    exclusive consumption, we would not be able to correctly compute some profile features or lose
    some precision when detecting common functions to baseline and target profiles.

    Both the <inclusive> and <exclusive> maps should have keys in the form of 'id1;id2;id3;...'
    which represent traces in a compact format where id1, id2, and id3 correspond to function IDs.

    If recursion squashing took place, a <squashed_id_map> should be provided as well.

    :param inclusive: a mapping of trace -> inclusive resource consumption
    :param exclusive: a mapping of trace -> inclusive resource consumption
    :param squashed_id_map: a mapping of squashed function ID -> function ID; if not provided,
           we assume no squashing was done

    :return: a per-trace profile with 'func', 'trace', 'inclusive', and 'exclusive' columns
    """
    return pl.LazyFrame(
        {
            "func": _generate_func_ids(inclusive.keys(), squashed_id_map),
            "trace": inclusive.keys(),
            "inclusive": inclusive.values(),
            # The .get() method avoids needlessly growing the defaultdict.
            "exclusive": (exclusive.get(t, 0) for t in inclusive),
        },
        schema={
            "func": pl.UInt32,
            "trace": pl.String,
            "inclusive": pl.Int64,
            "exclusive": pl.Int64,
        },
    )


def _generate_func_ids(
    traces: KeysView[str], squashed_id_map: Optional[Mapping[int, int]]
) -> Iterator[int]:
    """A helper function that extracts the ID of the last function from a possibly squashed trace.

    For squashed traces, the function returns the ID of the non-squashed function symbol. For
    example, if the ID of last function in a trace corresponds to the 'foo{x8}' symbol, the
    function will return the ID of the original 'foo' symbol.

    :param traces: a set of traces to extract the function ID from
    :param squashed_id_map: a mapping of squashed function ID -> function ID; if not provided,
           we assume no squashing was done

    :return: a generator over the extracted function IDs
    """
    # Optimize dot operator access.
    str_rsplit = str.rsplit

    if squashed_id_map is None:
        # No squashing was done, simply extract and return the last ID in the trace.
        for trace in traces:
            yield int(str_rsplit(trace, ";", maxsplit=1)[-1])
    else:
        # Some of the traces may have been squashed.
        for trace in traces:
            last_func_id = int(str_rsplit(trace, ";", maxsplit=1)[-1])
            # Check if the last ID corresponds to a squashed function that needs to be translated.
            try:
                yield squashed_id_map[last_func_id]
            except KeyError:
                yield last_func_id
