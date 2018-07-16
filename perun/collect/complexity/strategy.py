""" Module with complexity collector strategies for tracing.

    The strategies are meant to be useful default settings for collection so that user
    does not have to specify every detail for each collection. The strategies focus on
    userspace / everything collection with sampling / no sampling etc.

    The assemble_script method serves as a interface which handles specifics of each strategy.
"""

import collections
import os

import perun.utils.exceptions as exceptions

# The default global sampling for 'sample' strategies if global sampling is not set
_DEFAULT_SAMPLE = 5


def get_supported_strategies():
    """Provides list of supported strategies.

    :returns: list -- the names of supported strategies
    """
    return list(_STRATEGIES.keys())


def get_default_strategy():
    """Provides the name of the default collector strategy.

    :returns: str -- the name of the default strategy used
    """
    return 'custom'


def extract_configuration(**kwargs):
    """Interface for the script assembling. Handles the specifics for each strategy.

    :param kwargs: the parameters to the collector as set by the cli

    :returns: str -- the path to the created script file
    """
    # Choose the handler for specified strategy
    return _STRATEGIES[kwargs['method']](**kwargs)


def custom_strategy(func, func_sampled, static, static_sampled, dynamic, dynamic_sampled, **kwargs):
    """The custom strategy implementation. There are no defaults and only the parameters
    specified by the user are used for collection.

    :param list rules: the list of rules / functions used for tracing probes
    :param list of dict sampling: list of sampling specifications as dictionaries
    :param str cmd: the tracing target executable / process
    :param int global_sampling: the sampling value set globally for every rule

    :returns: str -- the script code
    """

    kwargs['func'] = _remove_duplicate_probes(_merge_probes_lists(
        func, func_sampled, kwargs['global_sampling']))
    kwargs['static'] = _remove_duplicate_probes(_pair_rules(_merge_probes_lists(
        static, static_sampled, kwargs['global_sampling'])))
    kwargs['dynamic'] = _remove_duplicate_probes(_pair_rules(_merge_probes_lists(
        dynamic, dynamic_sampled, kwargs['global_sampling'])))

    # Build sampling dictionary
    return kwargs


def _pair_rules(probes):
    result = []
    for probe in probes:
        # Split the probe definition into pair or probes
        delim = probe['name'].find('#')
        if delim != -1:
            probe['pair'] = probe['name'][delim + 1:]
            probe['name'] = probe['name'][:delim]
            result.append(probe)
        elif probe['name'].endswith('_end') or probe['name'].endswith('_END'):
            # Skip the end probes
            continue
        else:
            # Find the pair probe automatically as <name>_end template
            pair = next((pair_probe for pair_probe in probes if (pair_probe['name'] == probe['name'] + '_end' or
                                                                 pair_probe['name'] == probe['name'] + '_END')), None)
            if pair:
                probe['pair'] = pair['name']
            result.append(probe)
    return result


def _merge_probes_lists(probes, probes_sampled, global_sampling):
    # Add global sampling (default 0) to the probes without sampling specification
    probes = [{'name': probe, 'sample': global_sampling} for probe in probes]

    # Validate the sampling values and merge the lists
    for probe in probes_sampled:
        if probe[1] < 2:
            probes.append({'name': probe[0], 'sample': global_sampling})
        else:
            probes.append({'name': probe[0], 'sample': probe[1]})
    return probes


# TODO: allow the probe to be used in multiple pairs e.g. TEST+TEST_END, TEST+TEST_END2, requires modification of
# the script generator
def _remove_duplicate_probes(probes):
    # Classify the rules into paired, paired with sampling, single and single with sampling
    paired, paired_sampled, single, single_sampled = [], [], [], []
    for probe in probes:
        if probe['sample'] > 0:
            (paired_sampled if 'pair' in probe else single_sampled).append(probe)
        else:
            (paired if 'pair' in probe else single).append(probe)

    seen = set()
    unique = []
    # Prioritize paired rules - we can't afford to remove paired rule instead of a single rule
    # Also prioritize sampled rules
    for paired_rules in [paired_sampled, paired]:
        for probe in paired_rules:
            if probe['name'] not in seen and probe['pair'] not in seen:
                # Add new unique rule
                seen.add(probe['name'])
                seen.add(probe['pair'])
                unique.append(probe)

    # Now add single rules that are not duplicate
    for single_rules in [single_sampled, single]:
        for probe in single_rules:
            if probe['name'] not in seen:
                # Add new unique rule
                seen.add(probe['name'])
                unique.append(probe)

    return unique


def _not_implemented(method, **_):
    """Placeholder function for strategies that are not implemented and should not be used.

    :param str method: the name of the method that is being requested
    """
    raise exceptions.StrategyNotImplemented(method)


# The strategies names and their implementation
_STRATEGIES = collections.OrderedDict([
    ('userspace', _not_implemented),
    ('all', _not_implemented),
    ('u_sampled', _not_implemented),
    ('a_sampled', _not_implemented),
    ('custom', custom_strategy)
])

