perun_postprocess_regression_analysis_dir = perun_postprocess_dir / 'regression_analysis'

perun_postprocess_regression_analysis_files = files(
    '__init__.py',
    'data_provider.py',
    'derived.py',
    'generic.py',
    'methods.py',
    'regression_models.py',
    'run.py',
    'specific.py',
    'tools.py',
    'transform.py',
)

py3.install_sources(
    perun_postprocess_regression_analysis_files,
    subdir: perun_postprocess_regression_analysis_dir
)

subdir('extensions')
