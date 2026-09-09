"""A module for generating grids of Flame graphs."""

from __future__ import annotations

# Standard Imports
from collections.abc import Iterator
import contextlib
import dataclasses
from pathlib import Path
import re
from subprocess import PIPE, TimeoutExpired
import tempfile
from typing import Any, ClassVar, Optional, Protocol, Type, TYPE_CHECKING

# Third-Party Imports

# Perun Imports
from perun.utils import log, type_hints
from perun.utils.external import commands, processes
from perun.utils.structs.view_structs import FlameGraphSettings
from perun.view.flamegraph import core

if TYPE_CHECKING:
    from subprocess import Popen
    from types import TracebackType


@dataclasses.dataclass
class FlameGraphGrid:
    """A collection of flamegraphs that form a 2x2 grid of baseline, target and their diffs.

    The stored flamegraphs are already properly escaped and as such may be directly embedded into
    an HTML report.

    :ivar baseline: the baseline flamegraph
    :ivar target: the target flamegraph
    :ivar baseline_target_diff: the baseline-target difference flamegraph
    :ivar target_baseline_diff: the target-baseline difference flamegraph
    """

    __slots__ = "baseline", "target", "baseline_target_diff", "target_baseline_diff"

    # The default flamegraph titles used when generating the flamegraphs.
    DefaultTitles: ClassVar[tuple[str, str, str, str]] = (
        "Baseline Flamegraph",
        "Target Flamegraph",
        "Baseline > Target Diff Flamegraph",
        "Target > Baseline Diff Flamegraph",
    )
    # The tags used for escaping flamegraphs in the grid.
    EscapeTags: ClassVar[tuple[str, str, str, str]] = ("lhs_0", "rhs_0", "lhs_diff_0", "rhs_diff_0")

    def __init__(
        self,
        baseline: str = "",
        target: str = "",
        baseline_target_diff: str = "",
        target_baseline_diff: str = "",
    ) -> None:
        """
        :param baseline: the baseline flamegraph
        :param target: the target flamegraph
        :param baseline_target_diff: the baseline-target difference flamegraph
        :param target_baseline_diff: the target-baseline difference flamegraph
        """
        self.baseline: str = baseline
        self.target: str = target
        self.baseline_target_diff: str = baseline_target_diff
        self.target_baseline_diff: str = target_baseline_diff

    def __setitem__(self, index: int, flame_graph: str) -> None:
        """Set a new flamegraph according to the index.

        A helper method for access to individual flamegraphs, e.g., in a loop. Supported indices
        are [0, 3] and correspond to the baseline, target, baseline_target_diff, and
        target_baseline_diff flamegraphs.

        :param index: the index of the flamegraph; must be within the [0, 3] range
        :param flame_graph: the new flamegraph
        """
        setattr(self, self.__slots__[index], flame_graph)

    def __getitem__(self, index: int) -> str:
        """Get the flamegraph currently stored at an index.

        A helper method for access to individual flamegraphs, e.g., in a loop. Supported indices
        are [0, 3] and correspond to the baseline, target, baseline_target_diff, and
        target_baseline_diff flamegraphs.

        :param index: the index of the flamegraph to retrieve; must be within the [0, 3] range

        :return: the flamegraph currently stored at the index
        """
        return getattr(self, self.__slots__[index])

    def copy_from(self, grid: FlameGraphGrid) -> None:
        """Copies flamegraphs from another grid into this grid.

        :param grid: the other grid to copy the flamegraphs from
        """
        self.baseline = grid.baseline
        self.target = grid.target
        self.baseline_target_diff = grid.baseline_target_diff
        self.target_baseline_diff = grid.target_baseline_diff


@dataclasses.dataclass
class FlameGraphGridCommands:
    """A collection of commands and options for generating a flamegraph grid.

    :ivar escape_graphs: a flag indicating whether the SVGs should be escaped for HTML embedding
    :ivar baseline: the command to generate the baseline flamegraph
    :ivar target: the command to generate the target flamegraph
    :ivar baseline_target_difffolded: the command to diff baseline and target folded profiles
    :ivar baseline_target_fg_diff: the command to generate baseline-target difference flamegraph
    :ivar target_baseline_difffolded: the command to diff target and baseline folded profiles
    :ivar target_baseline_fg_diff: the command to generate target-baseline difference flamegraph
    """

    __slots__ = (
        "escape_graphs",
        "baseline",
        "target",
        "baseline_target_difffolded",
        "baseline_target_fg_diff",
        "target_baseline_difffolded",
        "target_baseline_fg_diff",
    )

    escape_graphs: bool
    baseline: str
    target: str
    baseline_target_difffolded: str
    baseline_target_fg_diff: str
    target_baseline_difffolded: str
    target_baseline_fg_diff: str


