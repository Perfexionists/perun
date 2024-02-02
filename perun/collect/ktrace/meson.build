perun_collect_ktrace_dir = perun_collect_dir / 'ktrace'

perun_collect_ktrace_files = files(
    '__init__.py',
    'bpfgen.py',
    'parser.py',
    'run.py',
    'symbols.py'
)

py3.install_sources(
    perun_collect_ktrace_files,
    subdir: perun_collect_ktrace_dir,
)
