""" Module for internal collector configuration file generator.

    The complexity collector library needs some specific configuration settings in order to work
    properly and efficiently. The library uses the ccicc.conf file to pass the configuration data
    at collector's runtime. The file format is specified in the ccicc.rst documentation

    This module handles all the necessary operations to create correct ccicc.conf file.

"""


import os
import json
import symbols


def create_ccicc(executable_path, runtime_filter, include_list, configuration):
    """ Creates the ccicc.conf configuration

    Arguments:
        executable_path(str): path to the executable which will use the configuration
        runtime_filter(list): function mangled names, which should be filtered at runtime
        include_list(list): list of function symbols(rule_key tuple) to be profiled
        configuration(dict): dictionary with configuration data

    Raises:
        OSError: if the ccicc file creation or opening failed
        ValueError: if the ccicc file is unexpectedly closed
    """
    # Open the file
    ccicc = _ccicc_create_file(executable_path)
    # Write the configuration settings
    _ccicc_write_config(ccicc, executable_path, runtime_filter, include_list, configuration)
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


def _ccicc_symbols_to_addresses(executable_path, runtime_filter, sample_map):
    """ Translates the identifiers in filter and sample configuration to their
        symbol table addresses

    Arguments:
        executable_path(str): path to the executable which will use the configuration
        runtime_filter(list): function mangled names, which should be filtered at runtime
        sample_map(dict): dict of sample configuration as 'mangled name: sample ratio'

    Returns:
        tuple: list of function addresses to be filtered at runtime
               dict of function addresses and sampling values
    """
    # Get the symbol:address
    symbol_map = symbols.extract_symbol_map(executable_path)
    # Translate the filter identifiers
    final_filter = []
    for func in runtime_filter:
        if func in symbol_map.keys():
            final_filter.append(int(symbol_map[func], 16))
    # Translate the sample identifiers
    final_sample = dict()
    for item in sample_map:
        if item in symbol_map:
            final_sample[int(symbol_map[item], 16)] = sample_map[item]
    return final_filter, final_sample


def _ccicc_write_config(ccicc_file, executable_path, runtime_filter, include_list, config):
    """ Writes the configuration stored in the config dictionary into the file

    Arguments:
        ccicc_file(file): file handle to the opened ccicc file
        executable_path(str): path to the executable which will use the configuration
        runtime_filter(list): addresses of functions to filter at runtime
        include_list(list): list of function symbols(rule_key tuple) to be profiled
        config(dict): dictionary with configuration data

    Raises:
        ValueError: if the ccicc file is unexpectedly closed
        TypeError: if the json serializing fails
    """
    sample_map = dict()
    # Create the translation table for identifiers
    if 'sampling' in config:
        sample_map = _ccicc_create_sample(include_list, config['sampling'])
    filter_list, sample_dict = _ccicc_symbols_to_addresses(executable_path, runtime_filter, sample_map)

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
        for sample_rule in sample_dict:
            conf['sampling'].append({'func': sample_rule, 'sample': sample_dict[sample_rule]})

    # Serializes the configuration dictionary to the proper ccicc format
    ccicc_file.write('CCICC = {0}'.format(json.dumps(conf, sort_keys=True, indent=2)))


def _ccicc_create_sample(include_list, sample_list):
    """ Creates the sample map as 'sample func mangled name: sample ratio' from the
        include list and sample list

    Arguments:
        include_list(list): list of rule_keys tuples
        sample_list(list): list of sampling rules (dictionaries)

    Returns:
        dict: the created sample map
    """
    sample_map = dict()
    # Try to pair the sample configuration and include list to create sample map 'mangled name: sample value'
    for sample in sample_list:
        # Unify the sampling function name to match the names in include list
        sample_name = symbols.unify_sample_func(sample['func'])
        for include_func in include_list:
            if include_func.rule == sample_name:
                # Sampling name and include list name match
                sample_map[include_func.mangled_name] = sample['sample']
                break
    return sample_map
