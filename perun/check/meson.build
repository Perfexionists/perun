perun_check_dir = perun_dir / 'check'

perun_check_files = files(
    '__init__.py',
    'factory.py',
    'detection_kit.py',
    'nonparam_kit.py',
)

py3.install_sources(
    perun_check_files,
    subdir: perun_check_dir,
)

subdir('methods')
