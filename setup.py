from setuptools import setup, find_packages

setup(
    name='perun',
    version='0.1',
    py_modules=['perun'],
    packages=find_packages(),
    package_data={'perun': [
        'view/flamegraph/flamegraph.pl',
        'collect/memory/malloc.so'
    ]},
    install_requires=[
        'click', 'termcolor', 'colorama', 'ruamel.yaml', 'GitPython', 'bokeh', 'pandas',
        'demandimport', 'Sphinx', 'sphinx-click', 'Jinja2', 'python-magic', 'scipy', 'faker',
        'namedlist'
    ],

    entry_points='''
        [console_scripts]
        perun=perun.cli:cli
    ''',
)
