"""This module provides wrapper for the Flame graph visualization"""

from __future__ import annotations

# Standard Imports
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass, field
from pathlib import Path
import tempfile
from typing import Any, Iterator

# Third-Party Imports

# Perun Imports
from perun.utils import mapping
from perun.utils.common import script_kit
from perun.utils.external import commands


@contextmanager
def fg_optional_tempfile(flame_data: list[str] | Path) -> Iterator[Path]:
    """A helper context manager that wraps flame graph data into a file path.

    If the provided flame graph data are already stored in a file, the file path is wrapped in
    a context manager. Otherwise, a new temporary file is created, the data are stored in it
    and the context manager wraps the path. The created temporary file will be deleted when the
    context manager wrapper exits.

    :param flame_data: the flame graph data to wrap

    :return: a wrapper context manager
    """
    if isinstance(flame_data, Path):
        # Wrap the path in a nullcontext so that we can use it as if it was a context manager
        with nullcontext(flame_data) as tmp:
            yield tmp
    else:
        # Save the flame data into a temporary file
        with tempfile.NamedTemporaryFile(mode="w") as tmp:
            tmp.write("".join(flame_data))
            # The flush ensures that all data are in the file when the flamegraph scripts read them
            tmp.flush()
            yield Path(tmp.name)


def draw_flame_graph(
    flame_data: list[str] | Path,
    title: str,
    units: str = "samples",
    *fg_flags: str,
    **fg_kwargs: Any,
) -> str:
    """Draw Flame graph from flame data.

    To create Flame graphs we use perl script created by Brendan Gregg.
    https://github.com/brendangregg/FlameGraph/blob/master/flamegraph.pl

    If the flame graph data are provided directly, they are first stored in a temporary file that
    can be read by the flame graph scripts.

    :param flame_data: the data to generate the flame graph from
    :param title: title of the flame graph
    :param units: the units of the flame graph data
    :param fg_flags: additional flags to pass to the flamegraph.pl script
    :param fg_kwargs: additional parameters forwarded to the flamegraph.pl

    :return: the generated flame graph
    """
    # converting profile format to format suitable to Flame graph visualization
    with fg_optional_tempfile(flame_data) as tmp:
        # We extend the flags with 'cp' for consistent palette
        cmd = build_flamegraph_command(tmp, title, units, "cp", *fg_flags, **fg_kwargs)
        out, _ = commands.run_safely_external_command(cmd)
    return out.decode("utf-8")


def draw_differential_flame_graph(
    lhs_flame_data: list[str] | Path,
    rhs_flame_data: list[str] | Path,
    title: str,
    units: str = "samples",
    *fg_flags: str,
    **fg_kwargs: Any,
) -> str:
    """Draws a lhs->rhs differential flame graph.

    If the LHS or RHS flame graph data are provided directly, they are first stored in temporary
    files that can be read by the flame graph scripts.

    :param lhs_flame_data: the data of the baseline profile to generate the flame graph diff from
    :param rhs_flame_data: the data of the target profile to generate the flame graph diff from
    :param title: title of the flame graph
    :param units: the units of the flame graph data
    :param fg_flags: additional flags to pass to the flamegraph.pl script
    :param fg_kwargs: additional parameters forwarded to the flamegraph.pl script

    :return: the lhs->rhs differential flame graph
    """
    with (
        fg_optional_tempfile(lhs_flame_data) as lhs_flame,
        fg_optional_tempfile(rhs_flame_data) as rhs_flame,
    ):
        diff_cmd = " ".join(
            [
                script_kit.get_script("difffolded.pl"),
                "-n",
                str(lhs_flame),
                str(rhs_flame),
            ]
        )
        fg_cmd = build_flamegraph_command(None, title, units, *fg_flags, **fg_kwargs)
        out, _ = commands.run_safely_external_command(f"{diff_cmd} | {fg_cmd}")
    return out.decode("utf-8")


def build_flamegraph_command(
    input_path: Path | None,
    title: str,
    units: str = "samples",
    *flags: str,
    total: int | None = None,
    **kwargs: Any,
) -> str:
    """Creates the flamegraph.pl command that generates a (possibly differential) flame graph.

    :param input_path: path to the file with folded flame graph data
    :param title: title of the flame graph
    :param units: the units of the flame graph data
    :param flags: additional flags to pass to the flamegraph.pl script
    :param total: the 'total' parameter of the flamegraph.pl script, if provided
    :param kwargs: additional parameters forwarded to the flamegraph.pl script

    :return: the resulting command for generating a flame graph
    """
    cmd = [
        script_kit.get_script("flamegraph.pl"),
        str(input_path) if input_path is not None else "",
        "--title",
        f"'{title}'",
        "--countname",
        f"'{units}'",
        "--reverse",
    ]
    # Additional flags
    cmd.extend(f"--{flag}" for flag in flags)
    # Additional parameters
    for key, val in kwargs.items():
        if val is not None:
            cmd.append(f"--{key}")
            cmd.append(f"'{val}'")
    # The 'total' parameter needs special handling: add a rootnode that scales the flamegraph
    # on X axis according to the 'total' value
    if total is not None and total > 0.0:
        cmd.extend(["--total", str(total), "--rootnode", "'Maximum (Baseline, Target)'"])
    return " ".join(cmd)


