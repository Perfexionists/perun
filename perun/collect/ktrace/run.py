"""Main module of the ktrace, which specifies its phases"""
import subprocess

# Standard Imports
from typing import Any
from pathlib import Path
import time

# Third-Party Imports
import click

# Perun Imports
from perun.collect.kperf import run as kperf
from perun.collect.ktrace import symbols, bpfgen, interpret
from perun.logic import runner
from perun.utils import log
from perun.utils.common import script_kit
from perun.utils.external import commands, processes
from perun.utils.structs import CollectStatus


BUSY_WAIT: int = 5


def get_kernel():
    """Returns the identification of the kernel

    TODO: this is temporary here, later this should be extracted to perun.utils.common.environment
    :return: identification of the kernel
    """
    out, _ = commands.run_safely_external_command("uname -r")
    return out.decode("utf-8").strip()


def before(**kwargs: Any) -> tuple[CollectStatus, str, dict[str, Any]]:
    """In before function we collect available symbols, filter them and prepare the eBPF program"""
    log.major_info("Creating the profiling program")

    log.minor_info("Discovering available and attachable symbols")
    if kwargs["perf_report"] is None:
        if kwargs["executable"] is None:
            log.error(
                "cannot collect perf events without executable. Run collection again with `-c cmd`."
            )
        perf_symbols = set()
        for precollect_program in kwargs["precollect_symbols_by"]:
            if precollect_program == 'perf':
                log.minor_status(
                    "Source of perf events",
                    status=f"{log.cmd_style('perf record ' + str(kwargs['executable']) + '; perf report')}",
                )
                perf_output = symbols.compute_perf_events(
                    str(kwargs["executable"]), kwargs["repeat_perf"], kwargs["with_sudo"]
                )
                perf_symbols.update(symbols.parse_perf_events(kwargs["cmd_names"], perf_output))
            elif precollect_program == 'kperf':
                for _ in range(0, kwargs["repeat_perf"]):
                    log.increase_indent()
                    perf_output = kperf.run_perf(kwargs['executable'], kwargs['with_sudo'])
                    for out in perf_output.split("\n"):
                        if out.strip():
                            trace, _ = out.split(" ")
                            perf_symbols.update(trace.split(';'))
                    log.decrease_indent()
    else:
        log.minor_status("Source of perf events", status=f"{log.path_style(kwargs['perf_report'])}")
        with open(kwargs["perf_report"], "r", encoding="utf-8") as perf_handle:
            perf_symbols = symbols.parse_perf_events(kwargs["cmd_names"], perf_handle)
    log.minor_success(f"Parsing sampled {log.highlight('perf')} events")

    log.increase_indent()
    available_symbols = symbols.get_available_symbols(get_kernel(), kwargs["probe_type"])
    attachable_symbols = symbols.filter_available_symbols(
        perf_symbols, available_symbols, exclude=symbols.exclude_btf_deny()
    )

    len_no = len(attachable_symbols)
    if len_no > 0:
        len_str = log.in_color(f"{len_no}", "green", attribute_style=["bold"])
    else:
        len_str = log.in_color(f"{len_no}", "red", attribute_style=["bold"])
    log.minor_info(f"found {len_str} attachable symbols")
    log.decrease_indent()
    if log.is_verbose_enough(log.VERBOSE_DEBUG) and len_no > 0:
        log.minor_info("Listing available probes")
        log.increase_indent()
        for func in sorted(attachable_symbols):
            log.minor_info(f"{func}")
        log.decrease_indent()

    kwargs["func_to_idx"], kwargs["idx_to_func"] = symbols.create_symbol_maps(attachable_symbols)
    log.minor_success("Generating the source of the eBPF program")

    bpfgen.generate_bpf_c(kwargs["cmd_names"], kwargs["func_to_idx"], kwargs["bpfring_size"])
    build_dir = Path(Path(__file__).resolve().parent, "bpf_build")
    commands.run_safely_external_command(f"make -C {build_dir}")
    log.minor_success("Building the eBPF program")

    return CollectStatus.OK, "", dict(kwargs)


def collect(**kwargs: Any) -> tuple[CollectStatus, str, dict[str, Any]]:
    """In collect, we run the eBPF program

    Note, that currently we wait for user to run the results manually

    :param kwargs: stash of shared values between the phases
    :return: collection status (error or OK), error message (if error happened) and shared parameters
    """
    log.major_info("Collecting performance data")

    # First we wait for starting the ktrace
    log.minor_info(f"waiting for {log.highlight('ktrace')} to start", end="")
    while True:
        log.tick()

        if processes.is_process_running("ktrace"):
            log.newline()
            break
        time.sleep(BUSY_WAIT)

    log.minor_success(f"{log.highlight('ktrace')}", "running")

    failed_reason = ""
    if kwargs["executable"]:
        if script_kit.may_contains_script_with_sudo(str(kwargs["executable"])):
            failed_reason = "the command might require sudo"
            log.minor_fail("Running the workload")
        else:
            try:
                commands.run_safely_external_command(str(kwargs["executable"]))
                log.minor_success("Running the workload", "finished")
            except (subprocess.CalledProcessError, FileNotFoundError) as exc:
                failed_reason = f"the called process failed: {exc}"
                log.minor_fail("Running the workload")
    else:
        log.minor_fail("Running the workload", "skipped")
        failed_reason = "command was not provided on CLI"
    if failed_reason:
        log.minor_info(f"The workload has to be run manually, since {failed_reason}", end="\n")

    log.minor_info(
        f"waiting for {log.highlight('ktrace')} to finish profiling {log.cmd_style(', '.join(kwargs['cmd_names']))}",
        end="",
    )

    while True:
        log.tick()

        if not processes.is_process_running("ktrace"):
            log.newline()
            break
        time.sleep(BUSY_WAIT)

    log.minor_success(f"collecting data for {log.cmd_style(', '.join(kwargs['cmd_names']))}")

    return CollectStatus.OK, "", dict(kwargs)


