"""Wrapper for trace collector, which collects profiling data about
running times for each of the specified functions or USDT markers in the code.

Specifies before, collect, after and teardown functions to perform the initialization,
collection and postprocessing of collection data.
"""

import time
import os

import click

from perun.collect.trace.strategy import extract_configuration
from perun.collect.trace.watchdog import WATCH_DOG
from perun.collect.trace.collect_engine import CollectEngine
from perun.collect.trace.configuration import Configuration
from perun.collect.trace.values import (
    OutputHandling,
    check,
    GLOBAL_DEPENDENCIES,
    Strategy,
)

import perun.logic.runner as runner
import perun.utils.log as stdout
import perun.utils.metrics as metrics
from perun.profile.factory import Profile
from perun.utils.structs import CollectStatus


def before(executable, **kwargs):
    """Validates, initializes and normalizes the collection configuration.

    :param Executable executable: full collection command with arguments and workload
    :param kwargs: dictionary containing the supplied configuration settings for the collector
    :returns: tuple (CollectStatus enum code,
                    string as a status message, mainly for error states,
                    dict of kwargs (possibly with some new values))
    """
    WATCH_DOG.header("Pre-processing phase...")
    # Check if we run in a workload generator batch and update metrics accordingly
    if executable.workload != executable.origin_workload:
        metrics.Metrics.add_sub_id(executable.workload)

    metrics.start_timer("total_time")
    kwargs["total_time"] = time.time()
    # Validate and normalize collection parameters
    config = Configuration(executable, **kwargs)
    # This makes the resources available even if 'before' fails and kwargs is not updated
    kwargs["opened_resources"].append(config)
    kwargs["config"] = config  # Alias for easier access to the Configuration object
    kwargs["probes"] = config.probes
    # Init the engine object that contains collection resource
    config.engine_factory()

    # Initialize the watchdog and log the kwargs dictionary after it's fully initialized
    WATCH_DOG.start_session(config.watchdog, config.pid, config.timestamp, config.quiet)

    # Check all the required dependencies
    check(GLOBAL_DEPENDENCIES)
    config.engine.check_dependencies()

    # Extract and / or post-process the collect configuration
    extract_configuration(config.engine, kwargs["probes"])
    if not kwargs["probes"].func and not kwargs["probes"].usdt:
        msg = (
            "No profiling probes created (due to invalid specification, failed extraction or "
            "filtering)"
        )
        return CollectStatus.ERROR, msg, dict(kwargs)

    # Set the variables for optimization methods
    kwargs["binary"] = config.binary

    # Cleanup the kwargs and log all the dictionaries
    WATCH_DOG.log_variable("before::kwargs", kwargs)
    WATCH_DOG.log_variable("before::kwargs::config", config.__dict__)
    WATCH_DOG.log_variable("before::kwargs::probes", kwargs["probes"].__dict__)

    return CollectStatus.OK, "", dict(kwargs)


def collect(**kwargs):
    """Assembles the engine collect program according to input parameters and collection strategy.
    Runs the created collection program and the profiled command.

    :param kwargs: dictionary containing the configuration and probe settings for the collector
    :returns: tuple (CollectStatus enum code,
                    string as a status message, mainly for error states,
                    dict of kwargs (possibly with some new values))
    """
    WATCH_DOG.header("Collect phase...")
    config = kwargs["config"]

    # Assemble the collection program according to the parameters
    metrics.add_metric("func_count", len(config.probes.func.keys()))
    config.engine.assemble_collect_program(**kwargs)

    # Run the collection program and profiled command
    metrics.start_timer("collect_time")
    config.engine.collect(**kwargs)
    metrics.end_timer("collect_time")

    return CollectStatus.OK, "", dict(kwargs)


def after(**kwargs):
    """Parses the trace collector output and transforms it into profile resources

    :param kwargs: the configuration settings for the collector
    :returns: tuple (CollectStatus enum code,
                    string as a status message, mainly for error states,
                    dict of kwargs (possibly with some new values))
    """
    WATCH_DOG.header("Post-processing phase... ")

    # Inform the user
    WATCH_DOG.info(
        "Processing raw performance data. Note that this may take a while for large raw data files."
    )
    data_size = os.stat(kwargs["config"].engine.data).st_size
    metrics.add_metric("data_size", data_size)
    WATCH_DOG.info(f"Raw data file size: {stdout.format_file_size(data_size)}")

    # Dirty temporary hack
    if kwargs["config"].engine.name == "ebpf":
        kwargs["profile"] = Profile()
        kwargs["profile"].update_resources(
            {"resources": list(kwargs["config"].engine.transform(**kwargs))}, "global"
        )
    else:
        kwargs["profile"] = kwargs["config"].engine.transform(**kwargs)

    WATCH_DOG.info("Data processing finished.")
    return CollectStatus.OK, "", dict(kwargs)


