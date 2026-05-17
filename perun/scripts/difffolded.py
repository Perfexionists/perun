#!/usr/bin/env python3

"""difffolded.py 	Diff baseline and target folded stack files.

Use this for generating flame graph differentials.

USAGE: ./difffolded.py [-hnst] [-f integer|float|auto] baseline target | ./flamegraph.py > diff2.svg

Options are described in the usage message (-h).

The flamegraph will be colored based on higher samples (red) and smaller
samples (blue). The frame widths will be based on the target (2nd folded file).
This might be confusing if stack frames disappear entirely; it will make
the most sense to ALSO create a differential based on the baseline widths,
while switching the hues; eg:

 ./difffolded.py target baseline | ./flamegraph.py --negate > diff1.svg

Here's what they mean when comparing a before and after profile:

diff1.svg: widths show the before profile, colored by what WILL happen
diff2.svg: widths show the after profile, colored by what DID happen

INPUT: See stackcollapse* programs.

OUTPUT: The full list of stacks, with two columns, one from each file.
If a stack wasn't present in a file, the column value is zero.

folded_stack_trace count_from_baseline count_from_target

eg:

funca;funcb;funcc 31 33
...


*******************************************************************************
* Python version details
*******************************************************************************

This Python version is meant as a drop-in replacement for the original Perl
script. As such, it requires only a Python interpreter with the Python standard
library: it deliberately avoids any 3rd party dependencies.

The Python version has been optimized for processing large folded profiles and,
based on some crude local measurements (Python 3.14, cached bytecode), appears
to be almost 2x faster for an example ~150 MB folded profile. Moreover, even
more speedup (~3x) can be achieved by importing the script and using its (lazy)
API directly. Small profiles tend to exhibit a slowdown compared to the Perl
version as the execution time is dominated by the Python interpreter startup
cost (~40ms+ on a local machine). Also note that the optimizations cause some
code duplication as we have no macros or templates in Python.

Additionally, this version introduces some minor changes compared to the
original Perl script:

 - Unhandled zero division in normalization is now detected, a warning is
   issued to the user, and the script falls back to the non-normalized output.
   Additionally, the exact float comparison has been replaced with a more
   reliable comparison.

 - Scientific notation is now supported both on the input and output.

 - The script can be used either through a CLI exactly as the Perl version, or
   through a programmatic Python API by importing the file and calling either
   the 'diff_folded' or 'diff_folded_lazy' functions. Using the functions
   directly will lead to an even bigger speedup (crude measurements show up to
   3x speedup).

 - The CLI has a new '--formatter' option related to the standard output.
   By default (the 'integer' mode), it truncates all counts to integers.
   However, the user may supply a custom Python formatter string (e.g.,'.3f'
   or '.10g') to format the counts (if an invalid formatter is passed, the
   script falls back to the 'integer' format. This option is ignored when
   using the API directly.

 - The CLI has a new '--sort-stacks' option which lexicographically sorts the
   diff records on output. This is especially useful when passing the diff
   output to the 'flamegraph.py' script directly, but it is also much faster
   to use this option than to sort the output file later, e.g., using the GNU
   'sort' coreutil.

 TODO: the script should also support 'reverse'. We do not need it yet, as
  folded report does not use reversed stacks.

*******************************************************************************

COPYRIGHT: Copyright (c) 2014 Brendan Gregg.

 This program is free software; you can redistribute it and/or
 modify it under the terms of the GNU General Public License
 as published by the Free Software Foundation; either version 2
 of the License, or (at your option) any later version.

 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with this program; if not, write to the Free Software Foundation,
 Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.

 (http://www.gnu.org/copyleft/gpl.html)

01-May-2026   Jiri Pavela   Optimized and ported to Python.
28-Oct-2014	Brendan Gregg	Created this.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable, MutableMapping, Iterator
from operator import itemgetter
import re
import sys
from typing import Any

# Absolute tolerance when comparing floats for equality.
DIFF_FOLDED_EPS = 1e-9


class FoldedDiff:
    """The result of the diff operation on folded profiles.

    :ivar data: the (possibly normalized and sorted) diffs stored as triples
          ``(stack, baseline count, target count)`` in a list.
    :ivar baseline_sum: the sum of all counts in the baseline profile.
    :ivar target_sum: the sum of all counts in the baseline profile.

    Note that we store the records in 'data' as tuples, since it appears to be
    the fastest and most memory-efficient variant compared to lists or custom
    (data)classes even though tuple immutability does not suit us.
    """

    __slots__ = "data", "baseline_sum", "target_sum"

    def __init__(
        self,
        data: list[tuple[str, float, float]],
        baseline_sum: float,
        target_sum: float,
    ) -> None:
        self.data: list[tuple[str, float, float]] = data
        self.baseline_sum: float = baseline_sum
        self.target_sum: float = target_sum


class FoldedDiffLazy:
    """The result of the diff operation on folded profiles computed lazily.

    This object is returned from the generator version of the diff operation.
    This may be slightly more efficient than the ``FoldedDiff`` when
    normalization and sorting are disabled, and the caller code needs
    to iterate over the data at most once.

    Enabling normalization or sorting will generally result in a similar
    performance as in the eager variant.

    Warning: when normalization and sorting are disabled, the ``target_sum``
    value is computed lazily as the collection is iterated, i.e., it stores
    only a partial result until the iterator is exhausted.

    :ivar data: the (possibly normalized and sorted) diffs yielded as
          triples ``(stack, baseline count, target count)``.
    :ivar baseline_sum: the sum of all counts in the baseline profile.
    :ivar target_sum: the sum of all counts in the baseline profile.
    """

    __slots__ = "data", "baseline_sum", "target_sum"

    def __init__(
        self,
        data_generator: Iterable[tuple[str, float, float]],
        baseline_sum: float,
        target_sum: float,
    ) -> None:
        self.data: Iterable[tuple[str, float, float]] = data_generator
        self.baseline_sum: float = baseline_sum
        self.target_sum: float = target_sum


def diff_folded(
    baseline: str,
    target: str,
    *,
    striphex: bool = False,
    normalize: bool = False,
    sort_stacks: bool = False,
    **_: Any,
) -> FoldedDiff:
    """Diff two folded profiles.

    This function may be used directly instead of calling the script through
    its CLI:

    ```
    folded = diff_folded(baseline, target, False, True)
    for stack, base_cnt, target_cnt in folded.data:
        ...
    ```

    Note that the ``diff_folded_lazy`` variant is generally more efficient when
    the entire diff does not need to be stored and accessed randomly and/or
    repeatedly, e.g., when the caller will simply iterate over the diffs.

    :param baseline: a path to the baseline folded profile.
    :param target: a path to the target folded profile.
    :param striphex: strip hex addresses in the stacks, e.g.,
           replace ``0x1234abc`` with ``0x...``.
    :param normalize: normalize the baseline sample counts using the formula
           ``(baseline_count * target_sum / baseline_sum)``.
    :param sort_stacks: sort the records lexicographically w.r.t. the stack.

    :return: a ``FoldedDiff`` object with the diff records.

    Extra keyword arguments are ignored so that dictionaries with possibly
    additional keys may be unpacked directly when calling the function.
    """
    folded = parse_profiles_eagerly(baseline, target, striphex)
    if sort_stacks:
        folded.data.sort(key=itemgetter(0))
    if normalize:
        folded.data = normalize_eager_diff(folded.data, folded.baseline_sum, folded.target_sum)
    return folded


def diff_folded_lazy(
    baseline: str,
    target: str,
    *,
    striphex: bool = False,
    normalize: bool = False,
    sort_stacks: bool = False,
    **_: Any,
) -> FoldedDiffLazy:
    """Diff two folded profiles lazily.

    This function may be used directly instead of calling the script through
    its CLI:

    ```
    folded_lazy = diff_folded_lazy(baseline, target)
    for stack, base_cnt, target_cnt in folded_lazy.data:
        ...
    ```

    The lazy variant will store the baseline profile in memory and then, when
    possible, will yield diff records on demand without storing the entire
    target profile in memory.

    Note that the most efficient use-case for lazy diff is when neither sorting
    nor normalization is requested. Otherwise, requesting normalization and/or
    sorting will lead to slightly slower execution and more memory consumption
    as the entire target profile needs to be eagerly parsed and stored in
    memory. Still, minor performance gains compared to a fully eager approach
    can be expected as the normalization and sorting can be done at least
    partially lazily.


    :param baseline: a path to the baseline folded profile.
    :param target: a path to the target folded profile.
    :param striphex: strip hex addresses in the stacks, e.g.,
           replace ``0x1234abc`` with ``0x...``.
    :param normalize: normalize the baseline sample counts using the formula
           ``(baseline_count * target_sum / baseline_sum)``.
    :param sort_stacks: sort the records lexicographically w.r.t. the stack.

    :return: a ``FoldedDiffLazy`` object with the diff record generator.

    Extra keyword arguments are ignored so that dictionaries with possibly
    additional keys may be unpacked directly when calling the function.
    """
    if normalize and not sort_stacks:
        # Normalization without sorting is the only combination that requires
        # us to parse the profiles eagerly to obtain the 'target_sum'.
        # However, the normalization itself can be done lazily.
        folded: FoldedDiff = parse_profiles_eagerly(baseline, target, striphex)
        data_gen = normalize_lazy_diff(folded.data, folded.baseline_sum, folded.target_sum)
        return FoldedDiffLazy(data_gen, folded.baseline_sum, folded.target_sum)

    folded_lazy: FoldedDiffLazy = parse_profiles_lazily(baseline, target, striphex)
    data_iter = folded_lazy.data
    if sort_stacks:
        data_iter = sorted(folded_lazy.data, key=itemgetter(0))
    if normalize:
        data_iter = normalize_lazy_diff(data_iter, folded_lazy.baseline_sum, folded_lazy.target_sum)
    folded_lazy.data = data_iter
    return folded_lazy


def parse_profiles_eagerly(
    baseline_file: str, target_file: str, striphex: bool = False
) -> FoldedDiff:
    """A helper function that parses both profiles eagerly.

    :param baseline_file: a path to the baseline folded profile.
    :param target_file: a path to the target folded profile.
    :param striphex: strip hex addresses in the stacks, e.g.,
           replace ``0x1234abc`` with ``0x...``.

    :return: a ``FoldedDiff`` object with non-normalized and unsorted records.
    """
    hex_pattern: re.Pattern[str] | None = build_strip_hex_pattern(striphex)
    baseline_data, baseline_total = parse_baseline(baseline_file, hex_pattern)
    folded: FoldedDiff = parse_target(target_file, baseline_data, baseline_total, hex_pattern)
    return folded


def parse_profiles_lazily(
    baseline_file: str, target_file: str, striphex: bool = False
) -> FoldedDiffLazy:
    """A helper function that parses the baseline eagerly and the target lazily.

    :param baseline_file: a path to the baseline folded profile.
    :param target_file: a path to the target folded profile.
    :param striphex: strip hex addresses in the stacks, e.g.,
           replace ``0x1234abc`` with ``0x...``.

    :return: a ``FoldedDiffLazy`` object with non-normalized, unsorted records.
    """
    hex_pattern: re.Pattern[str] | None = build_strip_hex_pattern(striphex)
    baseline_data, baseline_total = parse_baseline(baseline_file, hex_pattern)
    # The 'iter([])' is used as a temporary placeholder in order to
    # construct a valid 'FoldedDiffLazy' object, which is needed by the parsing
    # function. This is not the most elegant design, but it allows the lazy
    # parser to update the 'target_sum' as it parses the target profile.
    folded_lazy = FoldedDiffLazy(iter([]), baseline_total, 0.0)
    folded_lazy.data = parse_target_lazy(target_file, folded_lazy, baseline_data, hex_pattern)
    return folded_lazy


def parse_baseline(
    file_path: str,
    hex_strip_pattern: re.Pattern[str] | None,
) -> tuple[dict[str, float], float]:
    """Parses the baseline profile (eagerly).

    Note that there is no need to have a lazy variant of the baseline parser
    as even the lazy diff computation needs the entire baseline profile to be
    parsed.

    :param file_path: a path to the baseline folded profile.
    :param hex_strip_pattern: a RE pattern for stripping hex symbols.

    :return: a ``stack -> count`` mapping and the sum of all baseline counts.
    """
    # Optimize dot access
    str_rsplit = str.rsplit
    re_sub = re.Pattern.sub

    baseline_data: dict[str, float] = {}
    total_baseline = 0.0
    try:
        with open(file_path, encoding="utf-8") as file_handle:
            if hex_strip_pattern is None:
                for line in file_handle:
                    stack, count_str = str_rsplit(line, maxsplit=1)
                    try:
                        count = float(count_str)
                        total_baseline += count
                        baseline_data[stack] = count
                    except ValueError:
                        # The count conversion to float failed.
                        pass
            else:
                for line in file_handle:
                    stack, count_str = str_rsplit(line, maxsplit=1)
                    stack = re_sub(hex_strip_pattern, "0x...", stack)
                    try:
                        count = float(count_str)
                        total_baseline += count
                        baseline_data[stack] = count
                    except ValueError:
                        # The count conversion to float failed.
                        pass
        return baseline_data, total_baseline
    except OSError:
        print(f"ERROR: Can't read {file_path}", file=sys.stderr)
        sys.exit(1)


def parse_target(
    file_path: str,
    baseline_data: MutableMapping[str, float],
    baseline_sum: float,
    hex_strip_pattern: re.Pattern[str] | None,
) -> FoldedDiff:
    """Parses the target profile eagerly.

    :param file_path: a path to the target folded profile.
    :param baseline_data: the baseline profile data.
    :param baseline_sum: the sum of all baseline counts.
    :param hex_strip_pattern: a RE pattern for stripping hex symbols.

    :return: a ``FoldedDiff`` object with non-normalized and unsorted records.
    """
    # Optimize dot access
    str_rsplit = str.rsplit
    re_sub = re.Pattern.sub

    folded_data: list[tuple[str, float, float]] = []
    total_target = 0.0
    try:
        with open(file_path, encoding="utf-8") as file_handle:
            if hex_strip_pattern is None:
                for line in file_handle:
                    stack, count_str = str_rsplit(line, maxsplit=1)
                    try:
                        count = float(count_str)
                        total_target += count
                        folded_data.append((stack, baseline_data.pop(stack), count))
                    except KeyError:
                        folded_data.append((stack, 0.0, count))
                    except ValueError:
                        # The count conversion to float failed.
                        pass
            else:
                for line in file_handle:
                    stack, count_str = str_rsplit(line, maxsplit=1)
                    stack = re_sub(hex_strip_pattern, "0x...", stack)
                    try:
                        count = float(count_str)
                        total_target += count
                        folded_data.append((stack, baseline_data.pop(stack), count))
                    except KeyError:
                        folded_data.append((stack, 0.0, count))
                    except ValueError:
                        # The count conversion to float failed.
                        pass
        # Add baseline stacks that do not have a matching record in target.
        folded_data.extend(
            (stack, baseline_count, 0.0) for stack, baseline_count in baseline_data.items()
        )
        return FoldedDiff(folded_data, baseline_sum, total_target)
    except OSError:
        print(f"ERROR: Can't read {file_path}", file=sys.stderr)
        sys.exit(1)


def parse_target_lazy(
    file_path: str,
    folded_lazy: FoldedDiffLazy,
    baseline_data: MutableMapping[str, float],
    hex_strip_pattern: re.Pattern[str] | None,
) -> Iterator[tuple[str, float, float]]:
    """Parses the target profile lazily.

    :param file_path: a path to the target folded profile.
    :param folded_lazy: a partially initialized ``FoldedDiffLazy`` object
           where only the ``baseline_sum`` attribute is properly initialized.
    :param baseline_data: the baseline profile data.
    :param hex_strip_pattern: a RE pattern for stripping hex symbols.

    :return: a generator over the non-normalized and unsorted diff records.
    """
    # Optimize dot access
    str_rsplit = str.rsplit
    re_sub = re.Pattern.sub

    try:
        with open(file_path, encoding="utf-8") as file_handle:
            if hex_strip_pattern is None:
                for line in file_handle:
                    stack, count_str = str_rsplit(line, maxsplit=1)
                    try:
                        count = float(count_str)
                        folded_lazy.target_sum += count
                        yield stack, baseline_data.pop(stack), count
                    except KeyError:
                        yield stack, 0.0, count
                    except ValueError:
                        # The count conversion to float failed.
                        pass
            else:
                for line in file_handle:
                    stack, count_str = str_rsplit(line, maxsplit=1)
                    stack = re_sub(hex_strip_pattern, "0x...", stack)
                    try:
                        count = float(count_str)
                        folded_lazy.target_sum += count
                        yield stack, baseline_data.pop(stack), count
                    except KeyError:
                        yield stack, 0.0, count
                    except ValueError:
                        # The count conversion to float failed.
                        pass
        # Add baseline stacks that do not have a matching record in target.
        for stack, baseline_count in baseline_data.items():
            yield stack, baseline_count, 0.0
    except OSError:
        print(f"ERROR: Can't read {file_path}", file=sys.stderr)
        sys.exit(1)


def normalize_eager_diff(
    data: list[tuple[str, float, float]], baseline_sum: float, target_sum: float
) -> list[tuple[str, float, float]]:
    """Normalize eager diff records.

    Returns the ``data`` unmodified if normalization should be skipped
    (i.e., zero division error or identical sums).

    :param data: eagerly computed diff records to normalize.
    :param baseline_sum: the sum of all baseline counts.
    :param target_sum: the sum of all target counts.
    """
    scale: float | None = compute_scale_factor(baseline_sum, target_sum)
    if scale is not None:
        return [
            (stack, count_baseline * scale, count_target)
            for stack, count_baseline, count_target in data
        ]
    return data


def normalize_lazy_diff(
    data_iter: Iterable[tuple[str, float, float]],
    baseline_sum: float,
    target_sum: float,
) -> Iterable[tuple[str, float, float]]:
    """Normalize lazily computed diff records.

    Returns the ``data_iter`` if normalization should be skipped
    (i.e., zero division error or identical sums).

    :param data_iter: lazily computed diff records to normalize.
    :param baseline_sum: the sum of all baseline counts.
    :param target_sum: the sum of all target counts.
    """
    scale: float | None = compute_scale_factor(baseline_sum, target_sum)
    if scale is not None:
        return (
            (stack, count_baseline * scale, count_target)
            for stack, count_baseline, count_target in data_iter
        )
    return data_iter


def build_strip_hex_pattern(striphex: bool) -> re.Pattern[str] | None:
    """Pre-compile a regex pattern for detecting hex addresses.

    :param striphex: a flag indicating whether to strip hex addresses.

    :return: a regex pattern or ``None``, if hex stripping is disabled.
    """
    return re.compile(r"0x[0-9a-fA-F]+") if striphex else None


def compute_scale_factor(baseline_sum: float, target_sum: float) -> float | None:
    """Safely compute the normalization scale factor.

    If the scale factor cannot be computed, the normalization will be skipped.

    :param baseline_sum: the sum of all baseline counts.
    :param target_sum: the sum of all target counts.

    :return: a normalization scale factor or ``None`` if it cannot be computed.
    """
    scale: float | None = None
    # The 1e-9 acts as a float comparison epsilon.
    if abs(baseline_sum - target_sum) > DIFF_FOLDED_EPS:
        try:
            scale = target_sum / baseline_sum
        except ZeroDivisionError:
            # The original Perl script did not detect zero divisions.
            # If it happens, we avoid the normalization.
            print(
                "WARNING: Skipping normalization as the total baseline" " consumption is zero.",
                file=sys.stderr,
            )
    return scale


def print_diff_records(
    folded_data: Iterable[tuple[str, float, float]],
    formatter: str,
) -> None:
    """Format and print the folded records to the standard output.

    :param folded_data: the (eagerly or lazily computed) diff records to print.
    :param formatter: the formatting string to use for counts. Should be either
           ``""``, ``"integer"``, or any valid float formatting string.
    """
    # We avoid the print function as it has slightly higher overhead compared
    # to a direct stdout write.
    out = sys.stdout.write

    try:
        if formatter not in ("", "integer"):
            for stack, c1, c2 in folded_data:
                out(f"{stack} {c1:{formatter}} {c2:{formatter}}\n")
            return
    except ValueError as e:
        # Likely an invalid formatter. Fall back to an integer format.
        print(f"WARNING: An invalid formatter: {e}", file=sys.stderr)
    for stack, c1, c2 in folded_data:
        out(f"{stack} {int(c1):d} {int(c2):d}\n")


def initialize_cli_options(cli_parser: argparse.ArgumentParser) -> None:
    """Initializes the CLI options that may be reused by composite scripts.

    When importing the difffolded.py script by other Python scripts, it might
    be helpful to extend their CLI options with the options and arguments used
    by this script.

    Note that the ``--formater`` and ``--sort-stacks`` options are skipped.

    :param cli_parser: a CLI parser to extend.
    """
    cli_parser.add_argument(
        "-n",
        "--normalize",
        action="store_true",
        help=(
            "Normalize the baseline sample counts using the formula"
            "(baseline_count * target_sum / baseline_sum)."
        ),
    )
    cli_parser.add_argument(
        "-s",
        "--striphex",
        action="store_true",
        help=("Strip hex addresses in the stacks, e.g., replace '0x1234abc' with" " '0x...'."),
    )
    cli_parser.add_argument(
        "baseline",
        metavar="baseline",
        type=str,
        help="The first folded stack file (baseline).",
    )
    cli_parser.add_argument(
        "target",
        metavar="target",
        type=str,
        help="The second folded stack file (target)",
    )


if __name__ == "__main__":
    _cli_parser = argparse.ArgumentParser(
        description=("Diff two folded stack files for flame graph differentials."),
        usage=(
            "%(prog)s [-hnst] [-f integer|float|auto] folded1 folded2 |"
            " flamegraph.pl > diff2.svg"
        ),
    )
    _cli_parser.add_argument(
        "-f",
        "--formatter",
        default="integer",
        type=str,
        help=(
            "Format the counts on stdout output: use 'integer' or '' to"
            " truncate floats to integers and avoid scientific notation;"
            " or supply a custom formatter string (e.g., '.10g') that will be"
            " passed directly to the f-string expression. Falls back to the"
            " 'integer' formatter in case of an invalid formating string"
            " (default='integer')."
        ),
    )
    _cli_parser.add_argument(
        "-t",
        "--sort-stacks",
        action="store_true",
        help="Sort the stacks lexicographically.",
    )
    initialize_cli_options(_cli_parser)
    _cli_args = _cli_parser.parse_args()

    _folded_lazy = diff_folded_lazy(**vars(_cli_args))
    print_diff_records(_folded_lazy.data, _cli_args.formatter)