def generate_title(profile_header: dict[str, Any]) -> str:
    """Generate a title for flame graph based on the profile header.

    :param profile_header: the profile header

    :return: the title of the flame graph
    """
    profile_type = profile_header["type"]
    cmd, workload = (profile_header["cmd"], profile_header["workload"])
    return f"{profile_type} consumption of {cmd} {workload}"


def get_units(profile_key: str) -> str:
    """Obtain the units of the flame graph based on the profile key.

    :param profile_key: the profile key

    :return: the units of the flame graph
    """
    return mapping.get_unit(mapping.get_readable_key(profile_key))


def compute_max_traces(
    flame_data: list[str],
    img_width: float,
    min_width: str,
) -> tuple[int, int, int]:
    """Recreate Brendan Gregg's max trace depth computation for correct flamegraph height.

    This function provides the maximum length of traces and filtered maximum that takes into
    account the filtering of subtraces based on their sample count, as well as the total number of
    samples collected.

    :param flame_data: the flame graph data
    :param img_width: the width of the graph image
    :param min_width: the minimum width of the flame graph rectangles that will be drawn

    :return: the maximum trace length, the maximum length of traces that are being drawn, the total
             number of samples collected
    """
    max_unfiltered_trace = 0
    flame_stacks: _PerfStackRecord = _PerfStackRecord()
    # Process each flame data record
    for stack_trace in flame_data:
        # Update the perf stack traces representation with this record
        stack_str, samples = stack_trace.rsplit(maxsplit=1)
        stack = stack_str.split(";")
        max_unfiltered_trace = max(len(stack), max_unfiltered_trace)
        flame_stacks.update_stack(stack, int(float(samples)))
    min_width_f = _compute_minwidth_samples(flame_stacks.inclusive_samples, img_width, min_width)
    return max_unfiltered_trace, flame_stacks.filter(min_width_f), flame_stacks.inclusive_samples


def _compute_minwidth_samples(max_resource: float, img_width: float, min_width: str) -> float:
    """Computes the minimum width threshold for flamegraph blocks to be displayed.

    Reconstructed from the flamegraph.pl script.

    :param max_resource: the total number of samples collected
    :param img_width: the width of the graph image
    :param min_width: the minimum width of the flame graph rectangles that will be drawn

    :return: the minimum width threshold
    """
    try:
        if min_width.endswith("%"):
            return max_resource * float(min_width[:-1]) / 100
        else:
            x_padding: int = 10
            width_per_time: float = (img_width - 2 * x_padding) / max_resource
            return float(min_width) / width_per_time
    except ZeroDivisionError:
        # Unknown or invalid max_resource, we set the threshold so that it does not filter anything
        return 0.0


@dataclass
class _PerfStackRecord:
    """Representation of a single perf stack frame record from flame data.

    :ivar inclusive_samples: the number of samples in which a given stack frame record occurred
    :ivar nested: callee stack frame records
    """

    inclusive_samples: int = 0
    nested: dict[str, _PerfStackRecord] = field(default_factory=dict)

    def update_stack(self, stack: list[str], samples: int) -> None:
        """Update the stack traces with new flame data record.

        :param stack: the stack trace
        :param samples: the number of samples that contain this stack trace
        """
        self.inclusive_samples += samples
        if stack:
            func = stack.pop()
            self.nested.setdefault(func, _PerfStackRecord()).update_stack(stack, samples)

    def filter(self, min_width: float) -> int:
        """Filter the stack subtraces (recursively) that do not meet the minimum sample threshold.

        :param min_width: the samples threshold

        :return: the maximum stack length after the filtering
        """
        depth: int = 0
        delete_list: list[str] = []
        for nested_func, nested_record in self.nested.items():
            if nested_record.inclusive_samples < min_width:
                # This nested subtrace does not meet the samples threshold, we cut the entire
                # subtrace off including its subtraces.
                delete_list.append(nested_func)
            else:
                # This subtrace meets the threshold, check recursively
                depth = max(depth, nested_record.filter(min_width) + 1)
        for del_key in delete_list:
            del self.nested[del_key]
        return depth
