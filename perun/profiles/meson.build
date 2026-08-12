perun_profiles_dir = perun_dir / 'profiles'

perun_profiles_files = files(
    '__init__.py',
    '__init__.pyi',
)

py3.install_sources(
    perun_profiles_files,
    subdir: perun_profiles_dir,
)

subdir('native')
