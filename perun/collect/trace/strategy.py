""" Module with trace collector strategies for tracing.

    The strategies are meant to be useful default settings for collection so that user
    does not have to specify every detail for each collection. The strategies focus on
    collection of userspace / all symbols with sampling / no sampling etc.

    Using the strategies, one can automatically extract collection configuration from target
    executable(s) and / or postprocess the configuration (such as remove duplicate rules,
    pair static rules, merge the sampled / non-sampled rules etc.)

    extract_configuration serves as a recommended module interface
"""

from enum import IntEnum

import perun.utils as utils
from perun.collect.trace.systemtap_script import RecordType


class _Status(IntEnum):
    OK = 0
    STAP_DEP = 1
    NM_DEP = 2
    AWK_DEP = 3


# The default global sampling for 'sample' strategies if global sampling is not set
_DEFAULT_SAMPLE = 20


def get_supported_strategies():
    """Provides list of supported strategies.

    :return: list -- the names of supported strategies
    """
    return _STRATEGIES


def get_default_strategy():
    """Provides the name of the default collector strategy.

    :return: str -- the name of the default strategy used
    """
    return _STRATEGIES[-1]


# TODO: add test to check the existence of specified probes (needs cross-comparison)
def extract_configuration(func, func_sampled, static, static_sampled, **kwargs):
    """Interface for the script assembling. Handles the specifics for each strategy.

    The custom strategy - only the user specified probes are used and no automated extraction
    or pairing of symbols is performed.

    The userspace, all, u_sampled and a_sampled strategy - no manual configuration of profiled
    locations is required and is instead automatically extracted from the provided binary
    according to the specific strategy. However the user can specify additional rules
    that have higher priority than the extracted ones.

    The output dictionary is updated as follows:
     - func, static: contains prepared rules for profiling with unified sampling specification
       - the rules are stored as dict of dictionaries with keys 'name', 'sample' and optionally
         'pair' for rules that can be paired (such as static rules)

    :param list func: the list of function names that will be traced
    :param list func_sampled: the list of function names with specified sampling
    :param list static: the list of static probes that will be traced
    :param list static_sampled: the list of static probes with specified sampling
    :param kwargs: additional configuration parameters

    :return kwargs: the updated dictionary with post processed rules
    """
    # Do some strategy specific actions (e.g. extracting symbols)
    kwargs['global_sampling'], extracted_func, extracted_static = _strategy_specifics(**kwargs)

    # Create one dictionary of function probes specification
    kwargs['func'] = _merge_probes(func, func_sampled, extracted_func, kwargs['global_sampling'])

    # Create one dictionary of static probes specification
    kwargs['static'] = []
    if kwargs['with_static']:
        # We also need to do some automated pairing of static rules
        kwargs['static'] = _pair_rules(
            _merge_probes(static, static_sampled, extracted_static, kwargs['global_sampling']))
    return kwargs


def _strategy_specifics(method, binary, with_static, global_sampling, **_):
    """Handle specific operations related to various strategies such as extracting function
    and static probe symbols.

    :param str method: the collection strategy
    :param str binary: path to the binary file that is profiled
    :param bool with_static: True if static probes are being profiled
    :param int global_sampling: the global sampling value

    :return tuple: updated global_sampling, extracted functions or {}, extracted static probes or {}
    """
    # Set the default sampling if sampled strategy is required but sampling is not provided
    if method in ('u_sampled', 'a_sampled') and global_sampling == 1:
        global_sampling = _DEFAULT_SAMPLE

    # Extract the functions and static probes if needed
    func = _extract_functions(binary, method, global_sampling) if method != 'custom' else {}
    static = _extract_static(binary, global_sampling) if method != 'custom' and with_static else {}

    return global_sampling, func, static