def teardown(**kwargs):
    """Perform a cleanup of all the collection resources that need it, i.e. files, locks,
    processes, kernel modules etc.

    :param kwargs: the configuration settings for the collector
    :returns: tuple (CollectStatus enum code,
                    string as a status message, mainly for error states,
                    dict of kwargs (possibly with some new values))
    """
    WATCH_DOG.header("Teardown phase...")

    # The Configuration object can be directly in kwargs or the resources list
    config = None
    if "config" in kwargs:
        config = kwargs["config"]
    elif kwargs["opened_resources"]:
        config = kwargs["opened_resources"][0]
        kwargs["config"] = config

    # Cleanup all the engine related resources
    # Check that the engine was actually constructed
    if config is not None and not isinstance(config.engine, str):
        config.engine.cleanup(**kwargs)

    metrics.end_timer("total_time")
    # metrics.save()
    return CollectStatus.OK, "", dict(kwargs)


@click.command()
@click.option(
    "--engine",
    "-e",
    type=click.Choice(CollectEngine.available()),
    default=CollectEngine.default(),
    help=(
        "Sets the data collection engine to be used:\n"
        " - stap: the SystemTap framework\n"
        " - ebpf: the eBPF framework"
    ),
)
@click.option(
    "--strategy",
    "-s",
    type=click.Choice(Strategy.supported()),
    default=Strategy.default(),
    required=True,
    help=(
        "Select strategy for probing the binary. See documentation for"
        " detailed explanation for each strategy."
    ),
)
@click.option(
    "--func",
    "-f",
    type=str,
    multiple=True,
    help="Set the probe point for the given function as <lib>#<func>#<sampling>.",
)
@click.option(
    "--usdt",
    "-u",
    type=str,
    multiple=True,
    help="Set the probe point for the given USDT location as <lib>#<usdt>#<sampling>.",
)
@click.option(
    "--dynamic",
    "-d",
    type=str,
    multiple=True,
    help="Set the probe point for the given dynamic location as <lib>#<cl>#<sampling>.",
)
@click.option(
    "--global-sampling",
    "-g",
    type=int,
    default=1,
    help=(
        "Set the global sample for all probes, sampling parameter for specific"
        " rules have higher priority."
    ),
)
@click.option(
    "--with-usdt/--no-usdt",
    default=True,
    help="The selected strategy will also extract and profile USDT probes.",
)
@click.option(
    "--binary",
    "-b",
    type=click.Path(exists=True),
    help=(
        "The profiled executable. If not set, then the command is considered "
        "to be the profiled executable and is used as a binary parameter."
    ),
)
@click.option(
    "--libs",
    "-l",
    nargs=1,
    required=False,
    multiple=True,
    type=click.Path(exists=True),
    help="Additional libraries that should also be profiled.",
)
@click.option(
    "--timeout",
    "-t",
    type=float,
    default=0,
    help=(
        "Set time limit (in seconds) for the profiled command, i.e. the command will be "
        "terminated after reaching the time limit. Useful for, e.g., endless commands."
    ),
)
@click.option(
    "--zip-temps",
    "-z",
    is_flag=True,
    default=False,
    help=(
        "Zip and compress the temporary files (SystemTap log, raw performance data, "
        "watchdog log, etc.) into the Perun log directory before deleting them."
    ),
)
@click.option(
    "--keep-temps",
    "-k",
    is_flag=True,
    default=False,
    help="Do not delete the temporary files in the file system.",
)
@click.option(
    "--verbose-trace",
    "-vt",
    is_flag=True,
    default=False,
    help="Set the trace file output to be more verbose, useful for debugging.",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    default=False,
    help="Reduces the verbosity of the collector info messages.",
)
@click.option(
    "--watchdog",
    "-w",
    is_flag=True,
    default=False,
    help="Enable detailed logging of the whole collection process.",
)
@click.option(
    "--output-handling",
    "-o",
    type=click.Choice(OutputHandling.to_list()),
    default=OutputHandling.DEFAULT.value,
    help=(
        "Sets the output handling of the profiled command:\n"
        " - default: the output is displayed in the terminal\n"
        " - capture: the output is being captured into a file as well as displayed"
        " in the terminal (note that buffering causes a delay in the terminal output)\n"
        " - suppress: redirects the output to the DEVNULL"
    ),
)
@click.option(
    "--diagnostics",
    "-i",
    is_flag=True,
    default=False,
    help=(
        "Enable detailed surveillance mode of the collector. The collector turns on "
        "detailed logging (watchdog), verbose trace, capturing output etc. and stores "
        "the logs and files in an archive (zip-temps) in order to provide as much "
        "diagnostic data as possible for further inspection."
    ),
)
@click.option(
    "--stap-cache-off",
    "-sc",
    is_flag=True,
    default=False,
    help="Disables the SystemTap caching of compiled scripts.",
)
@click.option(
    "--no-profile",
    "-np",
    is_flag=True,
    default=False,
    help="Tracer will not transform and save processed data into a perun profile.",
)
# TODO: temporary
@click.option(
    "--extract-mixed-cg",
    "-mcg",
    is_flag=True,
    default=False,
    help="DEBUG: Extract mixed CG.",
)
@click.option(
    "--only-extract-cg",
    "-cg",
    is_flag=True,
    default=False,
    help="Tracer will only extract the CG of the current project version and terminate.",
)
@click.option(
    "--max-simultaneous-threads",
    "-mt",
    type=int,
    default=5,
    help="DEBUG: Maximum number of expected simultaneous threads when sampling is on.",
)
@click.option(
    "--no-ds-update",
    "-nds",
    is_flag=True,
    default=False,
    help="DEBUG: Disables Dynamic Stats updates",
)
@click.pass_context
def trace(ctx, **kwargs):
    """Generates `trace` performance profile, capturing running times of
    function depending on underlying structural sizes.

    \b
      * **Limitations**: C/C++ binaries
      * **Metric**: `mixed` (captures both `time` and `size` consumption)
      * **Dependencies**: ``SystemTap`` (+ corresponding requirements e.g. kernel -dbgsym version)
      * **Default units**: `us` for `time`, `element number` for `size`

    Example of collected resources is as follows:

    .. code-block:: json

        \b
        {
            "amount": 11,
            "subtype": "time delta",
            "type": "mixed",
            "uid": "SLList_init(SLList*)",
            "structure-unit-size": 0
        }

    Trace collector provides various collection *strategies* which are supposed to provide
    sensible default settings for collection. This allows the user to choose suitable
    collection method without the need of detailed rules / sampling specification. Currently
    supported strategies are:

    \b
      * **userspace**: This strategy traces all userspace functions / code blocks without
        the use of sampling. Note that this strategy might be resource-intensive.
      * **all**: This strategy traces all userspace + library + kernel functions / code blocks
        that are present in the traced binary without the use of sampling. Note that this strategy
        might be very resource-intensive.
      * **u_sampled**: Sampled version of the **userspace** strategy. This method uses sampling
        to reduce the overhead and resources consumption.
      * **a_sampled**: Sampled version of the **all** strategy. Its goal is to reduce the
        overhead and resources consumption of the **all** method.
      * **custom**: User-specified strategy. Requires the user to specify rules and sampling
        manually.

    Note that manually specified parameters have higher priority than strategy specification
    and it is thus possible to override concrete rules / sampling by the user.

    The collector interface operates with two seemingly same concepts: (external) command
    and binary. External command refers to the script, executable, makefile, etc. that will
    be called / invoked during the profiling, such as 'make test', 'run_script.sh', './my_binary'.
    Binary, on the other hand, refers to the actual binary or executable file that will be profiled
    and contains specified functions / USDT probes etc. It is expected that the binary will be
    invoked / called as part of the external command script or that external command and binary are
    the same.

    The interface for rules (functions, USDT probes) specification offers a way to specify
    profiled locations both with sampling or without it. Note that sampling can reduce the
    overhead imposed by the profiling. USDT rules can be further paired - paired rules act
    as a start and end point for time measurement. Without a pair, the rule measures time
    between each two probe hits. The pairing is done automatically for USDT locations with
    convention <name> and <name>_end or <name>_END - or other commonly found suffixes.
    Otherwise, it is possible to pair rules by the delimiter '#', such as <name1>#<name2>.

    Trace profiles are suitable for postprocessing by
    :ref:`postprocessors-regression-analysis` since they capture dependency of
    time consumption depending on the size of the structure. This allows one to
    model the estimation of trace of individual functions.

    Scatter plots are suitable visualization for profiles collected by
    `trace` collector, which plots individual points along with regression
    models (if the profile was postprocessed by regression analysis). Run
    ``perun show scatter --help`` or refer to :ref:`views-scatter` for more
    information about `scatter plots`.

    Refer to :ref:`collectors-trace` for more thorough description and
    examples of `trace` collector.
    """
    runner.run_collector_from_cli_context(ctx, "trace", kwargs)
