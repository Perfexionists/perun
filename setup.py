from setuptools import setup, find_packages
import perun

setup(
    name='perun',
    version=perun.__version__,
    py_modules=['perun'],
    packages=find_packages(),
    package_data={'perun': [
        'view/flamegraph/flamegraph.pl',
        'collect/memory/malloc.so'
    ]},
    install_requires=[
        'click', 'termcolor', 'colorama', 'ruamel.yaml', 'GitPython', 'bokeh', 'pandas',
        'demandimport', 'Sphinx', 'sphinx-click', 'Jinja2', 'python-magic', 'scipy', 'faker',
        'distribute==0.7.3', 'PyQt-Fit==1.3.4'
    ],

    entry_points='''
        [console_scripts]
        perun=perun.cli:safely_run_cli
    ''',
)
