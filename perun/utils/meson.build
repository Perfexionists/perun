perun_utils_dir = perun_dir / 'utils'

perun_utils_files = files(
    '__init__.py',
    'decorators.py',
    'exceptions.py',
    'log.py',
    'metrics.py',
    'streams.py',
    'structs.py',
    'timestamps.py',
)

py3.install_sources(
    perun_utils_files,
    subdir: perun_utils_dir
)

subdir('common')
subdir('external')
