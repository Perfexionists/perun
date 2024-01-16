perun_collect_trace_optimizations_resources_dir = perun_collect_trace_optimizations_dir / 'resources'

perun_collect_trace_optimizations_resources_files = files(
    '__init__.py',
    'angr_provider.py',
    'manager.py',
    'perun_call_graph.py',
    'perun_dynamic_stats.py',
)

py3.install_sources(
    perun_collect_trace_optimizations_resources_files,
    subdir: perun_collect_trace_optimizations_resources_dir,
)