def _merge_probes(specified, specified_sampled, extracted, global_sampling):
    """Merges the probe lists without / with specified sampling and extracted functions into one
    list with unified sampling specification

    :param list specified: list of strings that represent probe names
    :param list specified_sampled: list of tuples that contain 0) probe name, 1) probe sampling
    :param dict extracted: dictionary of extracted probe specification in unified format
    :param int global_sampling: the global sampling value that is applied to all probes
                                without specified sampling
    :return dict: dict of probes in unified format (dictionaries with 'name' and 'sample' keys)
    """
    # Add global sampling (default 0) to the probes without sampling specification
    probes = {probe: {'name': probe, 'sample': global_sampling} for probe in specified}

    # Validate the sampling values and merge the lists
    for probe in specified_sampled:
        probes[probe] = {'name': probe[0], 'sample': probe[1] if probe[1] > 1 else global_sampling}

    # 'Merge' the two dictionaries - user specification has bigger priority
    extracted.update(probes)
    return extracted


def _pair_rules(probes):
    """Pairs the rules according to convention:
     - rule names with '#' serving as a delimiter between two probes, which should be paired
       as a starting and ending probe
     - rules are paired according to their endings:
        <name>, <name>begin, <name>entry,  <name>start,  <name>create,  <name>construct
                <name>end,   <name>return, <name>finish, <name>destroy, <name>deconstruct.
     - the pairing algorithm first tries to pair the exact combination (e.g. begin, end) and if
       such exact combination is not found, then tries to pair rules among other combinations

     :param dict probes: the list of probes (as dicts) that should be paired

     :return dict: probe dictionaries with optionally added 'pair' key containing paired probe name
    """
    result = dict()

    suffix_pairs = {'begin': 'end', 'entry': 'return', 'start': 'finish',
                    'create': 'destroy', 'construct': 'deconstruct'}
    related = (['begin', 'entry', 'start'], ['create', 'construct'])

    delimited, beginnings, endings = _classify_static_probes(probes, suffix_pairs)

    # First process the delimited probes
    for k, v in delimited.items():
        delimiter = v[1]
        # The key is the same as name
        left, right = v[0]['name'][:delimiter], v[0]['name'][delimiter + 1:]
        _add_paired_rule(left, right, v[0]['sample'], v[0]['sample'], result, False)

    # Process the probes without pairing hints
    # Iterate all the names and try to pair them if possible
    for k, v in beginnings.items():
        if k in endings:
            b_suffixes, e_suffixes = v['suffix'], endings[k]['suffix']
            b_sample, e_sample = v['sample'], endings[k]['sample']

            # First check if the rule is simply <name>
            # TODO: take the first ending suffix as pair, change when multiple pairing is supported
            if not b_suffixes:
                full_name = k + e_suffixes[0][1] + e_suffixes[0][0]
                _add_paired_rule(k, full_name, b_sample, e_sample, result)
                continue

            # Try to create the proper pairs using suffix_pairs
            pairs = _pair_suffixes(b_suffixes, e_suffixes,
                                   lambda x: [suffix_pairs[x]])
            # All proper pairs were created, try to pair the rest using the related combinations
            pairs += _pair_suffixes(b_suffixes, e_suffixes,
                                    lambda x: related[0] if x in related[0] else related[1])
            for pair in pairs:
                _add_paired_rule(k + pair[0], k + pair[1], b_sample, e_sample, result)

            # Insert the rest of the suffix extensions
            if e_suffixes:
                _add_suffix_rules(k, e_suffixes, e_sample, result)
            if b_suffixes:
                _add_suffix_rules(k, b_suffixes, b_sample, result)
        else:
            _add_suffix_rules(k, v['suffix'], v['sample'], result)
    return result


