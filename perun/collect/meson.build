perun_collect_dir = perun_dir / 'collect'

perun_collect_files = files(
    '__init__.py',
)

py3.install_sources(
    perun_collect_files,
    subdir: perun_collect_dir,
)

subdir('bounds')
subdir('complexity')
subdir('kperf')
subdir('memory')
subdir('time')
subdir('trace')