class FlameGraphGridBuilder(Protocol):
    """A context manager interface for flamegraph grid creation.

    This context manager interface serves as a wrapper to simplify and unify the code for both
    serial and parallel creation of flamegraph grids. Although a flamegraph grid can be built
    serially without the need for a context manager, building the grid in parallel background
    processes needs a context manager that properly terminates and cleanup the processes and
    other resources when needed.
    """

    def __enter__(self): ...

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> Optional[bool]: ...


class FlameGraphGridSerialBuilder:
    """A context manager wrapper over serial flamegraph grid creation.

    The flamegraph grid creation begins when the class is instantiated. When the context manager
    is entered, the flamegraph grid is already available.

    See FlameGraphGridBuilder for more details.
    """

    def __init__(
        self,
        grid: FlameGraphGrid,
        grid_commands: FlameGraphGridCommands,
    ) -> None:
        """
        :param grid: [out] a reference to the grid object for the generated flamegraphs; context
               managers cannot explicitly return values, hence we use an output parameter
        :param grid_commands: the commands for generating a flamegraph grid
        """
        # We cannot simply assign the grids as it would not propagate outside the object.
        grid.copy_from(build_flamegraph_grid_serially(grid_commands))

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> Optional[bool]:
        return None


class FlameGraphGridParallelBuilder(contextlib.ExitStack):
    """A context manager for parallel background flamegraph grid creation.

    Each flamegraph in the grid is created using a separate process that runs in the background.
    The processes are spawned when the class is instantiated and terminated (waited for) when the
    context manager scope is about to be exited. Only the __exit__ method is blocking, meaning the
    code within the context manager scope is executed in parallel to the flamegraph processes
    running in the background.

    This class inherits from the ExitStack since it internally creates a lot of other context
    managers that must be properly managed and exited even if an error occurs.

    :ivar fg_handles: handles to temporary output files for the created flamegraphs; pipes have
          limited buffer sizes and we do not want to periodically scan for output or use blocking
          methods for reading the output
    :ivar diff_processes: handles of difffolded.pl (.py) processes that generate data for diff
          flamegraphs
    :ivar fg_processes: handles of flamegraph.pl (.py) processes
    :ivar grid: a reference to the grid object for the generated flamegraphs; context managers
          cannot explicitly return values, hence we use an output parameter
    :ivar escape_svgs: a flag indicating the SVGs should be escaped for HTML embedding
    """

    __slots__ = "fg_handles", "diff_processes", "fg_processes", "grid", "escape_svgs"

    def __init__(
        self,
        grid: FlameGraphGrid,
        grid_commands: FlameGraphGridCommands,
    ) -> None:
        """
        :param grid: [out] a grid object which will contain the generated flamegraphs
        :param grid_commands: the commands for generating a flamegraph grid
        """
        super().__init__()
        self.fg_handles: list[type_hints.TempTextIO] = []
        self.diff_processes: list[Popen[bytes]] = []
        self.fg_processes: list[Popen[bytes]] = []
        self.grid: FlameGraphGrid = grid
        self.escape_svgs: bool = grid_commands.escape_graphs

        log.major_info("Creating Flame Graph Grid (In Parallel)")

        # Here we start populating the ExitStack with context managers.
        # Spawn 4 temporary files that will store the generated flamegraphs.
        self.fg_handles = [
            self.enter_context(tempfile.NamedTemporaryFile(mode="w+")) for _ in range(4)
        ]
        # Spawn two difffolded processes: one for each diff flamegraph.
        # The processes should be spawned only if we are using the original Perl scripts and not
        # the optimized Python ones, which is indicated by empty difffolded commands.
        if grid_commands.baseline_target_difffolded:
            self.diff_processes = [
                self.enter_context(
                    processes.nonblocking_subprocess(
                        grid_commands.baseline_target_difffolded, {"stdout": PIPE}
                    )
                ),
                self.enter_context(
                    processes.nonblocking_subprocess(
                        grid_commands.target_baseline_difffolded, {"stdout": PIPE}
                    )
                ),
            ]
        # Spawn four flamegraph processes: one for each flamegraph in the grid.
        base_tar_kwargs: dict[str, Any] = {"stdout": self.fg_handles[2]}
        tar_base_kwargs: dict[str, Any] = {"stdout": self.fg_handles[3]}
        # Handle both Perl and Python versions.
        if grid_commands.baseline_target_difffolded:
            base_tar_kwargs["stdin"] = self.diff_processes[0].stdout
            tar_base_kwargs["stdin"] = self.diff_processes[1].stdout
        self.fg_processes = [
            self.enter_context(
                processes.nonblocking_subprocess(
                    grid_commands.baseline, {"stdout": self.fg_handles[0]}
                )
            ),
            self.enter_context(
                processes.nonblocking_subprocess(
                    grid_commands.target, {"stdout": self.fg_handles[1]}
                )
            ),
            self.enter_context(
                processes.nonblocking_subprocess(
                    grid_commands.baseline_target_fg_diff,
                    base_tar_kwargs,
                )
            ),
            self.enter_context(
                processes.nonblocking_subprocess(
                    grid_commands.target_baseline_fg_diff,
                    tar_base_kwargs,
                )
            ),
        ]
        log.minor_success("Spawning flamegraph background processes")

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> Optional[bool]:
        """Context manager exit method that gathers the flamegraphs unless an error occurred.

        If an error occurred either somewhere in the context manager scope or within this method,
        the ExitStack exits all stored context managers and the error is propagated outside.
        In such case, the flamegraph grid is not guaranteed to be fully created depending on where
        the error happened.

        If no error occurred, this method waits for all flamegraph processes to finish and populates
        the output grid object.

        Note that this is a blocking method.

        :param exc_type: the type of the exception that occurred, if any
        :param exc_val: the actual exception object, if any
        :param exc_tb: the traceback of the error, if any
        """
        try:
            # Only wait for and gather the flamegraphs if no error occurred yet.
            if exc_type is None:
                # We do not want to modify the list of handles directly. Instead, we keep a list of
                # handle indices corresponding to processes that have not finished yet.
                running_fg_processes: list[int] = list(range(len(self.fg_processes)))
                # Prepare the SVG escape tags so that we can escape the SVGs concurrently.
                tags_to_idx = {tag: idx for idx, tag in enumerate(FlameGraphGrid.EscapeTags)}
                while running_fg_processes:
                    for list_idx, proc_idx in enumerate(running_fg_processes):
                        try:
                            self.fg_processes[proc_idx].wait(timeout=0.1)
                            # This process has finished, store the generated flamegraph in the grid.
                            self.fg_handles[proc_idx].seek(0)
                            self.grid[proc_idx] = self.fg_handles[proc_idx].read()
                            if self.escape_svgs:
                                self.grid[proc_idx] = escape_flamegraph_svg(
                                    FlameGraphGrid.EscapeTags[proc_idx],
                                    self.grid[proc_idx],
                                    tags_to_idx,
                                )
                            log.minor_success(FlameGraphGrid.DefaultTitles[proc_idx], "generated")
                            running_fg_processes.pop(list_idx)
                            break
                        except TimeoutExpired:
                            # This process is still running, check the next one.
                            pass
                # Cleanup the difffolded processes properly. If the diff flamegraph processes
                # finished correctly, the difffolded processes must have finished as well.
                for diff_process in self.diff_processes:
                    diff_process.wait()
                log.minor_success("Flamegraph grid", "completed")
        except:
            # We use the catch-all except clause deliberately, as the resources should be cleaned
            # no matter what errors happened.
            super().__exit__(exc_type, exc_val, exc_tb)
            raise
        # The flamegraph grid is complete, cleanup all the context managers and resources.
        return super().__exit__(exc_type, exc_val, exc_tb)


