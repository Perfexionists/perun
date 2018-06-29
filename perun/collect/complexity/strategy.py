""" Module with complexity collector strategies for tracing.

    The strategies are meant to be useful default settings for collection so that user
    does not have to specify every detail for each collection. The strategies focus on
    userspace / everything collection with sampling / no sampling etc.

    The assemble_script method serves as a interface which handles specifics of each strategy.
"""

import collections

import perun.utils.exceptions as exceptions
import perun.collect.complexity.systemtap_script as stap_script

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


def assemble_script(**kwargs):
    """Interface for the script assembling. Handles the specifics for each strategy.

    :param kwargs: the parameters to the collector as set by the cli

    :returns: str -- the path to the created script file
    """
    # Choose the handler for specified strategy
    script = _STRATEGIES[kwargs['method']](**kwargs)

    # Create the file and save the script
    script_path = 'collect_script_{0}.stp'.format(kwargs['timestamp'])
    with open(script_path, 'w') as stp_handle:
        stp_handle.write(script)
    return script_path


def custom_strategy(function, static, dynamic, binary, **_):
    """The custom strategy implementation. There are no defaults and only the parameters
    specified by the user are used for collection.

    :param list rules: the list of rules / functions used for tracing probes
    :param list of dict sampling: list of sampling specifications as dictionaries
    :param str cmd: the tracing target executable / process
    :param int global_sampling: the sampling value set globally for every rule

    :returns: str -- the script code
    """

    # Build sampling dictionary
    return stap_script.assemble_system_tap_script(function, static, dynamic, binary)


# TODO: add clever automatic pairing based on <name>_start:<name>_end
def _filter_static_probes(rules):
    dynamic, static = [], []
    for rule in rules:
        # Detect static rule and strip the static identifier
        if rule.startswith('s:'):
            rule = rule[2:]
            # Pair the static probes to start, end locations
            probes = rule.split(':')
            if len(probes) == 1:
                static.append((probes[0], probes[0]))
            elif len(probes) == 2:
                static.append((probes[0], probes[1]))
            else:
                continue
        else:
            dynamic.append(rule)


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

