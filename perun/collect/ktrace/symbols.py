from __future__ import annotations
from pathlib import Path

from typing import Literal


def parse_perf_events(cmd_filter: str, perf_file: Path) -> list[str]:
    perf_functions: list[str] = []
    with open(perf_file, "r", encoding="utf-8") as perf_handle:
        for line in perf_handle:
            # Ignore comment or empty lines
            line = line.rstrip()
            if not line or line.startswith("#"):
                continue
            _, cmd, _, symbol_src, symbol_name = line.split()
            # Find kernel symbols related to the measured command
            if cmd == cmd_filter and symbol_src == "[k]":
                perf_functions.append(symbol_name)
    return perf_functions


def get_ftrace_symbols() -> set[str]:
    tracing_file = Path(Path(__file__).resolve().parent, "available_filter_functions")
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
    perf_symbols: list[str],
    attachable_symbols: set[str],
    max_symbols: int = 0,
    exclude: set[str] | None = None
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
