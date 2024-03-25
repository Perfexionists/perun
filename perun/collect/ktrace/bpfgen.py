"""
Generator of eBPF programs
"""
from __future__ import annotations

# Standard Imports
from pathlib import Path

# Third-Party Imports
import jinja2

# Perun Imports


def generate_bpf_c(cmd_names: list[str], symbol_map: dict[str, int], ring_size: int, include_main: bool = False) -> None:
    """Generates eBPF program for given command, symbol map and ring size

    Increasing ring size, will lead to higher memory usage,
    but might impact the throughput of handling events.

    :param cmd_names: list of profiled command
    :param symbol_map: map of functions to custom indexes for storing data
    :param ring_size: size of the ring buffer in the eBPF program
    :param include_main: flag whether the uprobe for main should be included or not
    """
    env = jinja2.Environment(loader=jinja2.PackageLoader("perun.collect.ktrace", "templates"))
    bpf_template = env.get_template("bpf_template_kprobes.c")
    content = bpf_template.render(
        bpfring_size=ring_size,
        command_names=cmd_names,
        symbols=symbol_map,
        include_main=include_main,
        main_id=len(symbol_map)
    )
    out_file = Path(Path(__file__).resolve().parent, "bpf_build", "ktrace.bpf.c")
    with open(out_file, "w+", encoding="utf-8") as bpf_out:
        bpf_out.write(content)
