"""Collection of global methods for detection of performance changes"""

import contextlib
import os
import re

import distutils.util as dutils

from perun.utils.structs import DegradationInfo, PerformanceChange

import perun.utils.exceptions as exceptions
import perun.utils.log as log
import perun.profile.helpers as profiles
import perun.profile.factory as profile_factory
import perun.logic.runner as runner
import perun.logic.config as config
import perun.logic.pcs as pcs
import perun.logic.store as store
import perun.utils as utils
import perun.utils.decorators as decorators
import perun.vcs as vcs


__author__ = 'Tomas Fiedor'

# Minimal confidence rate from both models to perform the detection
_MIN_CONFIDANCE_RATE = 0.15
# Supported detection strategies that work with different kinds of models
_SUPPORTED_DETECTION_MODELS_STRATEGIES = [
    'best-model', 'best-param', 'best-nonparam',
    'all-param', 'all-nonparam', 'all-models', 'best-both'
]


def get_supported_detection_models_strategies():
    """
    Provides supported detection models strategies to execute
    the degradation check between two profiles with different kinds
    of models. The individual strategies represent the way of
    executing the detection between profiles and their models:

        - best-param: best parametric models from both profiles
        - best-non-param: best non-parametric models from both profiles
        - best-model: best models from both profiles
        - all-param: all parametric models pair from both profiles
        - all-non-param: all non-parametric models pair from both profiles
        - all-models: all models pair from both profiles
        - best-both: best parametric and non-parametric models from both profiles

    :returns list of str: the names of all supported degradation models strategies
    """
    return _SUPPORTED_DETECTION_MODELS_STRATEGIES


def profiles_to_queue(minor_version):
    """Retrieves the list of profiles corresponding to minor version and transforms them to map.

    The map represents both the queue and also provides the mapping of configurations to profiles.

    :param minor_version: minor version for which we are retrieving the profile queue
    :returns: dictionary mapping configurations of profiles to the actual profiles
    """
    minor_version_profiles = profiles.load_list_for_minor_version(minor_version)
    return {
        profile.config_tuple: profile for profile in minor_version_profiles
    }


@decorators.static_variables(minor_version_cache=set())
def pre_collect_profiles(minor_version):
    """For given minor version, collects performance profiles according to the job matrix

    This is applied if the profiles were not already collected by this function for the given minor,
    and if the key :ckey:`degradation.collect_before_check` is set to true value.

    TODO: What if error happens during run matrix? This should be caught and solved

    :param MinorVersion minor_version: minor version for which we are collecting the data
    """
    should_precollect = dutils.strtobool(str(
        config.lookup_key_recursively('degradation.collect_before_check', 'false')
    ))
    if should_precollect and minor_version.checksum not in pre_collect_profiles.minor_version_cache:
        # Set the registering after run to true for this run
        config.runtime().set('profiles.register_after_run', 'true')
        # Actually collect the resources
        collect_to_log = dutils.strtobool(str(
            config.lookup_key_recursively('degradation.log_collect', 'false')
        ))
        log_file = os.path.join(
            pcs.get_log_directory(),
            "{}-precollect.log".format(minor_version.checksum)
        )
        out = log_file if collect_to_log else os.devnull
        with open(out, 'w') as black_hole:
            with contextlib.redirect_stdout(black_hole):
                try:
                    runner.run_matrix_job([minor_version])
                except SystemExit as system_exit:
                    log.warn("Could not precollect data for {} minor version: {}".format(
                        minor_version.checksum[:6], str(system_exit)
                    ))
        pre_collect_profiles.minor_version_cache.add(minor_version.checksum)


def degradation_in_minor(minor_version, quiet=False):
    """Checks for degradation according to the profiles stored for the given minor version.

    :param str minor_version: representation of head point of degradation checking
    :param bool quiet: if set to true then nothing will be printed
    :returns: list of found changes
    """
    minor_version_info = vcs.get_minor_version_info(minor_version)
    base_version_queue = minor_version_info.parents
    pre_collect_profiles(minor_version_info)
    targ_profile_queue = profiles_to_queue(minor_version)
    detected_changes = []
    while targ_profile_queue and base_version_queue:
        # Pop the nearest base
        base = base_version_queue.pop(0)

        # Enqueue the parents in BFS manner
        base_info = vcs.get_minor_version_info(base)
        base_version_queue.extend(base_info.parents)

        # Precollect profiles if this is set
        pre_collect_profiles(base_info)

        # Print header if there is at least some profile to check against
        base_profiles = profiles_to_queue(base)

        # Iterate through the profiles and check degradation between those of same configuration
        for base_config, base_profile in base_profiles.items():
            targ_profile = targ_profile_queue.get(base_config)
            cmdstr = profiles.config_tuple_to_cmdstr(base_config)
            if targ_profile:
                # Print information about configuration
                # and extend the list of the detected changes including the configuration
                # and source minor version.
                detected_changes.extend([
                    (deg, cmdstr, base_info.checksum) for deg in
                    degradation_between_profiles(base_profile, targ_profile, 'best-model')
                    if deg.result != PerformanceChange.NoChange
                ])
                del targ_profile_queue[targ_profile.config_tuple]

        # Store the detected degradation
        store.save_degradation_list_for(pcs.get_object_directory(), minor_version, detected_changes)
    if not quiet:
        log.print_list_of_degradations(detected_changes)
    return detected_changes


