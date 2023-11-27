perun_workload_dir = perun_dir / 'workload'

perun_workload_files = files(
    '__init__.py',
    'external_generator.py',
    'generator.py',
    'integer_generator.py',
    'singleton_generator.py',
    'string_generator.py',
    'textfile_generator.py',
)

py3.install_sources(
    perun_workload_files,
    subdir: perun_workload_dir
)