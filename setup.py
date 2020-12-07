from setuptools import setup, find_packages
import perun

setup(
    name='perun',
    version=perun.__version__,
    py_modules=['perun'],
    packages=find_packages(),
    package_data={'perun': [
        'view/flamegraph/flamegraph.pl',
        'collect/memory/malloc.so',
        'collect/bounds/bin/*',
        'collect/complexity/cpp_sources/*',
        'collect/complexity/lib/*',
        'templates/*',
        '../requirements.txt'
    ]},
    install_requires=[
        'click', 'termcolor', 'colorama', 'ruamel.yaml', 'GitPython', 'bokeh', 'pandas',
        'demandimport', 'Sphinx', 'sphinx-click', 'Jinja2', 'python-magic', 'faker',
    ],

    entry_points='''
        [console_scripts]
        perun=perun.cli:run_cli
    ''',
)
