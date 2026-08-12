perun_native_profile_dir = perun_profiles_dir / 'native'

perun_native_profile_files = files(
    '__init__.py',
    '__init__.pyi',
    'convert.py',
    'factory.py',
    'helpers.py',
    'imports.py',
    'query.py',
    'stats.py',
)

py3.install_sources(
    perun_native_profile_files,
    subdir: perun_native_profile_dir
)