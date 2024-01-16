perun_view_dir = perun_dir / 'view'

perun_view_files = files(
    '__init__.py',
)

py3.install_sources(
    perun_view_files,
    subdir: perun_view_dir
)

subdir('bars')
subdir('flamegraph')
subdir('flow')
subdir('scatter')
subdir('tableof')