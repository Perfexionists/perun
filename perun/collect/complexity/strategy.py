""" Module with complexity collector strategies for tracing.

    The strategies are meant to be useful default settings for collection so that user
    does not have to specify every detail for each collection. The strategies focus on
    userspace / everything collection with sampling / no sampling etc.

    Using the strategies, one can automatically extract collection configuration from target
    executable(s) and / or postprocess the configuration (such as remove duplicate rules,
    pair static rules, merge the sampled / non-sampled rules etc.)

    extract_configuration serves as a recommended module interface
"""

import collections
import shutil
from enum import IntEnum

import perun.utils.exceptions as exceptions
import perun.utils as utils
import perun.utils.log as log


class _Status(IntEnum):
    OK = 0,
    STAP_DEP = 1,
    NM_DEP = 2,
    AWK_DEP = 3


# The default global sampling for 'sample' strategies if global sampling is not set
_DEFAULT_SAMPLE = 20


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

    The output dictionary is updated as follows:
     - func, static, dynamic: contains prepared rules for profiling with unified sampling specification
       - the rules are stored as lists of dictionaries with keys 'name', 'sample' and optionally 'pair' for
         rules that can be paired (such as static or dynamic rules)

    :param list func: the list of function names that will be traced
    :param list func_sampled: the list of function names with specified sampling
    :param list static: the list of static probes that will be traced
    :param list static_sampled: the list of static probes with specified sampling
    :param list dynamic: the list of dynamic probes that will be traced
    :param list dynamic_sampled: the list of dynamic probes with specified sampling
    :param kwargs: additional configuration parameters

    :returns kwargs: the updated dictionary with post processed rules
    """

    # Remove duplicate rules, merge sampled / non-sampled rule lists and optionally pair the rules
    kwargs['func'] = _remove_duplicate_probes(_merge_probes_lists(
        func, func_sampled, kwargs['global_sampling']))
    kwargs['static'] = _remove_duplicate_probes(_pair_rules(_merge_probes_lists(
        static, static_sampled, kwargs['global_sampling'])))
    kwargs['dynamic'] = _remove_duplicate_probes(_pair_rules(_merge_probes_lists(
        dynamic, dynamic_sampled, kwargs['global_sampling'])))

    # Build sampling dictionary
    return kwargs


def extraction_strategy(func, func_sampled, static, static_sampled, **kwargs):
    """The userspace, all, u_sampled and a_sampled strategy implementation. No manual configuration of profiled
    locations is required and is instead automatically extracted from the provided binary according to the specific
    strategy. However the user can specify additional rules, that have higher priority than the extracted ones.

    The output dictionary is updated as follows:
     - func, static: contains prepared rules for profiling with unified sampling specification
       - the rules are stored as lists of dictionaries with keys 'name', 'sample' and optionally 'pair' for
         rules that can be paired (such as static or dynamic rules)

    :param list func: the list of function names that will be traced
    :param list func_sampled: the list of function names with specified sampling
    :param list static: the list of static probes that will be traced
    :param list static_sampled: the list of static probes with specified sampling
    :param kwargs: additional configuration parameters

    :returns kwargs: the updated dictionary with post processed rules
    """
    # Apply global sampling for sampled strategies
    if (kwargs['method'] == 'u_sampled' or kwargs['method'] == 'a_sampled') and kwargs['global_sampling'] == 0:
        kwargs['global_sampling'] = _DEFAULT_SAMPLE

    # Create probe locations: process separately user supplied and extracted locations, then merge them
    kwargs['func'] = _merge_extracted_with_custom(
        _remove_duplicate_probes(_extract_functions(**kwargs)),
        _remove_duplicate_probes(_merge_probes_lists(func, func_sampled, kwargs['global_sampling'])))
    kwargs['static'] = _merge_extracted_with_custom(
        _remove_duplicate_probes(_pair_rules(_extract_static_probes(**kwargs))),
        _remove_duplicate_probes(_pair_rules(_merge_probes_lists(static, static_sampled, kwargs['global_sampling']))))

    return kwargs


def _pair_rules(probes):
    """Pairs the rules according to convention:
     - rule names with '#' serving as a delimiter between two probes, which should be paired as a starting and
       ending probe
     - rules with <name>_end or <name>_END are paired with corresponding <name> probes

     :param list probes: the list of probes (as dicts) that should be paired
     :returns list: probe dictionaries with optionally added 'pair' key containing paired probe name
    """
    result = []
    for probe in probes:
        # Split the probe definition into pair or probes
        delim = probe['name'].find('#')
        if delim != -1:
            probe['pair'] = probe['name'][delim + 1:]
            probe['name'] = probe['name'][:delim]
            result.append(probe)
        elif not probe['name'].endswith('_end') and not probe['name'].endswith('_END'):
            # Find the pair probe automatically as <name>_end template
            pair = next((pair_probe for pair_probe in probes if (pair_probe['name'] == probe['name'] + '_end' or
                                                                 pair_probe['name'] == probe['name'] + '_END')), None)
            if pair:
                probe['pair'] = pair['name']
            result.append(probe)
    return result


def _merge_probes_lists(probes, probes_sampled, global_sampling):
    """Merges the probe lists without and with specified sampling into one list with unified sampling specification

    :param list probes: list of strings that represent probe names
    :param list probes_sampled: list of tuples that contain 0) probe name, 1) probe sampling
    :param global_sampling: the global sampling value that is applied to all probes without sampling
    :return list: list of probes in unified format (dictionaries with 'name' and 'sample' keys)
    """
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
    """Removes duplicate rules / probes using following technique:
     1) probes are classified into paired, paired with sampling, single and single with sampling
     2) sampled rules across paired and single rules are prioritized
     3) paired rules are prioritized over single rules

    :param list probes: the list of probes as a dictionaries
    :return list: the list of unique probes
    """
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


def _merge_extracted_with_custom(extracted, custom):
    """Merges extracted probe locations with user-specified ones, where the extracted have lower priority and can be
    overwritten by the user supplied rules.

    :param list extracted: list of extracted probes represented as a dictionaries
    :param list custom: list of user-specified probes represented also as a dictionaries
    :return list: the resulting list of merged probe locations
    """
    # Custom has higher priority than extracted
    seen = set()
    for probe in custom:
        seen.add(probe['name'])
    for probe in extracted:
        if probe['name'] not in seen:
            custom.append(probe)
    return custom


def _extract_functions(binary, method, global_sampling, **_):
    """Extracts function symbols from the supplied binary.

    :param str binary: path to the binary file
    :param str method: name of the applied extraction strategy
    :param int global_sampling: the sampling value applied to all extracted function locations
    :return list: extracted function symbols stored as a probes = dictionaries
    """
    # Check if nm and awk utils are available, both are needed for the extraction
    if not _check_dependency('nm') or not _check_dependency('awk'):
        return []
    user = method == 'userspace' or method == 'u_sampled'

    # Extract user function symbols from the supplied binary
    awk_filter = '$2 == "T"' if user else '$2 == "T" || $2 == "W"'
    output, _ = utils.run_safely_external_command(
        'nm -P {bin} | awk \'{filt} {{print $1}}\''.format(bin=binary, filt=awk_filter))
    output = output.decode('utf-8')

    # Transform to the desired format
    if user:
        return [{'name': func, 'sample': global_sampling} for func in output.splitlines() if _filter_user_symbol(func)]
    else:
        return [{'name': func, 'sample': global_sampling} for func in output.splitlines()]


def _extract_static_probes(binary, global_sampling, **kwargs):
    """Extract static probe locations from the supplied binary file.

    :param str binary: path to the binary file
    :param int global_sampling: the sampling value applied to all extracted static probe locations
    :return list: extracted static locations stored as a probes = dictionaries
    """
    # Check if static symbols are desired and stap is present
    if not kwargs['with_static'] or not _check_dependency('stap'):
        return []

    # Extract the static probe locations from the binary, note: stap -l returns code '1' if there are no static probes
    output, _ = utils.run_safely_external_command('sudo stap -l \'process("{bin}").mark("*")\''.format(bin=binary),
                                                  False)
    output = output.decode('utf-8')

    # There are no static probes in the binary
    if not output or output.lstrip(' ').startswith('Tip:'):
        return []

    # Transform
    return [{'name': probe, 'sample': global_sampling} for probe in _static_probe_filter(output)]


def _static_probe_filter(static_list):
    """Cut the static probe location name from the extract output.

    :param str static_list: the extraction output
    :return object: generator object that provides the static probe locations
    """
    for probe in static_list.splitlines():
        # The location is present between the '.mark("' and '")' substrings
        location = probe.rfind('.mark("')
        if location != -1:
            yield probe[location + 7:-2]


def _filter_user_symbol(func):
    """Filtering function for extracted function symbols from the executable, specifically used to filter symbols
    that are from standard library etc.

    :param str func: the (mangled) function name
    :return bool: True if the function is from the user, false otherwise
    """
    if not func:
        return False
    # Filter out function that start with underscore and not with '_Z', which is used in mangled symbols
    flen = len(func)
    if func[0] == '_':
        if func[:2] != '_Z' or flen < 3:
            return False
    return True


def _check_dependency(command):
    """Check possibly missing dependency utility (such as awk, nm, ls, ...)

    :param str command: the dependency utility to check
    :return bool: True if dependency utility is present on the system, False otherwise
    """
    if not shutil.which(command):
        log.warn(("Missing dependency utility '{util}'".format(util=command)))
        return False
    return True


def _not_implemented(method, **_):
    """Placeholder function for strategies that are not implemented and should not be used.

    :param str method: the name of the method that is being requested
    """
    raise exceptions.StrategyNotImplemented(method)


# The strategies names and their implementation
_STRATEGIES = collections.OrderedDict([
    ('userspace', extraction_strategy),
    ('all', extraction_strategy),
    ('u_sampled', extraction_strategy),
    ('a_sampled', extraction_strategy),
    ('custom', custom_strategy)
])
