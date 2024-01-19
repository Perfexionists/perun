perun_utils_dir = perun_dir / 'utils'

perun_utils_files = files(
    '__init__.py',
    'decorators.py',
    'exceptions.py',
    'helpers.py',
    'log.py',
    'metrics.py',
    'script_helpers.py',
    'streams.py',
    'structs.py',
    'timestamps.py',
    'view_helpers.py',
)

py3.install_sources(
    perun_utils_files,
    subdir: perun_utils_dir
)

subdir('common')
subdir('external')