def _classify_static_probes(probes, suffix_pairs):
    """Classifies the static probes into pairing groups:
       - explicitly paired probes using the # delimiter
       - probes with 'starting' suffixes specified in suffix pairs or without suffix
       - probes with 'ending' suffixes

    :param dict probes: the dictionary of static probes to be paired
    :param dict suffix_pairs: the suffix pairing combinations

    :return tuple: delimited probes, starting probes, ending probes
    """
    # Split the probes into group with and without delimiter '#'
    delimited, basic = dict(), dict()
    for k, v in probes.items():
        delimiter = v['name'].find('#')
        if delimiter != -1:
            delimited[k] = (v, delimiter)
        else:
            basic[k] = v

    # Process the basic probes - find endings and compare them
    beginnings, endings = dict(), dict()
    for k, v in basic.items():
        # Classify the probe as starting or ending according to the known suffixes
        if not _check_suffix(v, suffix_pairs.values(), endings):
            if not _check_suffix(v, suffix_pairs.keys(), beginnings):
                # Not starting nor ending suffix, treat as regular probe name
                beginnings.setdefault(v['name'], {'sample': v['sample'], 'suffix': []})
    return delimited, beginnings, endings


def _check_suffix(probe, suffix_group, cls):
    """Checks if the probe name contains any suffix from the suffix group and if yes, classifies it
    into the specified cls. Also stores the delimiter between the probe name and suffix, if any.

    :param dict probe: the given probe specification
    :param collection suffix_group: the collection of suffixes to check
    :param dict cls: the resulting class
    """
    default = {'sample': probe['sample'], 'suffix': []}
    # Iterate the suffixes from suffix group and check if the probe name ends with one of them
    for suffix in suffix_group:
        if probe['name'].lower().endswith(suffix):
            name = probe['name'][:-len(suffix)]
            # Store the delimiter if any
            delimiter = ''
            while name[-1] in _SUFFIX_DELIMITERS:
                delimiter = name[-1] + delimiter
                name = name[:-1]
            cls.setdefault(name, default)['suffix'].append((suffix, delimiter))
            return True
    return False


def _pair_suffixes(b_suffixes, e_suffixes, pairing):
    """Pairs the starting and ending suffixes of one probe according to the provided
    pairing function. Successfully paired suffixes are removed from the suffix lists.

    :param list b_suffixes: the list of beginning suffixes associated with the probe
    :param list e_suffixes: the list of ending suffixes
    :param function pairing: function that takes beginning suffix (in lowercase) and should
                             return the expected ending suffix or collection of them
    :return list: the list of combined suffix pairs
    """
    # Check if the probe has matching starting and ending suffixes
    pairs = []
    for suffix in list(b_suffixes):
        pair_suffixes = pairing(suffix[0].lower())
        # Can't use simple 'in' - we need case insensitive comparison and case sensitive result
        for e_suffix in list(e_suffixes):
            if e_suffix[0].lower() in pair_suffixes:
                b_suffixes.remove(suffix)
                e_suffixes.remove(e_suffix)
                pairs.append((suffix[1] + suffix[0], e_suffix[1] + e_suffix[0]))
                break
    return pairs


# TODO: Allow multiple pairs (needs advanced processing of sampling across all the pairs)
def _add_paired_rule(probe_start, probe_end, start_sample, end_sample, result, add_separate=True):
    """Add paired rule to the resulting probe dictionary.

    :param str probe_start: the full name of starting probe
    :param str probe_end: the full name of paired ending probe
    :param int start_sample: the sampling value for starting probe
    :param int end_sample: the sampling value for ending probe
    :param dict result: the dictionary of static probes
    :param bool add_separate: if one of the paired probe is already in the result, add the
                              remaining probe as simple non-paired probe
    """
    # Insert the created pair if both probes are unique (multiple pairing problem)
    if probe_start not in result and probe_end not in result:
        sampling = min(start_sample, end_sample)
        result[probe_start] = {'name': probe_start, 'sample': sampling,
                               'pair': (RecordType.StaticBegin, probe_end)}
        result[probe_end] = {'name': probe_start, 'sample': sampling,
                             'pair': (RecordType.StaticEnd, probe_start)}
    elif add_separate:
        # The probes are not unique, do the single insertion by setdefault
        result.setdefault(probe_start, {'name': probe_start, 'sample': start_sample})
        result.setdefault(probe_end, {'name': probe_end, 'sample': end_sample})


