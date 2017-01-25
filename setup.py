from setuptools import setup, find_packages

setup(
    name='perun',
    version='0.1',
    py_modules=['perun'],
    packages=find_packages(),
    install_requires=[
        'Click',
    ],
    entry_points='''
        [console_scripts]
        perun=perun.view.cli:cli
    ''',
)
