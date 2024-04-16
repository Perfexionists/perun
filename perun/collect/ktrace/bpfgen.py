"""
Generator of eBPF programs
"""
from __future__ import annotations

# Standard Imports
from typing import Any
from pathlib import Path

# Third-Party Imports
import jinja2

# Perun Imports
from perun.utils import log


def render_template(template_src: str, template_dst: str, **kwargs: Any) -> None:
    """Renders the template for given arguments

    :param template_src: source file of template
    :param template_dst: target file of template
    :param kwargs: arguments for template
    """
    env = jinja2.Environment(loader=jinja2.PackageLoader("perun.collect.ktrace", "templates"))
    bpf_template = env.get_template(template_src)
    content = bpf_template.render(**kwargs)
    out_file = Path(Path(__file__).resolve().parent, "bpf_build", template_dst)
    with open(out_file, "w+", encoding="utf-8") as bpf_out:
        bpf_out.write(content)


def generate_sources_for_kprobes(
    cmd_names: list[str], symbol_map: dict[str, int], ring_size: int, include_main: bool = False
) -> None:
    """Generates eBPF program for given command, symbol map and ring size

    Increasing ring size, will lead to higher memory usage,
    but might impact the throughput of handling events.

    :param cmd_names: list of profiled command
    :param symbol_map: map of functions to custom indexes for storing data
    :param ring_size: size of the ring buffer in the eBPF program
    :param include_main: flag whether the uprobe for main should be included or not
    """
    render_template(
        "ktrace.bpf.c.jinja2",
        "ktrace.bpf.c",
        bpfring_size=ring_size,
        command_names=cmd_names,
        symbols=symbol_map,
        include_main=include_main,
        main_id=len(symbol_map),
    )
    log.minor_success(f"{log.path_style('ktrace.bpf.c')}", "generated")
    render_template("ktrace.c.jinja2", "ktrace.c")
    log.minor_success(f"{log.path_style('ktrace.c')}", "generated")
    render_template("ktrace.h.jinja2", "ktrace.h")
    log.minor_success(f"{log.path_style('ktrace.h')}", "generated")


def generate_sources_for_multi_probes(
    cmd_names: list[str], symbol_map: dict[str, int], ring_size: int, include_main: bool = False
) -> None:
    """Generates eBPF program for given command, symbol map and ring size

    This generates version for kprobes.multi

    :param cmd_names: list of profiled command
    :param symbol_map: map of functions to custom indexes for storing data
    :param ring_size: size of the ring buffer in the eBPF program
    :param include_main: flag whether the uprobe for main should be included or not
    """
    render_template(
        "multi_ktrace.bpf.c.jinja2",
        "ktrace.bpf.c",
        bpfring_size=ring_size,
        command_names=cmd_names,
        include_main=include_main
    )
    log.minor_success(f"{log.path_style('ktrace.bpf.c')}", "generated")
    render_template("multi_ktrace.c.jinja2", "ktrace.c", symbols=symbol_map)
    log.minor_success(f"{log.path_style('ktrace.c')}", "generated")
    render_template("multi_ktrace.h.jinja2", "ktrace.h")
    log.minor_success(f"{log.path_style('ktrace.h')}", "generated")