@decorators.print_elapsed_time
@decorators.phase_function('check whole repository')
def degradation_in_history(head):
    """Walks through the minor version starting from the given head, checking for degradation.

    :param str head: starting point of the checked history for degradation.
    :returns: tuple (degradation result, degradation location, degradation rate)
    """
    detected_changes = []
    with log.History(head) as history:
        for minor_version in vcs.walk_minor_versions(head):
            history.progress_to_next_minor_version(minor_version)
            newly_detected_changes = degradation_in_minor(minor_version.checksum, True)
            log.print_short_change_string(log.count_degradations_per_group(newly_detected_changes))
            history.finish_minor_version(minor_version, newly_detected_changes)
            log.print_list_of_degradations(newly_detected_changes)
            detected_changes.extend(newly_detected_changes)
            history.flush(with_border=True)
    print("")
    log.print_short_summary_of_degradations(detected_changes)
    return detected_changes


def degradation_between_profiles(base_profile, targ_profile, models_strategy):
    """Checks between pair of (baseline, target) profiles, whether the can be degradation detected

    We first find the suitable strategy for the profile configuration and then call the appropriate
    wrapper function.

    :param ProfileInfo base_profile: baseline against which we are checking the degradation
    :param ProfileInfo targ_profile: profile corresponding to the checked minor version
    :param str models_strategy: name of detection models strategy to obtains relevant model kinds
    :returns: tuple (degradation result, degradation location, degradation rate)
    """
    if not isinstance(base_profile, profile_factory.Profile):
        base_profile = store.load_profile_from_file(base_profile.realpath, False)
    if not isinstance(targ_profile, profile_factory.Profile):
        targ_profile = store.load_profile_from_file(targ_profile.realpath, False)

    # We run all of the degradation methods suitable for the given configuration of profile
    for degradation_method in get_strategies_for(base_profile):
        yield from utils.dynamic_module_function_call(
            'perun.check', degradation_method, degradation_method,
            base_profile, targ_profile, models_strategy=models_strategy
        )


@decorators.print_elapsed_time
@decorators.phase_function('check two profiles')
def degradation_between_files(base_file, targ_file, minor_version, models_strategy):
    """Checks between pair of files (baseline, target) whether there are any changes in performance.

    :param dict base_file: baseline profile we are checking against
    :param dict targ_file: target profile we are testing
    :param str minor_version: targ minor_version
    :param str models_strategy: name of detection models strategy to obtains relevant model kinds
    :returns None: no return value
    """
    # First check if the configurations are compatible
    base_config = profiles.to_config_tuple(base_file)
    targ_config = profiles.to_config_tuple(targ_file)
    targ_minor_version = targ_file.get('origin', minor_version)
    if base_config != targ_config:
        log.error("incompatible configurations '{}' and '{}'".format(
            base_config, targ_config
        ) + "\n\nPerformance check does not make sense for profiles collected in different ways!")

    detected_changes = [
        (deg, profiles.config_tuple_to_cmdstr(base_config), targ_minor_version) for deg in
        degradation_between_profiles(base_file, targ_file, models_strategy)
        if deg.result != PerformanceChange.NoChange
    ]

    # Store the detected changes for given minor version
    store.save_degradation_list_for(
        pcs.get_object_directory(), targ_minor_version, detected_changes
    )
    print("")
    log.print_list_of_degradations(detected_changes, models_strategy)
    log.print_short_summary_of_degradations(detected_changes)


def is_rule_applicable_for(rule, configuration):
    """Helper function for testing, whether the rule is applicable for the given profile

    Profiles are w.r.t specification (:ref:`profile-spec`), the rule is as a dictionary, where
    keys correspond to the keys of the profile header, e.g.

    .. code-block:: json

        {
            'type': 'memory',
            'collector': 'cachegrind'
        }

    :param dict rule: dictionary with rule containing keys and values for which the rule is
        applicable
    :param dict configuration: dictionary with profile
    :return: true if the rule is applicable for given profile
    """
    for key, value in rule.items():
        if key == 'method':
            continue
        if key == 'postprocessor':
            postprocessors = [post['name'] for post in configuration['postprocessors']]
            if value not in postprocessors:
                return False
        elif key == 'collector':
            if configuration['collector_info']['name'] != value:
                return False
        elif configuration['header'].get(key, None) != value:
            return False
    return True


