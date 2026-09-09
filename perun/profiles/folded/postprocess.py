"""Functions for postprocessing of folded profiles."""

from __future__ import annotations

# Standard Imports
from collections.abc import Iterator
import re
from typing import TYPE_CHECKING

# Third-Party Imports

# Perun Imports
from perun.profiles import utils

if TYPE_CHECKING:
    from perun.profiles.structs import PostprocessParameters


def postprocess_folded_records(
    input_stream: Iterator[tuple[str, int]],
    params: PostprocessParameters,
) -> Iterator[tuple[str, int]]:
    """Postprocess a stream of folded records.

    The postprocessing includes hiding generics in function names and/or squashing recursive calls.

    :param input_stream: a stream of folded records (stack trace, resource consumption)
    :param params: a structure containing the postprocessing parameters

    :return: an iterator over postprocessed folded records
    """

    # Optimize dot operator access.
    re_search = re.search
    str_split = str.split
    squash_pattern = params.squash_pattern
    squash_recursion_flag = params.squash_recursion
    hide_generics_flag = params.hide_generics

    # Fast path if no postprocessing is requested.
    if not hide_generics_flag and not squash_recursion_flag:
        yield from input_stream
        return

    # Slow path if either squashing or generics hiding is requested.
    for trace, count in input_stream:
        # Split the trace into individual frames.
        frames: list[str] = str_split(trace, ";")

        # Transform the frames in-place.
        if hide_generics_flag:
            frames[:] = [utils.hide_uid_generics(frame) for frame in frames]

        # The squashing algorithm is implemented using two indices over the frame stack: the `iter`
        # index iterates over the entire stack to detect recursive calls, and the `stack` index
        # overwrites frames in-place when squashing happens.
        if squash_recursion_flag:
            stack_idx: int = 0
            iter_idx: int = 1
            end: int = len(frames)
            recursive_count: int = 1
            while iter_idx < end:
                # We want to merge the frames if they represent the same function, and they match
                # the squash pattern. Regex matching is done only once for each sequence of
                # identical frames, and only for non-default patterns (default pattern matches
                # everything).
                if frames[stack_idx] == frames[iter_idx] and (
                    squash_pattern is None
                    or (recursive_count > 1 or re_search(squash_pattern, frames[iter_idx]))
                ):
                    # This frame is part of a recursive call chain.
                    recursive_count += 1
                    iter_idx += 1
                    continue
                elif recursive_count > 1:
                    # A recursive call chain has ended. We update the name of the squashed function.
                    frames[stack_idx] = f";{frames[stack_idx]}{{x{recursive_count}}}"
                    recursive_count = 1
                stack_idx += 1
                iter_idx += 1
            # We must still update the last frame if it was part of a recursive call.
            if recursive_count > 1:
                frames[stack_idx] = f";{frames[stack_idx]}{{x{recursive_count}}}"
                stack_idx += 1
                yield ";".join(frames[:stack_idx]), count
