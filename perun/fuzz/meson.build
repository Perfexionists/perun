perun_fuzz_dir = perun_dir / 'fuzz'

perun_fuzz_files = files(
    '__init__.py',
    'factory.py',
    'filesystem.py',
    'filetype.py',
    'helpers.py',
    'interpret.py',
    'randomizer.py',
    'structs.py',
)

py3.install_sources(
    perun_fuzz_files,
    subdir: perun_fuzz_dir
)

subdir('evaluate')
subdir('methods')