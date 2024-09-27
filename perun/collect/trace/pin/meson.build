perun_collect_trace_pin_dir = perun_collect_trace_dir / 'pin'

perun_collect_trace_pin_files = files(
    '__init__.py',
    'engine.py',
    'scan_binary.py',
)

py3.install_sources(
    perun_collect_trace_pin_files,
    subdir: perun_collect_trace_pin_dir,
)

subdir('parse')
