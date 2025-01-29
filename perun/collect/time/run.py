"""A wrapper of the classical time linux utility.

Time collects the runtime of given commands with repetition of the measurements. First we do a
several warm-up executions, followed by the actual timing.
"""

from __future__ import annotations

# Standard Imports
import sys
from typing import Any
import time as systime

# Third-Party Imports
import click

# Perun Imports
from perun.logic import runner
from perun.utils import log
from perun.utils.common import common_kit
from perun.utils.external import commands
from perun.utils.structs.common_structs import CollectStatus, Executable


TIME_TYPES = ("real", "user", "sys")


def collect(
    executable: Executable, repeat: int = 10, warmup: int = 3, **_: Any
) -> tuple[CollectStatus, str, dict[str, Any]]:
    """Times the runtime of the given command, with stated repeats.

    :param executable: executed command, with arguments and workloads
    :param warmup: number of warm-up phases, i.e. number of times the binary will be run, but
        the resulting collection will not be stored
    :param repeat: number of repeats of the timing, by default 10
    :param _: dictionary with key, value options
    :return:
    """
    time_executable = "time"
    if sys.platform == "darwin":
        # On macOS, GNU time executable is called 'gtime'
        time_executable = "gtime"
    log.major_info("Running time collector")
    log.minor_info("Warming up")
    for __ in log.progress(range(0, warmup), description="Warmup"):
        command = " ".join([f"{time_executable} -p", str(executable)]).split(" ")
        commands.get_stdout_from_external_command(
            command, log_tag="warmup", log_verbosity=log.VERBOSE_RELEASE
        ).split("\n")
    log.newline()

    log.minor_info(f"Timing {executable.cmd} {common_kit.str_to_plural(repeat, 'time')}")
    times = []

    before_timing = systime.time()
    for timing in log.progress(range(1, repeat + 1), description="Main Run"):
        command = " ".join([f"{time_executable} -p", str(executable)]).split(" ")
        collected_data = commands.get_stdout_from_external_command(
            command, log_tag="main_run", log_verbosity=log.VERBOSE_RELEASE
        ).split("\n")

        times.extend(
            [
                (timing, t[0], t[1])
                for t in map(lambda x: x.split(" "), collected_data)
                if len(t) == 2 and t[0] in TIME_TYPES
            ]
        )
    log.newline()
    overall_time = systime.time() - before_timing

    return (
        CollectStatus.OK,
        "",
        {
            "profile": {
                "global": {
                    "timestamp": overall_time,
                    "resources": [
                        {
                            "amount": float(timing),
                            "uid": executable.cmd,
                            "order": order,
                            "subtype": key,
                            "type": "time",
                        }
                        for (order, key, timing) in times
                    ],
                }
            }
        },
    )


@click.command()
@click.option(
    "--warmup",
    "-w",
    "warmup",
    default=3,
    nargs=1,
    type=click.INT,
    metavar="<int>",
    help="Before the actual timing, the collector will execute <int> warm-up executions.",
)
@click.option(
    "--repeat",
    "-r",
    default=10,
    nargs=1,
    type=click.INT,
    metavar="<int>",
    help="The timing of the given binaries will be repeated <int> times.",
)
@click.pass_context
def time(ctx: click.Context, **kwargs: Any) -> None:
    """Generates `time` performance profile, capturing overall running times of
    the profiled command.

    \b
      * **Limitations**: `none`
      * **Metric**: running `time`
      * **Dependencies**: `none`
      * **Default units**: `s`

    This is a wrapper over the ``time`` linux utility and captures resources
    in the following form:

    .. code-block:: json

        \b
        {
            "amount": 0.59,
            "type": "time",
            "subtype": "sys",
            "uid": cmd
            "order": 1
        }

    Refer to :ref:`collectors-time` for more thorough description and examples
    of `trace` collector.
    """
    runner.run_collector_from_cli_context(ctx, "time", kwargs)
