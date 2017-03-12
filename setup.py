from setuptools import setup, find_packages

setup(
    name='perun',
    version='0.1',
    py_modules=['perun'],
    packages=find_packages(),
    package_data = {'perun': ['collect/memory/malloc.so']},
    install_requires=[
        'click', 'termcolor', 'colorama', 'kivy', 'PyYAML'
    ],

    entry_points='''
        [console_scripts]
        perun=perun.view.cli:cli
    ''',
)
