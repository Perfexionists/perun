perun_collect_trace_dir = perun_collect_dir / 'trace'

perun_collect_trace_files = files(
    '__init__.py',
    'collect_engine.py',
    'configuration.py',
    'probes.py',
    'processes.py',
    'run.py',
    'strategy.py',
    'threads.py',
    'values.py',
    'watchdog.py',
)

py3.install_sources(
    perun_collect_trace_files,
    subdir: perun_collect_trace_dir,
)

subdir('ebpf')
subdir('optimizations')
subdir('systemtap')