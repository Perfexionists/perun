""" Module with complexity collector strategies for tracing.

    The strategies are meant to be useful default settings for collection so that user
    does not have to specify every detail for each collection. The strategies focus on
    userspace / everything collection with sampling / no sampling etc.

    The assemble_script method serves as a interface which handles specifics of each strategy.
"""

import collections

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


def assemble_script(**kwargs):
    """Interface for the script assembling. Handles the specifics for each strategy.

    :param dict kwargs: the parameters to the collector as set by the cli

    :returns: str -- the path to the created script file
    """
    # Choose the handler for specified strategy
    script = _STRATEGIES[kwargs['method']](**kwargs)

    # Create the file and save the script
    script_path = kwargs['cmd'] + '_collect.stp'
    with open(script_path, 'w') as stp_handle:
        stp_handle.write(script)
    return script_path


def custom_strategy(rules, sampling, cmd, global_sampling, **_):
    """The custom strategy implementation. There are no defaults and only the parameters
    specified by the user are used for collection.

    :param list rules: the list of rules / functions used for tracing probes
    :param list of dict sampling: list of sampling specifications as dictionaries
    :param str cmd: the tracing target executable / process
    :param int global_sampling: the sampling value set globally for every rule

    :returns: str -- the script code
    """

    # Build sampling dictionary
    samples = _build_samples(sampling, rules, global_sampling)

    # Assembly the script
    script = ''
    # Add sampling counters
    for _, sample in samples.items():
        script += 'global samp_{0} = {1}\n'.format(str(sample[1]), sample[0] - 1)
    script += '\n'

    # Add probes
    for rule in rules:
        probe_in = 'probe process("{0}").function("{1}").call {{\n'.format(cmd, rule)
        probe_out = 'probe process("{0}").function("{1}").return {{\n'.format(cmd, rule)
        call = 'printf("%s %s\\n", thread_indent(1), probefunc())\n'
        ret = 'printf("%s\\n", thread_indent(-1))\n'

        if rule in samples:
            # Probe should be sampled, add counter manipulation
            probe_in += ('\tsamp_{0}++\n'
                         '\tif(samp_{0} == {1}) {{\n'
                         '\t\t{2}'
                         '\t\tsamp_{0} = 0\n'
                         '\t}}\n}}\n\n'
                         .format(str(samples[rule][1]), str(samples[rule][0]), call))
            probe_out += ('\tif(samp_{0} == 0) {{\n'
                          '\t\t{1}'
                          '\t}}\n}}\n\n'.format(str(samples[rule][1]), ret))
        else:
            # Probe does not need to be sampled
            probe_in += '\t{0}}}\n\n'.format(call)
            probe_out += '\t{0}}}\n\n'.format(ret)

        # Add probe and return points to the script
        script += probe_in + probe_out

    return script


def _build_samples(sampling, rules, global_sampling):
    """Creates sampling dictionary that has appropriate form for the script generation.
    Handles the global sampling and specific sampling overlaps and priorities.

    :param list of dict sampling: list of sampling specifications as dictionaries
    :param list rules: the list of rules / functions used for tracing probes
    :param int global_sampling: the sampling value set globally for every rule

    :returns: dict -- the sampling dictionary in form of {rule: (sampling value, index)},
                      where index is unique value representing the rule name

    """

    # Create samples from sampling list, filter <negative, 1> entries
    samples = {samp['func']: (samp['sample'], idx) for idx, samp in
               enumerate(sampling) if samp['sample'] > 1}

    # Create samples for all remaining rules if needed
    if global_sampling:
        samples_all = {rule: (global_sampling, idx) for idx, rule in enumerate(rules)}
        for k, v in samples.items():
            # Change the sampling value and keep the sampling index
            samples_all[k] = (v[0], samples_all[k][1])
        samples = samples_all

    return samples


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