def parse_strategy(strategy):
    """Translates the given string to the real name of the strategy---callable function.

    This handles short names for the degradation strategies.

    :param str strategy: name of the strategy
    :return:
    """
    short_strings = {
        'aat': 'average_amount_threshold',
        'bmoe': 'best_model_order_equality',
        'preg': 'polynomial_regression',
        'lreg': 'linear_regression',
        'fast': 'fast_check',
        'int': 'integral_comparison',
        'loc': 'local_statistics',
    }
    return short_strings.get(strategy, strategy)


def get_strategies_for(profile):
    """Retrieves the best strategy for the given profile configuration

    :param ProfileInfo profile: Profile information with configuration tuple
    :return: method to be used for checking degradation between profiles of
        the same configuration type
    """
    # Retrieve the application strategy
    try:
        application_strategy = config.lookup_key_recursively('degradation.apply')
    except exceptions.MissingConfigSectionException:
        log.error("'degradation.apply' could not be found in any configuration\n"
                  "Run either 'perun config --local edit' or 'perun config --shared edit' and set "
                  " the 'degradation.apply' to suitable value (either 'first' or 'all').")

    # Retrieve all of the strategies from configuration
    strategies = config.gather_key_recursively('degradation.strategies')
    already_applied_strategies = []
    first_applied = False
    for strategy in strategies:
        if (application_strategy == 'all' or not first_applied) \
                and is_rule_applicable_for(strategy, profile)\
                and 'method' in strategy.keys()\
                and strategy['method'] not in already_applied_strategies:
            first_applied = True
            method = parse_strategy(strategy['method'])
            already_applied_strategies.append(method)
            yield method


def run_detection_for_profiles(detection_method, base_profile, targ_profile, models_strategy):
    """
    The wrapper for running detection methods for all kinds of models.

    According to the given `models_strategy` this function obtains the relevant
    models from both given profiles and subsequently calls the function, that
    ensure the executing of detection between them. In the end, this function
    returns the structure `DegradationInfo` with the detected information.

    :param callable detection_method: method to execute the detection logic with the call template
    :param Profile base_profile: baseline profile against which we are checking the degradation
    :param Profile targ_profile: target profile corresponding to the checked minor version
    :param str models_strategy: name of detection models strategy to obtains relevant model kinds
    :returns: tuple - degradation result (structure DegradationInfo)
    """
    if models_strategy in ('all-models', 'best-both'):
        partial_strategies = ['all-param', 'all-nonparam'] if models_strategy == 'all-models' else \
            ['best-param', 'best-nonparam']
        for partial_strategy in partial_strategies:
            for degradation_info in run_detection_for_profiles(
                    detection_method, base_profile, targ_profile, partial_strategy
            ):
                yield degradation_info
    else:
        base_models = base_profile.get_models(models_strategy)
        targ_models = targ_profile.get_models(models_strategy)
        for degradation_info in run_detection(
                detection_method, base_profile, base_models,
                targ_profile, targ_models, models_strategy=models_strategy
        ):
            yield degradation_info


def run_detection(detection_method, base_profile, base_models, targ_profile, targ_models, **kwargs):
    """
    The runner of detection methods for a set of models pairs (base and targ).

    The method performs the degradation check between two relevant models, obtained from
    the given set of models. According to the match of the UIDs of the models is called
    the detection method, that returns a dictionary with information about the changes
    from the comparison of these models. This method subsequently return the structure
    DegradationInfo with relevant items about detected changes between compared models.

    :param callable detection_method: method to execute the detection logic with the call template
    :param Profile base_profile: base profile against which we are checking the degradation
    :param dict base_models: set of models to comparison from base profile
    :param Profile targ_profile: targ profile corresponding to the checked minor version
    :param dict targ_models: set of models to comparison from targ profile
    :param kwargs: contains name of detection models strategy to obtains relevant model kinds
    :return: tuple - degradation result (structure DegradationInfo)
    """
    uid_flag = kwargs['models_strategy'] in ('all-param', 'all-nonparam')
    for param_uid, targ_model in targ_models.items():
        uid = targ_model['uid'] if uid_flag else param_uid
        base_model = base_models.get(uid, base_models.get(param_uid))

        if base_model and round(min(base_model['r_square'], targ_model['r_square']), 2) \
                >= _MIN_CONFIDANCE_RATE:
            change_result = detection_method(
                base_model, targ_model, base_profile=base_profile, targ_profile=targ_profile
            )

            yield DegradationInfo(
                res=change_result.get('change_info'),
                t=str(change_result.get('rel_error')),
                loc=re.sub(base_model.get('model', base_model.get('method')) + '$', '', uid)
                if uid_flag else uid,
                fb=base_model.get('model', base_model.get('method')),
                tt=targ_model.get('model', targ_model.get('method')),
                ct='r_square',
                cr=round(min(base_model['r_square'], targ_model['r_square']), 2),
                pi=change_result.get('partial_intervals'),
            )
