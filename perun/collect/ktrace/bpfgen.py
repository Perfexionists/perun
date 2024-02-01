from pathlib import Path

import jinja2


def generate_bpf_c(cmd_name: str, symbol_map: dict[str, int], ring_size: int) -> None:
    env = jinja2.Environment(loader=jinja2.PackageLoader("perun.collect.ktrace", "templates"))
    bpf_template = env.get_template("bpf_template_kprobes.c")
    content = bpf_template.render(
        bpfring_size=ring_size,
        command_len=len(cmd_name) + 1,
        command_cmp_len=len(cmd_name),
        command_name=cmd_name,
        symbols=symbol_map,
    )
    out_file = Path(Path(__file__).resolve().parent, "bpf_build", "ktrace.bpf.c")
    with open(out_file, "w+", encoding="utf-8") as bpf_out:
        bpf_out.write(content)
