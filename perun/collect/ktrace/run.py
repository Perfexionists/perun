from typing import Any
from pathlib import Path

import click

from perun.logic import runner
from perun.utils.external import commands
from perun.utils.structs import CollectStatus
from perun.utils import log
from perun.collect.ktrace import symbols, bpfgen, parser


def before(**kwargs: Any) -> tuple[CollectStatus, str, dict[str, Any]]:
    log.info("Symbol discovery phase.")
    perf_symbols = symbols.parse_perf_events(kwargs["cmd_name"], kwargs["perf_report"])
    strace_symbols = symbols.get_ftrace_symbols()
    kprobe_symbols = symbols.get_bpftrace_symbols("available_bpftrace_kprobe", "kprobe")
    kfunc_symbols = symbols.get_bpftrace_symbols("available_bpftrace_kfunc", "kfunc")
    attachable = symbols.filter_available_symbols(
        perf_symbols, kprobe_symbols, exclude=symbols.exclude_btf_deny()
    )
    log.info(f"Found {len(attachable)} attachable symbols.")
    for func in attachable:
        log.info(f"  {func}")
    kwargs["kernel_funcs"] = attachable
    return CollectStatus.OK, "", dict(kwargs)


def collect(**kwargs: Any) -> tuple[CollectStatus, str, dict[str, Any]]:
    kwargs["func_to_idx"], kwargs["idx_to_func"] = symbols.create_symbol_maps(kwargs["kernel_funcs"])
    bpfgen.generate_bpf_c(kwargs["cmd_name"], kwargs["func_to_idx"], kwargs["bpfring_size"])
    build_dir = Path(Path(__file__).resolve().parent, "bpf_build")
    commands.run_safely_external_command(f"make -C {build_dir}")
    return CollectStatus.OK, "", dict(kwargs)


def after(**kwargs: Any) -> tuple[CollectStatus, str, dict[str, Any]]:
    raw_data_file = Path(Path(__file__).resolve().parent, "bpf_build", "output.log")
    output_file = Path(Path(__file__).resolve().parent, "bpf_build", "profile.csv")
    if not raw_data_file.exists():
        return CollectStatus.ERROR, "No 'output.log' file. Please run the collection manually.", dict(kwargs)
    trace_data = parser.traces_details_to_pandas(
        parser.parse_traces(raw_data_file, kwargs["idx_to_func"], parser.FuncDataDetails)
    )
    trace_data.to_csv(output_file, index=False)
    return CollectStatus.OK, "", dict(kwargs)


# def teardown():
#     pass


@click.command()
@click.argument("cmd-name")
@click.argument("perf-report", type=click.Path(exists=True, path_type=Path))
@click.option("--bpfring-size", "-s", type=int, default=4096 * 4096)  # add checks
@click.pass_context
def ktrace(ctx, **kwargs):
    """Generates kernel traces for specific commands based on perf reports.

    """
    runner.run_collector_from_cli_context(ctx, "ktrace", kwargs)
