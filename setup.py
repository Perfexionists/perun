from setuptools import setup, find_packages

setup(
    name='perun',
    version='0.1',
    py_modules=['perun'],
    packages=find_packages(),
    package_data={'perun': [
        'view/flamegraph/flamegraph.pl',
        'collect/memory/malloc.so',
        'collect/complexity/target/*.so',
        'collect/complexity/cpp_sources/*.{h,cpp}',
        'collect/complexity/cpp_sources/Makefile',
        'collect/complexity/cpp_sources/workload/*.{h,cpp,conf}'
    ]},
    install_requires=[
        'click', 'termcolor', 'colorama', 'ruamel.yaml', 'GitPython', 'bokeh', 'pandas',
        'demandimport', 'Sphinx', 'sphinx-click', 'Jinja2', 'python-magic', 'scipy'
    ],

    entry_points='''
        [console_scripts]
        perun=perun.cli:cli
    ''',
)