def build_flamegraph_grid_serially(grid_cmds: FlameGraphGridCommands) -> FlameGraphGrid:
    """Create a flamegraph grid serially in this process.

    :param grid_cmds: the commands for generating a flamegraph grid

    :return: the generated flamegraph grid
    """
    log.major_info("Creating Flame Graph Grid (Serially)")

    # Transform the commands into a tuple that we can index in a loop.
    if grid_cmds.baseline_target_difffolded:
        # Perl variant.
        cmds: tuple[str, str, str, str] = (
            grid_cmds.baseline,
            grid_cmds.target,
            f"{grid_cmds.baseline_target_difffolded} | {grid_cmds.baseline_target_fg_diff}",
            f"{grid_cmds.target_baseline_difffolded} | {grid_cmds.target_baseline_fg_diff}",
        )
    else:
        # Python variant.
        cmds = (
            grid_cmds.baseline,
            grid_cmds.target,
            grid_cmds.baseline_target_fg_diff,
            grid_cmds.target_baseline_fg_diff,
        )

    grid: FlameGraphGrid = FlameGraphGrid()
    for idx, (fg_cmd, tag) in enumerate(zip(cmds, FlameGraphGrid.EscapeTags)):
        # Execute the command and escape the resulting flamegraph.
        grid[idx] = commands.run_safely_external_command(fg_cmd)[0].decode("utf-8")
        if grid_cmds.escape_graphs:
            grid[idx] = escape_flamegraph_svg(tag, grid[idx])
        log.minor_success(FlameGraphGrid.DefaultTitles[idx], "generated")

    log.minor_success("Flamegraph grid", "completed")
    return grid


