perun_profiles_dir = perun_dir / 'profiles'

perun_profiles_files = files(
    '__init__.py',
    '__init__.pyi',
    'imports.py',
    'stats.py',
    'structs.py',
    'utils.py',
)

py3.install_sources(
    perun_profiles_files,
    subdir: perun_profiles_dir,
)

subdir('conversions')
subdir('folded')
subdir('native')
subdir('polars')
