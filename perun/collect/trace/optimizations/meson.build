perun_collect_trace_optimizations_dir = perun_collect_trace_dir / 'optimizations'

perun_collect_trace_optimizations_files = files(
    '__init__.py',
    'call_graph.py',
    'call_graph_levels.py',
    'cg_projection.py',
    'diff_tracing.py',
    'dynamic_baseline.py',
    'dynamic_sampling.py',
    'dynamic_stats.py',
    'optimization.py',
    'static_baseline.py',
    'structs.py',
)

py3.install_sources(
    perun_collect_trace_optimizations_files,
    subdir: perun_collect_trace_optimizations_dir,
)

subdir('resources')