project(
    'perun',
    'c',
    version: '0.25.1',
    license: 'GPL-3',
    meson_version: '>=1.0.0',
    default_options: [
        'buildtype=debugoptimized',
        'c_std=c11',
        'optimization=2',
    ],
)

py3 = import('python').find_installation(pure: false)
py3_dep = py3.dependency()

perun_files = files(
    'LICENSE',
    'pyproject.toml',
    'tox.ini',
    'MANIFEST.in',
)

perun_dir = 'perun'

py3.install_sources(
    perun_files,
    subdir: perun_dir,
)

subdir('perun')
