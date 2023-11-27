perun_collect_trace_ebpf_dir = perun_collect_trace_dir / 'ebpf'

perun_collect_trace_ebpf_files = files(
    '__init__.py',
    'ebpf.py',
    'engine.py',
    'program.py',
)

py3.install_sources(
    perun_collect_trace_ebpf_files,
    subdir: perun_collect_trace_ebpf_dir,
)