perun_collect_complexity_dir = perun_collect_dir / 'complexity'

perun_collect_complexity_files = files(
    '__init__.py',
    'configurator.py',
    'makefiles.py',
    'run.py',
    'symbols.py',
)

py3.install_sources(
    perun_collect_complexity_files,
    subdir: perun_collect_complexity_dir,
)

install_subdir(
    'cpp_sources',
    install_dir: py3.get_install_dir() / perun_collect_complexity_dir,
    install_tag: 'python-runtime',
)

install_subdir(
    'lib',
    install_dir: py3.get_install_dir() / perun_collect_complexity_dir,
    install_tag: 'python-runtime',
)