@contextlib.contextmanager
def build_flamegraph_grid(
    grid: FlameGraphGrid,
    grid_commands: FlameGraphGridCommands,
    parallelize: bool,
) -> Iterator[FlameGraphGridBuilder]:
    """Create a context manager for flamegraph grid serial or parallel builder.

    The context manager hides the specifics of building a flamegraph grid serially in a single
    process or in several parallel background processes.

    :param grid: [out] a reference to the grid object for the generated flamegraphs; context
               managers cannot explicitly return values, hence we use an output parameter
    :param grid_commands: the commands for generating a flamegraph grid
    :param parallelize: determines whether to build the grid serially or in parallel

    :return: the context manager wrapping the grid builder
    """
    creator = FlameGraphGridParallelBuilder if parallelize else FlameGraphGridSerialBuilder
    with creator(grid, grid_commands) as builder:
        yield builder


def build_flamegraph_grid_commands(
    baseline: Path,
    target: Path,
    settings: FlameGraphSettings,
    escape_svgs: bool,
    *new_flags: str,
    titles: tuple[str, str, str, str] = FlameGraphGrid.DefaultTitles,
    **override_kwargs: Any,
) -> FlameGraphGridCommands:
    """Create a collection of commands for generating a flamegraph grid.

    :param baseline: a path to the file with baseline folded flame graph data
    :param target: a path to the file with target folded flame graph data
    :param settings: flamegraph configuration parameters and flags
    :param escape_svgs: a flag indicating whether the SVGs should be escaped for HTML embedding
    :param new_flags: additional flags that should be passed to the flamegraph script
    :param titles: the titles of the respective flamegraphs
    :param override_kwargs: additional parameters that should extend or override the parameter
           values stored in the settings object

    :return: the flamegraph commands for generating a flamegraph grid
    """
    return FlameGraphGridCommands(
        escape_svgs,
        core.build_flamegraph_command(baseline, settings, titles[0], *new_flags, **override_kwargs),
        core.build_flamegraph_command(target, settings, titles[1], *new_flags, **override_kwargs),
        *core.build_diff_flamegraph_commands(
            target, baseline, settings, titles[2], "negate", *new_flags, **override_kwargs
        ),
        *core.build_diff_flamegraph_commands(
            baseline, target, settings, titles[3], *new_flags, **override_kwargs
        ),
    )


