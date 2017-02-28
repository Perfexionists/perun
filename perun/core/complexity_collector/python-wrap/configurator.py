""" Module for internal collector configuration file generator.

    The complexity collector library needs some specific configuration settings in order to work
    properly and efficiently. The library uses the ccicc.conf file to pass the configuration data
    at collector's runtime. The file format is specified in the ccicc.rst documentation

    This module handles all the necessary operations to create correct ccicc.conf file.

"""


import os
import json
from symbols import extract_symbol_map, translate_mangled_symbols


def create_ccicc(executable_path, runtime_filter, configuration):
    """ Creates the ccicc.conf configuration

    Arguments:
        executable_path(str): path to the executable which will use the configuration
        runtime_filter(list): addresses of functions to filter at runtime
        configuration(dict): dictionary with configuration data

    Raises:
        OSError: if the ccicc file creation or opening failed
        ValueError: if the ccicc file is unexpectedly closed
    """
    # Open the file
    ccicc = _ccicc_create_file(executable_path)
    # Write the configuration settings
    _ccicc_write_config(ccicc, executable_path, runtime_filter, configuration)
    ccicc.close()


def _ccicc_create_file(executable_path):
    """ Creates and/or opens the ccicc.conf file

    Arguments:
        executable_path(str): path to the executable which will use the configuration

    Returns:
        file: handle to the opened ccicc file

    Raises:
        OSError: if the ccicc file creation or opening failed
    """
    # Extract the executable directory for ccicc target
    path = os.path.realpath(executable_path)
    pos = path.rfind('/')
    path = path[:pos + 1]
    path += 'ccicc.conf'
    # Attempt to open the file
    file = open(path, 'w')
    return file


def _ccicc_translate_identifiers(executable_path, runtime_filter, sample):
    """ Translates the identifiers in filter and sample configuration to their
        symbol table addresses

    Arguments:
        executable_path(str): path to the executable which will use the configuration
        runtime_filter(list): addresses of functions to filter at runtime
        sample(list): list of sampling configuration dictionaries

    Returns:
        tuple: list of function addresses to be filtered at runtime
               dict of function demangled names and corresponding addresses for sampling
    """
    # TODO: Handle name ambiguity
    # TODO: Refactor
    # TODO: Collision in names?
    # Get the symbol : address and symbol : name maps
    symbol_map = extract_symbol_map(executable_path)
    name_map = translate_mangled_symbols(list(symbol_map.keys()))
    # Translate the filter identifiers
    final_filter = []
    for func in runtime_filter:
        if func in symbol_map.keys():
            final_filter.append(int(symbol_map[func], 16))
    # Translate the sample identifiers
    final_sample = dict()
    for item in sample:
        for name in name_map.keys():
            if item['func'] in name_map[name]:
                final_sample[item['func']] = int(symbol_map[name], 16)
                break
    return final_filter, final_sample


def _ccicc_write_config(ccicc_file, executable_path, runtime_filter, config):
    """ Writes the configuration stored in the config dictionary into the file

    Arguments:
        ccicc_file(file): file handle to the opened ccicc file
        executable_path(str): path to the executable which will use the configuration
        runtime_filter(list): addresses of functions to filter at runtime
        config(dict): dictionary with configuration data

    Raises:
        ValueError: if the ccicc file is unexpectedly closed
        TypeError: if the json serializing fails
    """
    sample = []
    # Create the translation table for identifiers
    if 'sampling' in config:
        sample = config['sampling']
    filter_list, sample_dict = _ccicc_translate_identifiers(executable_path, runtime_filter, sample)

    # Append the file name configuration
    conf = {'file-name': config['file-name']}
    # Append the storage size configuration
    if 'init-storage-size' in config:
        conf['init-storage-size'] = config['init-storage-size']
    # Append the runtime filter configuration
    if filter_list:
        conf['runtime-filter'] = filter_list
    # Append the sampling configuration
    if sample_dict:
        conf['sampling'] = []
        for sample_rule in config['sampling']:
            conf['sampling'].append({'func': sample_dict[sample_rule['func']], 'sample': sample_rule['sample']})

    # Serializes the configuration dictionary to the proper ccicc format
    ccicc_file.write('CCICC = {0}'.format(json.dumps(conf, sort_keys=True, indent=2)))
