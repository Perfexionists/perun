""" Module for internal collector configuration file generator.

    The complexity collector library needs some specific configuration settings in order to work
    properly and efficiently. The library uses the circ.conf file to pass the configuration data
    at collector's runtime.

    This module handles all the necessary operations to create correct circ.conf file.

"""


import os
import json

from typing import TextIO, TypedDict

import perun.collect.complexity.symbols as symbols


# Default internal parameters
DEFAULT_DATA_FILENAME = 'trace.log'
DEFAULT_STORAGE_SIZE = 20000
DEFAULT_DIRECT_OUTPUT = False

_HEX_BASE = 16


class Configuration(TypedDict):
    target_dir: str
    internal_data_filename: str
    files: list[str]
    rules: list[str]
    profile: dict
    sampling: list[dict]
    internal_storage_size: int
    internal_direct_output: bool


def create_runtime_config(
        executable_path: str,
        runtime_filter: list[str],
        include_list: list[symbols.RuleKey],
        configuration: Configuration
):
    """ Creates the config.conf configuration

    :param str executable_path: path to the executable which will use the configuration
    :param list runtime_filter: function mangled names, which should be filtered at runtime
    :param list include_list: list of function symbols(rule_key tuple) to be profiled
    :param dict configuration: dictionary with configuration data
    """
    # Open the file
    config_path = os.path.join(os.path.dirname(executable_path), 'circ.conf')
    with open(config_path, 'w+') as config_handle:
        # Write the configuration settings
        _write_config_to(
            config_handle, executable_path, runtime_filter, include_list, configuration
        )


def _convert_symbols_to_addresses(
        executable_path: str, runtime_filter: list[str], sample_map: dict[str, int]
) -> tuple[list[int], dict[int, int]]:
    """ Translates the identifiers in filter and sample configuration to their
        symbol table addresses

    :param str executable_path: path to the executable which will use the configuration
    :param list runtime_filter: function mangled names, which should be filtered at runtime
    :param dict sample_map: dict of sample configuration as 'mangled name: sample ratio'

    :return tuple:  list of function addresses to be filtered at runtime
                    dict of function addresses and sampling values
    """
    # Get the symbol:address
    symbol_map = symbols.extract_symbol_map(executable_path)
    # Translate the filter identifiers
    final_filter = []
    for func in runtime_filter:
        if func in symbol_map.keys():
            final_filter.append(int(symbol_map[func], _HEX_BASE))
    # Translate the sample identifiers
    final_sample = dict()
    for item in sample_map:
        if item in symbol_map:
            final_sample[int(symbol_map[item], _HEX_BASE)] = sample_map[item]
    return final_filter, final_sample


def _write_config_to(
        config_handle: TextIO,
        executable_path: str,
        runtime_filter: list[str],
        include_list: list[symbols.RuleKey],
        job_settings: Configuration
):
    """ Writes the configuration stored in the config dictionary into the file

    :param file config_handle: file handle to the opened config file
    :param str executable_path: path to the executable which will use the configuration
    :param list runtime_filter: addresses of functions to filter at runtime
    :param list include_list: list of function symbols(rule_key tuple) to be profiled
    :param dict job_settings: dictionary with collect job configuration data
    """
    sample_map = dict()
    # Create the translation table for identifiers
    if 'sampling' in job_settings:
        sample_map = _create_sample_from(include_list, job_settings['sampling'])
    filter_list, sample_dict = _convert_symbols_to_addresses(
        executable_path, runtime_filter, sample_map
    )

    # Create the internal configuration
    internal_conf = {
        'internal_data_filename': job_settings.get('internal_data_filename', DEFAULT_DATA_FILENAME),
        'internal_storage_size': job_settings.get('internal_storage_size', DEFAULT_STORAGE_SIZE),
        'internal_direct_output': job_settings.get('internal_direct_output', DEFAULT_DIRECT_OUTPUT),
    }
    # Append the runtime filter configuration
    if filter_list:
        internal_conf['runtime_filter'] = filter_list
    # Append the sampling configuration
    if sample_dict:
        sampling = []
        for sample_rule in sample_dict:
            sampling.append({'func': sample_rule, 'sample': sample_dict[sample_rule]})
        internal_conf['sampling'] = sampling

    # Serializes the configuration dictionary to the proper circ format
    config_handle.write('CIRC = {0}'.format(json.dumps(internal_conf, sort_keys=True, indent=2)))


def _create_sample_from(
        include_list: list[symbols.RuleKey], sample_list: list[dict]
) -> dict[str, int]:
    """ Creates the sample map as 'sample func mangled name: sample ratio' from the
        include list and sample list

    :param list include_list: list of rule_keys tuples
    :param list sample_list: list of sampling rules (dictionaries)

    :return dict: the created sample map
    """
    sample_map = dict()
    # Try to pair the sample configuration and include list to create sample map
    # 'mangled name: sample value'
    for sample in sample_list:
        # Unify the sampling function name to match the names in include list
        sample_name = symbols.unify_sample_func(sample['func'])
        for include_func in include_list:
            if include_func.rule == sample_name:
                # Sampling name and include list name match
                sample_map[include_func.mangled_name] = sample['sample']
                break
    return sample_map