def escape_flamegraph_svg(tag: str, content: str, _tag_to_index: dict[str, int] = {}) -> str:
    """Escapes SVG content so that multiple flame graph may be embedded inside an HTML file.

    :param tag: the tag used to prefix the functions and ids
    :param content: the SVG content to escape
    :param _tag_to_index: a cache-like tag -> index mapping. Used to correctly replace calls to
           `getElementsByClassName("svg-content")` by
           `getElementsByClassName("svg-content")[<index>]`.
           The default value is mutable intentionally: this allows the caller to control the
           escaping per each generated HTML file.
    :return: the escaped content
    """
    tag_index = _tag_to_index.setdefault(tag, len(_tag_to_index))
    functions = [
        r"(?<!\w)(c)\(",
        r"(?<!\w)(get_params)\(",
        r"(?<!\w)(parse_params)\(",
        r"(?<!\w)(find_child)\(",
        r"(?<!\w)(find_group)\(",
        r"(?<!\w)(g_to_func)\(",
        r"(?<!\w)(g_to_text)\(",
        r"(?<!\w)(init)\(",
        r"(?<!\w)(orig_load)\(",
        r"(?<!\w)(orig_save)\(",
        r"(?<!\w)(reset_search)\(",
        r"(?<!\w)(reset_search_hover)\(",
        r"(?<!\w)(s)\(",
        r"(?<!\w)(search)\(",
        r"(?<!\w)(search_hover)\(",
        r"(?<!\w)(search_prompt)\(",
        r"(?<!\w)(find_frames)\(",
        r"(?<!\w)(searchout)\(",
        r"(?<!\w)(searchover)\(",
        r"(?<!\w)(clearzoom)\(",
        r"(?<!\w)(unzoom)\(",
        r"(?<!\w)(update_text)\(",
        r"(?<!\w)(zoom)\(",
        r"(?<!\w)(zoom_child)\(",
        r"(?<!\w)(zoom_parent)\(",
        r"(?<!\w)(zoom_reset)\(",
        r"(?<!\w)(toggleExclusive)\(",
        r"(?<!\w)(removeExclusiveView)\(",
        r"(?<!\w)(updateExclusiveView)\(",
        r"(?<!\w)(is_event_still_in_group)\(",
        r"(?<!\w)(is_hover_highlighted)\(",
        r"(?<!\w)(restore_frame_after_hover)\(",
        r"(?<!\w)(clear_hover_highlights)\(",
        r"(?<!\w)(apply_hover_highlight)\(",
        r"(?<!\w)(search_hover_show_stats)\(",
    ]
    other = [
        (r"\"search\"", f'"{tag}_search"'),
        (r"#search", f"#{tag}_search"),
        (r"\"background\"", f'"{tag}_background"'),
        (r"#background", f"#{tag}_background"),
        (r"\"frames\"", f'"{tag}_frames"'),
        (r"#frames", f"#{tag}_frames"),
        (r"#excToggle", f"#{tag}_excToggle"),
        (r"\"excToggle\"", f'"{tag}_excToggle"'),
        (r"#unzoom", f"#{tag}_unzoom"),
        (r"\"unzoom\"", f'"{tag}_unzoom"'),
        (r"\"matched\"", f'"{tag}_matched"'),
        (r"\"matchedhover\"", f'"{tag}_matchedhover"'),
        (r"details", f"{tag}_details"),
        (r"nameTypeLabel", f"{tag}_nameTypeLabel"),
        (r"inclusiveLabel", f"{tag}_inclusiveLabel"),
        (r"exclusiveLabel", f"{tag}_exclusiveLabel"),
        (r"matched", f"{tag}_matched"),
        (r"searchbtn", f"{tag}_searchbtn"),
        (r"unzoombtn", f"{tag}_unzoombtn"),
        (r"currentSearchTerm", f"{tag}_currentSearchTerm"),
        (r"hoverSearchTerm", f"{tag}_hoverSearchTerm"),
        (r"ignorecase", f"{tag}_ignorecase"),
        (r"ignorecaseBtn", f"{tag}_ignorecaseBtn"),
        (r"searching", f"{tag}_searching"),
        (r"matchedtxt", f"{tag}_matchedtxt"),
        (r"matchedHoverTxt", f"{tag}_matchedHoverTxt"),
        (r"exclusiveMode", f"{tag}_exclusiveMode"),
        (r"isDiff", f"{tag}_isDiff"),
        (r"svg\.", f"{tag}_svg."),
        (r"svg =", f"{tag}_svg ="),
        (r"svg,", f"{tag}_svg,"),
        (r">\s*\n<", r"><"),
        (
            r"getElementsByTagName\(\"svg\"\)\[0\]",
            f'getElementsByClassName("svg-content")[{tag_index}]',
        ),
        (r"document.", f"{tag}_svg."),
        (f"{tag}_svg.createElementNS", "document.createElementNS"),
        (
            f"({tag}_(svg|details|detailsName|detailsIncl|detailsExcl|matchedHoverCount|matchedHoverIncl|matchedHoverExcl|matchedSearchCount|matchedSearchIncl|matchedSearchExcl|nameTypeLabel|inclusiveLabel|exclusiveLabel|matchedHoverLabel|matchedSearchLabel|searchbtn|matchedtxt|matchedHoverTxt|ignorecaseBtn|unzoombtn)) = {tag}_svg.",
            "\\1 = document.",
        ),
        # Huge thanks to following article:
        # https://chartio.com/resources/tutorials/how-to-resize-an-svg-when-the-window-is-resized-in-d3-js/
        # Which helped to solve the issue with non-resizable flamegraphs
        (
            '<svg version="1.1" width="[0-9]+" height="[0-9]+"',
            '<svg version="1.1" preserveAspectRatio="xMinYMin meet" class="svg-content"',
        ),
    ]
    for func in functions:
        content = re.sub(func, f"{tag}_\\1(", content)
    for unit, sub in other:
        content = re.sub(unit, sub, content)
    return content
