perun_check_methods_dir = perun_check_dir / 'methods'

perun_check_methods_files = files(
    '__init__.py',
    'abstract_base_checker.py',
    'average_amount_threshold.py',
    'best_model_order_equality.py',
    'exclusive_time_outliers.py',
    'fast_check.py',
    'integral_comparison.py',
    'linear_regression.py',
    'local_statistics.py',
    'polynomial_regression.py',
)

py3.install_sources(
    perun_check_methods_files,
    subdir: perun_check_methods_dir,
)
