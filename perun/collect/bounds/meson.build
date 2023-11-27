perun_collect_bounds_dir = perun_collect_dir / 'bounds'

perun_collect_bounds_files = files(
    '__init__.py',
    'parser.py',
    'run.py',
)

libedit_2_dep = dependency('libedit', version: ['>=2.0.0', '<3.0.0'], required: false)

#if libedit_2_dep.found()
  py3.install_sources(
      perun_collect_bounds_files,
      subdir: perun_collect_bounds_dir,
  )

  install_subdir(
      'bin',
      install_dir: py3.get_install_dir() / perun_collect_bounds_dir,
      install_tag: 'python-runtime',
  )
  #endif
