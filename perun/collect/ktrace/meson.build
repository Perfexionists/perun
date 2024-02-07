perun_collect_ktrace_dir = perun_collect_dir / 'ktrace'

perun_collect_ktrace_files = files(
    '__init__.py',
    'bpfgen.py',
    'interpret.py',
    'run.py',
    'symbols.py'
)

py3.install_sources(
    perun_collect_ktrace_files,
    subdir: perun_collect_ktrace_dir,
)
