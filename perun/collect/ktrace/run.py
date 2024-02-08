"""Main module of the ktrace, which specifies its phases"""

# Standard Imports
from typing import Any
from pathlib import Path
import pickle
import time

# Third-Party Imports
import click

# Perun Imports
from perun.logic import runner
from perun.utils.external import commands, processes
from perun.utils.structs import CollectStatus
from perun.utils import log
from perun.collect.ktrace import symbols, bpfgen, interpret


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
    log.info("Discovering available and attachable symbols.")

    perf_symbols = symbols.parse_perf_events(kwargs["cmd_name"], kwargs["perf_report"])
    available_symbols = symbols.get_available_symbols(get_kernel(), kwargs["probe_type"])
    attachable_symbols = symbols.filter_available_symbols(
        perf_symbols, available_symbols, exclude=symbols.exclude_btf_deny()
    )

    log.info(f"Found {len(attachable_symbols)} attachable symbols.")
    if log.is_verbose_enough(log.VERBOSE_DEBUG):
        for func in attachable_symbols:
            log.info(f"  {func}")
    log.done()

    log.info("Creating and building the eBPF program", end="")
    kwargs["func_to_idx"], kwargs["idx_to_func"] = symbols.create_symbol_maps(attachable_symbols)
    bpfgen.generate_bpf_c(kwargs["cmd_name"], kwargs["func_to_idx"], kwargs["bpfring_size"])
    build_dir = Path(Path(__file__).resolve().parent, "bpf_build")
    commands.run_safely_external_command(f"make -C {build_dir}")
    log.done()

    result_filename = log.in_color(f"{build_dir}/ktrace", color="grey", attribute_style=["bold"])
    log.info(f"You can now run `{result_filename}`")

    return CollectStatus.OK, "", dict(kwargs)


def collect(**kwargs: Any) -> tuple[CollectStatus, str, dict[str, Any]]:
    """In collect, we run the eBPF program

    Note, that currently we wait for user to run the results manually

    :param kwargs: stash of shared values between the phases
    :return: collection status (error or OK), error message (if error happened) and shared parameters
    """
    ktrace_coloured = log.in_color("ktrace", color='yellow', attribute_style=['bold'])
    cmd_coloured = log.in_color(f"{kwargs['cmd_name']}")

    # First we wait for starting the ktrace
    log.info(f"You can now run the '{ktrace_coloured}' (yourself).")
    log.info(f"Waiting for {ktrace_coloured} to start", end='')
    while True:
        log.info('.', end='')

        if processes.is_process_running("ktrace"):
            log.info('')
            break
        time.sleep(BUSY_WAIT)

    log.info(f"{ktrace_coloured}: ", end='')
    log.tag("running", "green")

    log.info("")
    log.info(f"You can now run the '{cmd_coloured}' (yourself).")
    log.info(f"Waiting for {ktrace_coloured} to finish profiling '{cmd_coloured}'", end='')

    while True:
        log.info('.', end='')

        if not processes.is_process_running("ktrace"):
            log.info('')
            break
        time.sleep(BUSY_WAIT)

    log.info(f"Collection of '{cmd_coloured}'", end='')
    log.done()

    return CollectStatus.OK, "", dict(kwargs)


def after(**kwargs: Any) -> tuple[CollectStatus, str, dict[str, Any]]:
    """Creates performance profile based on the results"""
    log.info("Creating performance profile")

    raw_data_file = Path(Path(__file__).resolve().parent, "bpf_build", "output.log")
    output_file = Path(Path(__file__).resolve().parent, "bpf_build", "profile.csv")

    parsed_traces = interpret.parse_traces(raw_data_file, kwargs["idx_to_func"], interpret.FuncDataDetails)
    trace_data = interpret.traces_details_to_pandas(parsed_traces)
    trace_data.to_csv(output_file, index=False)

    log.info(f"Saving traces to {log.in_color('tracedata.pickle', color='grey', attribute_style=['bold'])}")
    with open("tracedata.pickle", "wb") as pickle_file:
        pickle.dump(parsed_traces, pickle_file)

    log.info(
        f"Intermediate data saved to '{log.in_color(str(output_file), 'grey', attribute_style=['bold'])}'"
    )

    resources = interpret.trace_details_to_resources(parsed_traces)
    kwargs['profile'] = {
        'global': {
            'time': parsed_traces.total_runtime,
            'resources': resources
        }
    }

    return CollectStatus.OK, "", dict(kwargs)


# def teardown():
#     pass


@click.command()
@click.argument("cmd-name")
@click.argument("perf-report", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--probe-type", "-s", type=click.Choice(["kprobe", "kfunc", "ftrace"]), default="kprobe"
)
@click.option("--bpfring-size", "-s", type=int, default=4096 * 4096)  # add checks
@click.pass_context
def ktrace(ctx, **kwargs):
    """Generates kernel traces for specific commands based on perf reports."""
    runner.run_collector_from_cli_context(ctx, "ktrace", kwargs)
