"""Collection of global methods for delta debugging.
https://www.debuggingbook.org/html/DeltaDebugger.html
"""

from __future__ import annotations

import subprocess
import tempfile
import os
from perun.utils.external import commands as external_commands
from perun.utils import log
from typing import Any, TYPE_CHECKING
from pathlib import Path
from perun.utils.common import common_kit
from perun.fuzz.evaluate.by_perun import target_testing
from typing import Iterable

from perun.fuzz.structs import Mutation

if TYPE_CHECKING:
    from perun.profile.factory import Profile
    from perun.utils.structs.common_structs import Executable, MinorVersion, CollectStatus, Job


def run_delta_debugging_for_command(
    executable: Executable,
    **kwargs: Any,
) -> None:
    output_dir = Path(kwargs["output_dir"]).resolve()
    kwargs["is_fuzzing"] = False
    debugged_input = delta_debugging_algorithm(executable, **kwargs)
    log.minor_info("shortest failing input = " + debugged_input)
    input_sample = kwargs["input_sample"]
    create_debugging_file(output_dir, input_sample, debugged_input)


def delta_debugging_algorithm(executable: Executable, is_fuzzing: bool, **kwargs: Any) -> str:
    n = 2  # granularity
    inp = read_input(is_fuzzing, **kwargs)
    while len(inp) >= 2:
        start = 0
        subset_length = int(len(inp) / n)
        program_fails = False
        while start < len(inp):
            complement = inp[: int(start)] + inp[int(start + subset_length) :]
            if is_fuzzing:
                program_fails = run_with_fuzzing(executable, complement, **kwargs)
            else:
                program_fails = run_command_with_input(executable, complement, **kwargs)
            if program_fails:
                inp = complement
                n = max(n - 1, 2)
                break
            start += subset_length

        if not program_fails:
            if n == len(inp):
                break
            n = min(n * 2, len(inp))
    return inp


def run_with_fuzzing(
    executable: Executable,
    complement: str,
    mutation: Mutation,
    collector: str,
    postprocessor: list[str],
    minor_version_list: list[MinorVersion],
    base_result: Iterable[tuple[CollectStatus, Profile, Job]],
    **kwargs: Any,
) -> bool:
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(complement.encode())
        temp_file.flush()
        input_variation = Mutation(temp_file.name, mutation.history, mutation.predecessor)
        program_fails = target_testing(
            executable,
            input_variation,
            collector,
            postprocessor,
            minor_version_list,
            base_result,
            **kwargs,
        )
        if program_fails:
            os.remove(mutation.path)
            mutation.path = temp_file.name
        else:
            os.remove(temp_file.name)
        return program_fails


def run_command_with_input(executable: Executable, complement: str, **kwargs: Any) -> bool:
    timeout = kwargs.get("timeout", 1.0)
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(complement.encode())
        temp_file.flush()

    try:
        full_cmd = f"{executable} {temp_file.name}"
        external_commands.run_safely_external_command(full_cmd, True, True, timeout)
        os.remove(temp_file.name)

    except subprocess.TimeoutExpired:
        return True

    return False


def read_input(is_fuzzing: bool, **kwargs: Any) -> str:
    if is_fuzzing:
        mutation = kwargs.get("mutation")
        if mutation is None:
            raise ValueError("Got unexpected mutation")
        input_file = mutation.path
    else:
        input_file = kwargs.get("input_sample", "")

    input_path = Path(input_file)
    if input_path.is_file():
        with open(input_path, "r") as file:
            input_value = file.read()
    else:
        input_value = input_file

    return input_value


def create_debugging_file(output_dir: Path, file_name: str, input_data: str) -> None:
    output_dir = output_dir.resolve()
    dir_name = "delta_debugging"
    full_dir_path = output_dir / dir_name
    file_path = Path(file_name)
    common_kit.touch_dir(str(full_dir_path))
    file_path = full_dir_path / file_path.name

    with open(file_path, "w") as file:
        file.write(input_data)
