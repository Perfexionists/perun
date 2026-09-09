"""A module for generating a single Flame graph visualization."""

from __future__ import annotations

# Standard Imports
import pathlib
import tempfile
from typing import Any, Iterator, Optional

# Third-Party Imports

# Perun Imports
from perun.profiles import structs
from perun.profiles.folded import postprocess
from perun.utils.common import script_kit
from perun.utils.external import processes
from perun.utils.structs.view_structs import FlameGraphSettings


def generate_flamegraph(
    folded_stream: Iterator[tuple[str, int]],
    output_path: pathlib.Path,
    title: str,
    settings: FlameGraphSettings,
    postprocess_params: structs.PostprocessParameters,
) -> None:
    """Draws and saves a flamegraph to a file.

    :param folded_stream: an input stream of folded profile records (stack trace, consumption)
    :param output_path: a path to the output .svg file containing the flame graph
    :param title: the title of the flame graph
    :param settings: parameters forwarded to the flame graph scripts
    :param postprocess_params: profile postprocessing parameters
    """

    with tempfile.NamedTemporaryFile(mode="w+") as folded_file:
        for trace, count in postprocess.postprocess_folded_records(
            folded_stream, postprocess_params
        ):
            folded_file.write(f"{trace} {count}\n")
        folded_file.flush()
        fg_cmd = build_flamegraph_command(pathlib.Path(folded_file.name), settings, title)
        # TODO: hack. We want to redirect the output of the flamegraph script directly to file
        #  without storing it in a temporary string. Hence, we use a non-blocking subprocess helper
        #  which allows us to set the output pipe to a file handle.
        with (
            open(output_path, "w") as output_file,
            processes.nonblocking_subprocess(fg_cmd, {"stdout": output_file}),
        ):
            pass


def generate_title(profile_header: dict[str, Any]) -> str:
    """Generate a title for flame graph based on the profile header.

    :param profile_header: the profile header

    :return: the title of the flame graph
    """
    profile_type = profile_header["type"]
    cmd, workload = (profile_header["cmd"], profile_header["workload"])
    return f"{profile_type} consumption of {cmd} {workload}"


def build_flamegraph_command(
    input_path: Optional[pathlib.Path],
    settings: FlameGraphSettings,
    title: str,
    *new_flags: str,
    **override_kwargs: Any,
) -> str:
    """Create a command to generate a flame graph.

    :param input_path: a path to the file with folded flame graph data; may be omitted in which case
           the input data should be supplied to the flamegraph process via stdin
    :param settings: flamegraph configuration parameters and flags
    :param title: the title of the flame graph
    :param new_flags: additional flags that should be passed to the flamegraph script
    :param override_kwargs: additional parameters that should extend or override the parameter
           values stored in the settings object

    :return: the command for generating a flame graph
    """

    suffix = ".pl" if settings.use_perl else ".py"
    cmd = [
        script_kit.get_script(f"flamegraph{suffix}"),
        str(input_path) if input_path is not None else "",
        "--title",
        f"'{title}'",
    ]
    # Extend the command with parameters.
    cmd.extend(_add_flamegraph_params(settings, *new_flags, **override_kwargs))
    return " ".join(cmd)


def build_diff_flamegraph_commands(
    baseline: pathlib.Path,
    target: pathlib.Path,
    settings: FlameGraphSettings,
    title: str,
    *new_flags: str,
    **override_kwargs: Any,
) -> tuple[str, str]:
    """Create diffing and flamegraph commands to generate a differential flame graph.

    :param baseline: a path to the file with baseline folded flame graph data
    :param target: a path to the file with target folded flame graph data
    :param settings: flamegraph configuration parameters and flags
    :param title: the title of the flame graph
    :param new_flags: additional flags that should be passed to the flamegraph script
    :param override_kwargs: additional parameters that should extend or override the parameter
           values stored in the settings object

    :return: the difffolded and flamegraph commands for generating a differential flame graph
    """
    if settings.use_perl:
        normalize_flag = ""
        if settings.normalize or "normalize" in new_flags:
            normalize_flag = "-n"
        diff_cmd = f"{script_kit.get_script('difffolded.pl')} {normalize_flag} {baseline} {target}"
        fg_cmd = build_flamegraph_command(None, settings, title, *new_flags, **override_kwargs)
    else:
        diff_cmd = ""
        extended_flags = list(new_flags)
        if settings.normalize and "normalize" not in new_flags:
            extended_flags.append("normalize")
        # We take advantage of our diff_flamegraph helper script here.
        cmd = [
            script_kit.get_script("diff_flamegraph.py"),
            str(baseline),
            str(target),
            "--title",
            f"'{title}'",
        ]
        cmd.extend(_add_flamegraph_params(settings, *new_flags, **override_kwargs))
        fg_cmd = " ".join(cmd)
    return diff_cmd, fg_cmd


def _add_flamegraph_params(
    settings: FlameGraphSettings,
    *new_flags: str,
    **override_kwargs: Any,
) -> list[str]:
    """Construct a collection of flags and keyword arguments for a flamegraph script.

    :param settings: flamegraph configuration parameters and flags
    :param new_flags: additional flags that should be passed to the flamegraph script
    :param override_kwargs: additional parameters that should extend or override the parameter
           values stored in the settings object

    :return: a list of flags and parameters
    """
    params: list[str] = []
    # Extend the command with flags.
    flags: set[str] = set(new_flags)
    if settings.inverted and "inverted" not in new_flags:
        flags.add("inverted")
    params.extend(f"--{flag}" for flag in flags)

    # Extend the command with flamegraph parameters that have non-default values.
    # Although we could supply the parameters with default values as well, it would needlessly
    # clutter the resulting command.
    kw_params: dict[str, str | int] = settings.get_nondefault_kw_attributes()
    # The parameters may be overridden and extended by the caller.
    kw_params.update(override_kwargs)
    if settings.use_perl:
        # Sub-root is unsupported by Perl.
        del kw_params["subrootnode"]
    for key, val in kw_params.items():
        if val is not None:
            params.append(f"--{key}")
            params.append(f"'{val}'")
    return params
