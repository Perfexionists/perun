"""Functions for loading and working with streams (e.g. yaml)

Some of the stuff are stored in the stream, like e.g. yaml and are reused in several places.
This module encapulates such functions, so they can be used in CLI, in tests, in configs.
"""

import os
from ruamel.yaml import YAML

import perun.utils.log as log

__author__ = 'Tomas Fiedor'


def safely_load_yaml_from_file(yaml_file):
    """
    :param str yaml_file: name of the yaml file
    :raises ruamel.yaml.scanner.ScannerError: when the input file contains error
    """
    if not os.path.exists(yaml_file):
        log.warn('yaml source file \'{}\' does not exist'.format(yaml_file))
        return {}

    with open(yaml_file, 'r') as yaml_handle:
        return safely_load_yaml_from_stream(yaml_handle)


def safely_load_yaml_from_stream(yaml_stream):
    """
    :param str yaml_stream: stream in the yaml format (or not)
    :raises ruamel.yaml.scanner.ScannerError: when the input file contains error
    """
    # Remove the trailing double quotes screwing correct loading of yaml
    if isinstance(yaml_stream, str) and yaml_stream[0] == '"' and yaml_stream[-1] == '"':
        yaml_stream = yaml_stream[1:-1]
    loaded_yaml = YAML().load(yaml_stream)

    if not loaded_yaml and yaml_stream:
        log.warn('stream is not in yaml format')

    return loaded_yaml or {}


def safely_load_yaml(yaml_source):
    """Wrapper which takes the yaml source and either load it from the file or from the string

    :param str yaml_source: either string or name of the file
    :raises ruamel.yaml.scanner.ScannerError: when the input file contains error
    """
    if os.path.exists(yaml_source):
        return safely_load_yaml_from_file(yaml_source)
    else:
        return safely_load_yaml_from_stream(yaml_source)
