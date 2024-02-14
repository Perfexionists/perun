"""Collection of handing of eBPF primitives, i.e. symbols such as kprobes or kfuncs"""
from __future__ import annotations

# Standard Imports
from typing import Literal, Iterable, Collection
from pathlib import Path
import re
import subprocess

# Third-Party Imports

# Perun Imports
from perun.utils import log
from perun.utils.external import commands


KernelSymbolType = Literal["kprobe", "kfunc", "ftrace"]


def get_available_symbols(kernel: str, probe_type: KernelSymbolType) -> set[str]:
    """Obtains available symbols for profiling for given kernel and given probe_type

    :param kernel: identification of the kernel (as returned by `uname -r`)
    :param probe_type: type fo the probes, one of the ('ftrace', 'kprobe' or 'kfunc')
    :return: set of available symbols
    """
    # To obtain ftrace_symbols available to your system run the following:
    #     1. sudo cp /sys/kernel/tracing/available_filter_functions ./available_filter_functions;
    #     2. Change owner and permissions.
    if probe_type == "ftrace":
        return get_ftrace_symbols()
    # To obtain 'kprobes' or 'kfuncs' runs on of the following:
    #     1. sudo bpftrace -l 'kprobe:*' > available_bpftrace_kprobe
    #     2. sudo bpftrace -l 'kfunc:*' > available_bpftrace_func
    else:
        return get_bpftrace_symbols(f"symbols/{kernel}_bpftrace_{probe_type}", "kprobe")


def compute_perf_events(cmd: str, repeat: int, with_sudo: bool = False) -> list[str]:
    """Computes file with perf records

    We use the default frequency as we wish to collect as many events as we could.
    Brendan Gregg advises to use 99Hz frequency, however, this (anecdotally let to
    low number of events).

    Runs following two commands:
      1. perf record <CMD>
      2. perf report

    Note, on some systems the `with_sudo` should be set to True, otherwise the kernel events
    will not be profiled.

    :param cmd: command that is profiled by perf
    :param repeat: number of repeats of the run command
    :param with_sudo: whether the command should be run with sudo
    """
    log.minor_info(
        f"Collecting perf events {log.highlight(repeat)} times, with sudo={log.highlight(with_sudo)}"
    )
    sample_matcher = re.compile(r"\((\d+) samples\)")
    log.increase_indent()
    result = []
    for _ in range(0, repeat):
        try:
            perf_cmd = f"perf record {cmd}"
            if with_sudo:
                perf_cmd = f"sudo {perf_cmd}"
            _, err = commands.run_safely_external_command(perf_cmd)
            if match := sample_matcher.search(err.decode("utf-8")):
                log.minor_status("Collected", status=f"{log.success_highlight(match.group(1))}")
            else:
                log.minor_fail("Collected", "no samples")
            out, _ = commands.run_safely_external_command("perf report")
            result.extend(out.decode("utf-8").splitlines())
        except subprocess.CalledProcessError as err:
            log.warn(f"{log.cmd_style('perf record' + cmd)} returned error: {err}")
    log.decrease_indent()
    return result


def parse_perf_events(cmd_filter: str, perf_stream: Iterable[str]) -> set[str]:
    perf_functions: set[str] = set()
    for line in perf_stream:
        # Ignore comment or empty lines
        line = line.rstrip()
        if not line or line.startswith("#"):
            continue
        _, cmd, _, symbol_src, symbol_name = line.split()
        # Find kernel symbols related to the measured command
        if cmd == cmd_filter and symbol_src == "[k]":
            perf_functions.add(symbol_name)
    return perf_functions


def get_ftrace_symbols() -> set[str]:
    tracing_file = Path(Path(__file__).resolve().parent, "symbols/available_filter_functions")
    attachable: set[str] = set()
    with open(tracing_file, "r", encoding="utf-8") as attachable_handle:
        # The file is potentially big, read line by line
        for func in attachable_handle:
            attachable.add(func.rstrip())
    return attachable


def get_bpftrace_symbols(filename: str, probe_type: Literal["kfunc", "kprobe"]) -> set[str]:
    # TODO: invoke bpftrace directly.
    bpftrace_list_file = Path(Path(__file__).resolve().parent, filename)
    attachable: set[str] = set()
    probe_prefix = f"{probe_type}:"
    probe_prefix_len = len(probe_prefix)
    with open(bpftrace_list_file, "r", encoding="utf-8") as bpftrace_list_handle:
        for line in bpftrace_list_handle:
            if not line.startswith(probe_prefix):
                print(f"Warning: A bpftrace list entry is not {probe_type}!")
                continue
            # Get rid of the probe type prefix
            attachable.add(line.rstrip()[probe_prefix_len:])
    return attachable


def exclude_btf_deny() -> set[str]:
    # TODO: automate vmlinux extraction using objdump, e.g.:
    #  objdump -j .BTF_ids -x /usr/lib/debug/usr/lib/modules/5.17.6-300.fc36.x86_64/vmlinux | grep "deny" -A 20
    # TODO: or parse directly from online repo to have the most up-to-date exclude list?
    # For now, only a fixed list of functions
    return {
        "migrate_disable",
        "migrate_enable",
        "rcu_read_unlock_strict",
        "preempt_count_add",
        "preempt_count_sub",
        "__rcu_read_lock",
        "__rcu_read_unlock",
    }


def filter_available_symbols(
    perf_symbols: Collection[str],
    attachable_symbols: set[str],
    max_symbols: int = 0,
    exclude: set[str] | None = None,
) -> set[str]:
    if exclude is None:
        exclude = set()
    if max_symbols == 0:
        max_symbols = len(perf_symbols)
    filtered_symbols: set[str] = set()
    for p_symbol in perf_symbols:
        if p_symbol not in attachable_symbols or p_symbol in exclude:
            continue
        filtered_symbols.add(p_symbol)
        if len(filtered_symbols) >= max_symbols:
            break
    return filtered_symbols


def create_symbol_maps(symbols: set[str]) -> tuple[dict[str, int], dict[int, str]]:
    name_to_idx, idx_to_name = {}, {}
    # The symbol indexing must currently be deterministic across multiple runs
    for idx, symbol in enumerate(sorted(symbols)):
        name_to_idx[symbol] = idx
        idx_to_name[idx] = symbol
    return name_to_idx, idx_to_name
