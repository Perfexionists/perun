perun_postprocess_dir = perun_dir / 'postprocess'

perun_postprocess_files = files(
    '__init__.py',
)

py3.install_sources(
    perun_postprocess_files,
    subdir: perun_postprocess_dir
)

subdir('kernel_regression')
subdir('moving_average')
subdir('regression_analysis')
subdir('regressogram')
