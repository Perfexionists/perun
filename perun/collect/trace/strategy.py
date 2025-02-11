"""Module with trace collector strategies for tracing.

The strategies are meant to be useful default settings for collection so that user
does not have to specify every detail for each collection. The strategies focus on
collection of userspace / all symbols with sampling / no sampling etc.

Using the strategies, one can automatically extract collection configuration from target
executable(s) and / or postprocess the configuration (such as remove duplicate rules,
pair USDT rules, merge the sampled / non-sampled rules etc.)

extract_configuration serves as a recommended module interface
"""

# Standard Imports

# Third-Party Imports

# Perun Imports
from perun.collect.trace.probes import Probes, ProbeType
from perun.collect.trace.values import Strategy, SUFFIX_DELIMITERS
from perun.collect.trace.watchdog import WATCH_DOG
from perun.utils.external import commands


# TODO: add test to check the existence of specified probes (needs cross-comparison)
def extract_configuration(engine, probes):
    """Handles the specifics for each strategy.

    The custom strategy - only the user specified probes are used and no automated extraction
    or pairing of symbols is performed.

    The userspace, all, u_sampled and a_sampled strategy - no manual configuration of profiled
    locations is required and is instead automatically extracted from the provided binary
    according to the specific strategy. However the user can specify additional rules
    that have higher priority than the extracted ones.

    :param engine: the collection engine object
    :param probes: the probes object

    """
    WATCH_DOG.info("Attempting to build the probes configuration")

    # Do some strategy specific actions (e.g. extracting symbols)
    extracted_func, extracted_usdt = _extract_strategy_specifics(engine, probes)
    WATCH_DOG.debug(
        f"Number of extracted function probes: '{len(extracted_func)}', usdt probes: '{len(extracted_usdt)}'"
    )

    # Create one dictionary of function probes specification
    extracted_func.update(probes.user_func)
    probes.func = extracted_func

    # Create one dictionary of USDT probes specification
    if probes.with_usdt:
        extracted_usdt.update(probes.usdt)
        # We also need to do some automated pairing of usdt rules
        probes.usdt = _pair_rules(extracted_usdt)
        probes.usdt_reversed = probes.usdt.pop("#pairs_reversed#")

    WATCH_DOG.info("Configuration built successfully")


def _extract_strategy_specifics(engine, probes):
    """Handles specific operations related to various strategies such as extracting function
    and USDT probe symbols.

    :param engine: the collection engine object
    :param probes: the probes object

    :return: extracted functions or {}, extracted USDT probes or {}
    """
    # Extract the functions and usdt probes if needed
    func, usdt = {}, {}
    if probes.strategy != Strategy.CUSTOM:
        func = _extract_functions(engine.targets, probes.strategy, probes.global_sampling)
        if probes.with_usdt:
            usdt = _extract_usdt(engine, probes.global_sampling)

    return func, usdt


def _pair_rules(usdt_probes):
    """Pairs the rules according to convention:
    - rule names with ';' serving as a delimiter between two probes, which should be paired
      as a starting and ending probe
    - rules are paired according to their endings:
       <name>, <name>begin, <name>entry,  <name>start,  <name>create,  <name>construct
               <name>end,   <name>return, <name>finish, <name>destroy, <name>deconstruct.
    - the pairing algorithm first tries to pair the exact combination (e.g. begin, end) and if
      such exact combination is not found, then tries to pair rules among other combinations

    :param usdt_probes: the collection of USDT probes that should be paired

    :return: a new USDT probe collection with removed paired probes and updated 'pair' value
                  for every probe (the probe is paired with itself in case no paired rule is found)
    """
    # Add reverse mapping for paired probes
    result = {"#pairs_reversed#": {}}

    # Direct suffix pairs that should be paired
    suffix_pairs = {
        "begin": "end",
        "entry": "return",
        "start": "finish",
        "create": "destroy",
        "construct": "deconstruct",
    }
    # Related suffixes that could still be paired together
    related = (["end", "return", "finish"], ["destroy", "deconstruct"])

    # Classify the probes into manually delimited, beginning and ending probes (based on suffixes)
    delimited, beginnings, endings = _classify_usdt_probes(usdt_probes, suffix_pairs)

    # First process the delimited probes
    for prb_name, (prb_conf, delimiter) in delimited.items():
        # The key is the same as name
        prb1, prb2 = prb_conf["name"][:delimiter], prb_conf["name"][delimiter + 1 :]
        prb_conf["name"] = prb1
        prb_conf["pair"] = prb2
        result["#pairs_reversed#"][prb2] = prb1
        result[prb1] = prb_conf

    # Process the probes without pairing hints
    # Iterate all the names and try to pair them if possible
    for prb_name, b_suffixes in beginnings.items():
        if prb_name in endings:
            e_suffixes = endings[prb_name]

            # First check if the rule is simply <name>
            # TODO: take the first ending suffix as pair, change when multiple pairing is supported
            if not b_suffixes:
                suffix, delimiter = e_suffixes[0][0], e_suffixes[0][1]
                full_name = prb_name + delimiter + suffix
                _add_paired_probe(prb_name, full_name, usdt_probes, result)
                continue

            # Try to create the proper pairs using suffix_pairs
            pairs = _pair_suffixes(b_suffixes, e_suffixes, lambda x: [suffix_pairs[x]])
            # All proper pairs were created, try to pair the rest using the related combinations
            pairs += _pair_suffixes(
                b_suffixes,
                e_suffixes,
                lambda x: related[0] if x in related[0] else related[1],
            )
            for pair in pairs:
                _add_paired_probe(prb_name + pair[0], prb_name + pair[1], usdt_probes, result)

            # Insert the rest of the suffix extensions
            _add_suffix_probes(prb_name, b_suffixes + e_suffixes, usdt_probes, result)
        else:
            _add_suffix_probes(prb_name, b_suffixes, usdt_probes, result)
    return result


