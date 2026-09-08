perun_conversions_profile_dir = perun_profiles_dir / 'conversions'

perun_conversions_profile_files = files(
    '__init__.py',
    '__init__.pyi',
    'elk_native.py',
    'folded_polars.py',
    'native_folded.py',
    'native_pandas.py',
    'native_polars.py',
    'perf_native.py',
    'polars_folded.py',
)

py3.install_sources(
    perun_conversions_profile_files,
    subdir: perun_conversions_profile_dir
)