def _add_suffix_rules(name, suffixes, sample, result):
    """Add static probe rules created from name and suffixes as non-paired rules

    :param str name: the base name of the probe
    :param list suffixes: list of all suffixes to add
    :param int sample: the sampling value for the rules
    :param dict result: the static probe dictionary
    """
    if not suffixes:
        result.setdefault(name, {'name': name, 'sample': sample})
    for suffix in suffixes:
        full_suffix = suffix[1] + suffix[0]
        result.setdefault(name + full_suffix, {'name': name + full_suffix, 'sample': sample})


def _extract_functions(binary, method, global_sampling, **_):
    """Extracts function symbols from the supplied binary.

    :param str binary: path to the binary file
    :param str method: name of the applied extraction strategy
    :param int global_sampling: the sampling value applied to all extracted function locations

    :return list: extracted function symbols stored as a probes = dictionaries
    """
    # Load userspace / all function symbols from the binary
    user = method in ('userspace', 'u_sampled')
    funcs = _load_function_names(binary, user)

    # There are no functions
    if not funcs:
        return {}

    # Transform to the desired format
    if user:
        return {func: {'name': func, 'sample': global_sampling} for func in funcs.splitlines() if
                _filter_user_symbol(func)}
    return {func: {'name': func, 'sample': global_sampling} for func in funcs.splitlines()}


def _extract_static(binary, global_sampling, **_):
    """Extract static probe locations from the supplied binary file.

    :param str binary: path to the binary file
    :param int global_sampling: the sampling value applied to all extracted static probe locations

    :return list: extracted static locations stored as a probes = dictionaries
    """
    # Extract the static probe locations from the binary
    # note: stap -l returns code '1' if there are no static probes
    probes = _load_static_probes(binary)

    # There are no static probes in the binary
    if not probes or probes.lstrip(' ').startswith('Tip:'):
        return {}

    # Transform
    return {probe: {'name': probe, 'sample': global_sampling}
            for probe in _static_probe_names(probes)}


def _load_function_names(binary, only_user):
    """Load all / userspace function symbols from the supplied binary.

    :param str binary: the path to the profiled binary
    :param bool only_user: True if only userspace symbols are to be extracted

    :return str: the output of the symbol extraction as a string
    """
    # Check if nm and awk utils are available, both are needed for the extraction
    if utils.check_dependency('nm') and utils.check_dependency('awk'):
        # Extract user function symbols from the supplied binary
        awk_filter = '$2 == "T"' if only_user else '$2 == "T" || $2 == "W"'
        output, _ = utils.run_safely_external_command(
            'nm -P {bin} | awk \'{filt} {{print $1}}\''.format(bin=binary, filt=awk_filter))
        return output.decode('utf-8')
    return ''


def _load_static_probes(binary):
    """Load static probes from the binary file using the systemtap.

    :param str binary: path to the binary file

    :return str: the decoded standard output
    """
    if utils.check_dependency('stap'):
        out, _ = utils.run_safely_external_command(
            'sudo stap -l \'process("{bin}").mark("*")\''.format(bin=binary), False)
        return out.decode('utf-8')
    return ''


def _static_probe_names(static_list):
    """Cut the static probe location name from the extract output.

    :param str static_list: the extraction output

    :return object: generator object that provides the static probe locations
    """
    for probe in static_list.splitlines():
        # The location is present between the '.mark("' and '")' substrings
        location = probe.rfind('.mark("')
        if location != -1:
            yield probe[location + len('.mark("'):-2]


def _filter_user_symbol(func):
    """Filtering function for extracted function symbols from the executable,
    specifically used to filter symbols that are from standard library etc.

    :param str func: the (mangled) function name

    :return bool: True if the function is from the user, false otherwise
    """
    if not func:
        return False
    # Filter function that start with underscore and not with '_Z', which is used in mangled symbols
    flen = len(func)
    if func[0] == '_':
        if func[:2] != '_Z' or flen < 3:
            return False
    return True


# The set of supported strategies
_STRATEGIES = ['userspace', 'all', 'u_sampled', 'a_sampled', 'custom']
# The set of supported delimiters between probe and its suffix
_SUFFIX_DELIMITERS = ('_', '-')