def _classify_usdt_probes(usdt_probes, suffix_pairs):
    """Classifies the USDT probes into pairing groups:
       - explicitly paired probes using the ; delimiter
       - probes with 'starting' suffixes specified in suffix pairs or without suffix
       - probes with 'ending' suffixes

    :param usdt_probes: the dictionary of USDT probes to be paired
    :param suffix_pairs: the suffix pairing combinations

    :return: delimited probes, starting probes, ending probes
    """
    # Split the probes into group with and without delimiter ';'
    delimited, basic = dict(), dict()
    for prb_name, prb_conf in usdt_probes.items():
        delimiter = prb_conf["name"].find(";")
        if delimiter != -1:
            delimited[prb_name] = (prb_conf, delimiter)
        else:
            basic[prb_name] = prb_conf

    # Process the basic probes - find endings and compare them
    beginnings, endings = dict(), dict()
    for prb_name, prb_conf in basic.items():
        # Classify the probe as starting or ending according to the known suffixes
        if not _check_suffix_of(prb_conf, suffix_pairs.values(), endings):
            if not _check_suffix_of(prb_conf, suffix_pairs.keys(), beginnings):
                # Not starting nor ending suffix, treat as regular probe name
                beginnings.setdefault(prb_conf["name"], [])
    return delimited, beginnings, endings


def _check_suffix_of(usdt_probe, suffix_group, cls):
    """Checks if the probe name contains any suffix from the suffix group and if yes, classifies it
    into the specified cls. Also stores the delimiter between the probe name and suffix, if any.

    :param usdt_probe: the given probe specification
    :param suffix_group: the collection of suffixes to check
    :param cls: the resulting class
    """
    # Iterate the suffixes from suffix group and check if the probe name ends with one of them
    for suffix in suffix_group:
        if usdt_probe["name"].lower().endswith(suffix):
            name = usdt_probe["name"][: -len(suffix)]
            # Store the delimiter if any
            delimiter = ""
            while name[-1] in SUFFIX_DELIMITERS:
                delimiter = name[-1] + delimiter
                name = name[:-1]
            cls.setdefault(name, []).append((suffix, delimiter))
            return True
    return False


def _pair_suffixes(b_suffixes, e_suffixes, pair_by):
    """Pairs the starting and ending suffixes of one probe according to the provided
    pairing function. Successfully paired suffixes are removed from the suffix lists.

    :param b_suffixes: the list of beginning suffixes associated with the probe
    :param e_suffixes: the list of ending suffixes
    :param pair_by: function that takes beginning suffix (in lowercase) and should
                             return the expected ending suffix or collection of them
    :return: the list of combined suffix pairs
    """
    # Check if the probe has matching starting and ending suffixes
    pairs = []
    for b_suffix, b_delimiter in list(b_suffixes):
        pair_suffixes = pair_by(b_suffix.lower())
        # Can't use simple 'in' - we need case insensitive comparison and case sensitive result
        for e_suffix, e_delimiter in list(e_suffixes):
            if e_suffix.lower() in pair_suffixes:
                b_suffixes.remove((b_suffix, b_delimiter))
                e_suffixes.remove((e_suffix, e_delimiter))
                pairs.append((b_delimiter + b_suffix, e_delimiter + e_suffix))
                break
    return pairs