def after(**kwargs: Any) -> tuple[CollectStatus, str, dict[str, Any]]:
    """Creates performance profile based on the results"""
    log.major_info("Creating performance profile")

    raw_data_file = Path(Path(__file__).resolve().parent, "bpf_build", "output.log")
    output_file = Path(Path(__file__).resolve().parent, "bpf_build", "profile.csv")

    profile_output_type = kwargs["output_profile_type"]
    save_intermediate = kwargs["save_intermediate_to_csv"]

    if profile_output_type == "flat":
        flat_parsed_traces = interpret.parse_traces(
            raw_data_file, kwargs["idx_to_func"], interpret.FuncDataFlat
        )
        trace_data = interpret.traces_flat_to_pandas(flat_parsed_traces)
        if save_intermediate:
            trace_data.to_csv(output_file, index=False)
        resources = interpret.pandas_to_resources(trace_data)
        total_runtime = flat_parsed_traces.total_runtime
    elif profile_output_type == "details":
        detailed_parsed_traces = interpret.parse_traces(
            raw_data_file, kwargs["idx_to_func"], interpret.FuncDataDetails
        )
        trace_data = interpret.traces_details_to_pandas(detailed_parsed_traces)
        resources = interpret.pandas_to_resources(trace_data)
        total_runtime = detailed_parsed_traces.total_runtime
        if save_intermediate:
            trace_data.to_csv(output_file, index=False)
    else:
        assert profile_output_type == "clustered"
        detailed_parsed_traces = interpret.parse_traces(
            raw_data_file, kwargs["idx_to_func"], interpret.FuncDataDetails
        )
        resources = interpret.trace_details_to_resources(detailed_parsed_traces)
        total_runtime = detailed_parsed_traces.total_runtime
    log.minor_success("generating profile")

    if not resources:
        log.warn("no resources were generated (probably due to empty file?)")
    if save_intermediate and profile_output_type != "clustered":
        log.minor_status(f"intermediate data saved", f"{log.cmd_style(str(output_file))}")
    kwargs["profile"] = {"global": {"time": total_runtime, "resources": resources}}
    return CollectStatus.OK, "", dict(kwargs)


# def teardown():
#     pass


@click.command()
@click.argument("cmd-names", required=True, nargs=-1)
@click.option(
    "--with-sudo",
    "-ws",
    default=False,
    is_flag=True,
    help="Whether some commands should be run with sudo or not",
)
@click.option(
    "--repeat-perf",
    "-rp",
    default=5,
    type=click.INT,
    help="How many times should the perf sampling be repeated",
)
@click.option(
    "--perf-report",
    "-pr",
    default=None,
    type=click.Path(exists=True, path_type=Path),
    help="File with collected perf events; if not set, then the events will be collected several times.",
)
@click.option(
    "--probe-type",
    "-p",
    type=click.Choice(["kprobe", "kfunc", "ftrace"]),
    default="kprobe",
    help="type of probes in resulting eBPF program",
)
@click.option(
    "--bpfring-size",
    "-s",
    type=int,
    default=4096 * 4096 * 10,
    help="Size of the ring buffer used in eBPF program. Increasing the size will lead to lesser number of lost events.",
)  # add checks
@click.option(
    "--output-profile-type",
    "-t",
    type=click.Choice(["clustered", "details", "flat"]),
    default="flat",
    help="type of the resulting profile; clustered has highest granularity, flat has lowest granularity.",
)
@click.option(
    "--save-intermediate-to-csv",
    "-c",
    is_flag=True,
    type=bool,
    default=False,
    help="Saves the intermediate results into some file",
)
@click.option(
    "--precollect-symbols-by",
    "-ps",
    multiple=True,
    type=click.Choice(["perf", "kperf"]),
    default=("kperf", "perf"),
    help="Precollects symbols that will be instrumented by selected profiler. "
         "`perf` collects only topmost functions from stack; "
         "`kperf` collects all functions in traces on stack.",
)
@click.pass_context
def ktrace(ctx, **kwargs):
    """Generates kernel traces for specific commands based on perf reports."""
    runner.run_collector_from_cli_context(ctx, "ktrace", kwargs)