# TODO: Allow multiple pairs (needs advanced processing of sampling across all the pairs)
def _add_paired_probe(probe_start, probe_end, usdt_probes, result):
    """Add paired rule to the resulting probe dictionary.

    :param probe_start: the starting probe name
    :param probe_end: the paired ending probe name
    :param usdt_probes: the probes dictionary
    :param result: the new dictionary of USDT probes
    """

    def is_unique(probe_name):
        """A helper function for determining if the given probe name is not already contained
        in the resulting dictionary or if it has not been already removed.

        :param probe_name: the name of the probe to check

        :return: specifies if the probe is indeed unique
        """
        return probe_name not in result and probe_name not in result["#pairs_reversed#"]

    # Insert the created pair if both probes are unique (multiple pairing problem)
    if is_unique(probe_start) and is_unique(probe_end):
        probe_start, probe_end = usdt_probes[probe_start], usdt_probes[probe_end]
        sampling = min(probe_start["sample"], probe_end["sample"])
        probe_start["pair"] = probe_end["name"]
        probe_start["sample"] = sampling
        # Insert the paired probe and the new probe specification into the result
        result["#pairs_reversed#"][probe_end["name"]] = probe_start["name"]
        result[probe_start["name"]] = probe_start
    else:
        # The probes are not unique, do the single insertion
        _add_single_probe(probe_start, usdt_probes, result)
        _add_single_probe(probe_end, usdt_probes, result)


def _add_suffix_probes(name, suffixes, usdt_probes, result):
    """Add USDT probe rules created from name and suffixes as non-paired rules

    :param name: the base name of the probe
    :param suffixes: list of all the suffixes to add
    :param usdt_probes: the original USDT probes dictionary
    :param result: the new USDT probe dictionary
    """
    if not suffixes:
        _add_single_probe(name, usdt_probes, result)
    for suffix, delimiter in suffixes:
        # Build the proper name first
        full_name = name + delimiter + suffix
        _add_single_probe(full_name, usdt_probes, result)


def _add_single_probe(name, usdt_probes, result):
    """Add non-paired USDT probe to the resulting probe collection.

    :param name: the probe name
    :param usdt_probes: the original probes dictionary
    :param result: the new USDT probe dictionary
    """
    if name in usdt_probes and name not in result["#pairs_reversed#"]:
        usdt_probes[name]["pair"] = name
        # Single probes do not support sampling
        usdt_probes[name]["sample"] = 1
        result.setdefault(name, usdt_probes[name])


def _extract_functions(targets, strategy, global_sampling):
    """Extracts function symbols from the supplied binary.

    :param targets: paths to executables / libraries that should have their symbols extracted
    :param strategy: name of the applied extraction strategy
    :param global_sampling: the sampling value applied to all extracted function locations

    :return: extracted function symbols stored as probes = dictionaries
    """
    # Load userspace / all function symbols from the binary
    user = strategy in (Strategy.USERSPACE, Strategy.USERSPACE_SAMPLED)
    filt = _filter_user_symbol if user else lambda _: True
    probes = {}

    for target in targets:
        func_count = 0
        funcs = _load_function_names(target, user)
        # Transform to the desired format
        for func in funcs.splitlines():
            if filt(func) and func not in probes:
                func_count += 1
                probes[func] = Probes.create_probe_record(
                    func, ProbeType.FUNC, lib=target, pair=func, sample=global_sampling
                )
        if not func_count:
            WATCH_DOG.info(f"No function symbols found in '{target}'")
    return probes


def _extract_usdt(engine, global_sampling):
    """Extract USDT probe locations from the supplied binary file.

    :param engine: the collection engine object
    :param global_sampling: the sampling value applied to all extracted USDT probe locations

    :return: extracted USDT locations stored as probes = dictionaries
    """
    # Extract the usdt probe locations from the binary
    usdt_probes = engine.available_usdt()

    # Transform
    return {
        usdt: Probes.create_probe_record(usdt, ProbeType.USDT, lib=target, sample=global_sampling)
        for target, target_usdt in usdt_probes.items()
        for usdt in target_usdt
    }


def _load_function_names(binary, only_user):
    """Load all / userspace function symbols from the supplied binary.

    :param binary: the path to the profiled binary
    :param only_user: True if only userspace symbols are to be extracted

    :return: the output of the symbol extraction as a string
    """
    # Extract user function symbols from the supplied binary
    awk_filter = '$2 == "T" || $2 == "t"' if only_user else '$2 == "T" || $2 == "W"'
    output, _ = commands.run_safely_external_command(
        f"nm -P {binary} | awk '{awk_filter} {{print $1}}'"
    )
    return output.decode("utf-8")


def _filter_user_symbol(func):
    """Filtering function for extracted function symbols from the executable,
    specifically used to filter symbols that are from standard library etc.

    :param func: the (mangled) function name

    :return: True if the function is from the user, false otherwise
    """
    if not func:
        return False
    # Filter function that start with underscore and not with '_Z', which is used in mangled symbols
    flen = len(func)
    if func[:2] == "__":
        if func[:3] != "__Z" or flen < 4:
            return False
    # Remove functions that are generated by the compiler
    if "." in func or func == "_start" or func == "_init":
        return False
    return True
