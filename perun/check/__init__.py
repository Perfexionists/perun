import os
import re

import distutils.util as dutils
from enum import Enum

import perun.utils.exceptions as exceptions
import perun.profile.factory as profiles
import perun.utils.log as log
import perun.logic.runner as runner
import perun.logic.commands as commands
import perun.logic.config as config
import perun.logic.store as store
import perun.utils as utils
import perun.utils.decorators as decorators
import perun.vcs as vcs

from perun.logic.pcs import PCS

__author__ = 'Tomas Fiedor'


PerformanceChange = Enum(
    'PerformanceChange', 'Degradation MaybeDegradation ' +
                         'Unknown NoChange MaybeOptimization Optimization'
)

CHANGE_STRINGS = {
    PerformanceChange.Degradation: 'Degradation',
    PerformanceChange.MaybeDegradation: 'Maybe Degradation',
    PerformanceChange.NoChange: 'No Change',
    PerformanceChange.Unknown: 'Unknown',
    PerformanceChange.MaybeOptimization: 'Maybe Optimization',
    PerformanceChange.Optimization: 'Optimization'
}
CHANGE_COLOURS = {
    PerformanceChange.Degradation: 'red',
    PerformanceChange.MaybeDegradation: 'yellow',
    PerformanceChange.NoChange: 'white',
    PerformanceChange.Unknown: 'grey',
    PerformanceChange.MaybeOptimization: 'cyan',
    PerformanceChange.Optimization: 'blue'
}
LINE_PARSING_REGEX = re.compile(
    r"(?P<location>.+)\s"
    r"PerformanceChange[.](?P<result>[A-Za-z]+)\s"
    r"(?P<type>\S+)\s"
    r"(?P<from>\S+)\s"
    r"(?P<to>\S+)\s"
    r"(?P<ctype>\S+)\s"
    r"(?P<crate>\S+)\s"
    r"(?P<minor>\S+)\s"
    r"(?P<cmdstr>.+)"
)


def save_degradation_list_for(base_dir, minor_version, degradation_list):
    """Saves the given degradation list to a minor version storage

    This converts the list of degradation records to a storage-able format. Moreover,
    this loads all of the already stored degradations. For each tuple of the change
    location and change type, this saves only one change record.

    :param str base_dir: base directory, where the degradations will be stored
    :param str minor_version: minor version for which we are storing the degradations
    :param degradation_list:
    :return:
    """
    already_saved_changes = load_degradation_list_for(base_dir, minor_version)

    list_of_registered_changes = dict()
    degradation_list.extend(already_saved_changes)
    for deg_info, cmdstr, source in degradation_list[::-1]:
        info_string = " ".join([
            deg_info.to_storage_record(),
            source,
            cmdstr
        ])
        uid = (deg_info.location, deg_info.type)
        list_of_registered_changes[uid] = info_string

    # Sort the changes
    to_be_stored_changes = sorted(list(list_of_registered_changes.values()))

    # Store the changes in the file
    minor_dir, minor_storage_file = store.split_object_name(base_dir, minor_version, ".changes")
    store.touch_dir(minor_dir)
    store.touch_file(minor_storage_file)
    with open(minor_storage_file, 'w') as write_handle:
        write_handle.write("\n".join(to_be_stored_changes))


def parse_changelog_line(line):
    """Parses one changelog record into the triple of degradation info, command string and minor.

    :param str line: input line from one change log
    :return: triple (degradation info, command string, minor version)
    """
    tokens = LINE_PARSING_REGEX.match(line)
    deg_info = DegradationInfo(
        PerformanceChange[tokens.group('result')],
        tokens.group('type'),
        tokens.group('location'),
        tokens.group('from'),
        tokens.group('to'),
        tokens.group('ctype'),
        float(tokens.group('crate'))
    )
    return deg_info, tokens.group('cmdstr'), tokens.group('minor')


def load_degradation_list_for(base_dir, minor_version):
    """Loads a list of degradations stored for the minor version.

    This opens a file in the .perun/objects directory in the minor version subdirectory with the
    extension ".changes". The file is basically a log of degradation records separated by
    white spaces in ascii coding.

    :param str base_dir: directory to the storage of the objects
    :param str minor_version:
    :return: list of triples (DegradationInfo, command string, minor version source)
    """
    minor_dir, minor_storage_file = store.split_object_name(base_dir, minor_version, ".changes")
    store.touch_dir(minor_dir)
    store.touch_file(minor_storage_file)
    with open(minor_storage_file, 'r') as read_handle:
        lines = read_handle.readlines()

    degradation_list = []
    for line in lines:
        parsed_triple = parse_changelog_line(line.strip())
        degradation_list.append(parsed_triple)
    return degradation_list


def profiles_to_queue(pcs, minor_version):
    """Retrieves the list of profiles corresponding to minor version and transforms them to map.

    The map represents both the queue and also provides the mapping of configurations to profiles.

    :param PCS pcs: storage of the perun
    :param minor_version: minor version for which we are retrieving the profile queue
    :returns: dictionary mapping configurations of profiles to the actual profiles
    """
    minor_version_profiles = commands.get_minor_version_profiles(pcs, minor_version)
    return {
        profile.config_tuple: profile for profile in minor_version_profiles
    }


def print_configuration(configuration):
    """Helper function for printing information about configuration of given profile

    :param tuple configuration: configuration tuple (collector, cmd, args, workload, postprocessors)
    """
    print("  > collected by ", end='')
    log.cprint("{}".format(configuration[0]), 'magenta', attrs=['bold'])
    if configuration[4]:
        print("+", end='')
        log.cprint("{}".format(configuration[4]), 'magenta', attrs=['bold'])
    print(" for cmd: '$ {}'".format(profiles.config_tuple_to_cmdstr(configuration)))


def get_degradation_change_colours(degradation_result):
    """Returns the tuple of two colours w.r.t degradation results.

    If the change was optimization (or possible optimization) then we print the first model as
    red and the other by green (since we went from better to worse model). On the other hand if the
    change was degradation, then we print the first one green (was better) and the other as red
    (is now worse). Otherwise (for Unknown and no change) we keep the stuff yellow, though this
    is not used at all

    :param PerformanceChange degradation_result: change of the performance
    :returns: tuple of (from model string colour, to model string colour)
    """
    if degradation_result in (
            PerformanceChange.Optimization, PerformanceChange.MaybeOptimization
    ):
        return 'red', 'green'
    elif degradation_result in (
            PerformanceChange.Degradation, PerformanceChange.MaybeDegradation
    ):
        return 'green', 'red'
    else:
        return 'yellow', 'yellow'


def print_degradation_results(deg_info, left_border="| ", indent=4):
    """Helper function for printing results of degradation detection

    :param DegradationInfo deg_info: results of degradation detected in given profile
    :param str left_border: string which is outputed on the left border of the screen
    :param int indent: indent of the output
    """
    # We do not print the information about no change, if the verbosity is not at least info level
    if log.is_verbosity_below(log.VERBOSE_INFO) and deg_info.result == PerformanceChange.NoChange:
        return
    print(left_border + ' '*indent + '  - ', end='')
    # Print the actual result
    log.cprint(
        '{}'.format(CHANGE_STRINGS[deg_info.result]).ljust(20),
        CHANGE_COLOURS[deg_info.result], attrs=['bold']
    )
    # Print the location of the degradation
    print(' at ', end='')
    log.cprintln('{}'.format(deg_info.location), 'white', attrs=['bold'])
    # Print the exact rate of degradation and the confidence (if there is any
    if deg_info.result != PerformanceChange.NoChange:
        from_colour, to_colour = get_degradation_change_colours(deg_info.result)
        print(left_border + ' '*indent + '      from: ', end='')
        log.cprint('{}'.format(deg_info.from_baseline), from_colour, attrs=[])
        print(' -> to: ', end='')
        log.cprint('{}'.format(deg_info.to_target), to_colour, attrs=[])
        if deg_info.confidence_type != 'no':
            print(' (with confidence ', end='')
            log.cprint(
                '{} = {}'.format(
                    deg_info.confidence_type, deg_info.confidence_rate),
                'white', attrs=['bold']
            )
            print(')', end='')
        print('')


def process_profile_pair(baseline_profile, target_profile, profile_config, left_border="| ", indent=4):
    """Helper function for processing pair of baseline and target profile.

    The function wraps the actual check for the found degradation, printing of the results and
    of some initial information (the configuration of profiles).

    :param object baseline_profile: either dictionary or ProfileInfo object, representing the
        baseline profile, i.e. the predecessor we are testing against
    :param target_profile: either dictionary or ProfileInfo object, representing the target,
        i.e. the profile where we are checking for performance changes
    :param tuple profile_config: profile configuration (should be the same for both profiles)
    :param str left_border: symbols printed on the left border of the report
    :param int indent: indent of the rest of the information
    :return: iterable stream of degradation propagated from profiles
    """
    print(left_border, end='')
    print_configuration(profile_config)
    found_change = False
    for degradation in degradation_between_profiles(baseline_profile, target_profile, left_border):
        found_change = found_change or degradation.result != PerformanceChange.NoChange
        print_degradation_results(degradation, left_border, indent)
        yield degradation
    if not found_change and log.is_verbosity_below(log.VERBOSE_INFO):
        print(left_border + ' '*indent + '  - ', end='')
        log.cprint(CHANGE_STRINGS[PerformanceChange.NoChange],
                   CHANGE_COLOURS[PerformanceChange.NoChange], attrs=['bold'])
        print(' detected')


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
        runner.run_matrix_job([minor_version])
        pre_collect_profiles.minor_version_cache.add(minor_version.checksum)


def degradation_in_minor(minor_version):
    """Checks for degradation according to the profiles stored for the given minor version.

    :param str minor_version: representation of head point of degradation checking
    :returns: tuple (degradation result, degradation location, degradation rate)
    """
    pcs = PCS(store.locate_perun_dir_on(os.getcwd()))
    minor_version_info = vcs.get_minor_version_info(pcs.vcs_type, pcs.vcs_path, minor_version)
    baseline_version_queue = minor_version_info.parents
    log.print_minor_version(minor_version_info)
    pre_collect_profiles(minor_version_info)
    target_profile_queue = profiles_to_queue(pcs, minor_version)
    detected_changes = []
    while target_profile_queue and baseline_version_queue:
        # Pop the nearest baseline
        baseline = baseline_version_queue.pop(0)

        # Enqueue the parents in BFS manner
        baseline_info = vcs.get_minor_version_info(pcs.vcs_type, pcs.vcs_path, baseline)
        baseline_version_queue.extend(baseline_info.parents)

        # Precollect profiles if this is set
        pre_collect_profiles(baseline_info)

        # Print header if there is at least some profile to check against
        baseline_profiles = profiles_to_queue(pcs, baseline)
        if baseline_profiles:
            print("|\\\n| ", end='')
            log.print_minor_version(baseline_info)

        # Iterate through the profiles and check degradation between those of same configuration
        for baseline_config, baseline_profile in baseline_profiles.items():
            target_profile = target_profile_queue.get(baseline_config)
            cmdstr = profiles.config_tuple_to_cmdstr(baseline_config)
            if target_profile:
                # Print information about configuration
                # and extend the list of the detected changes including the configuration
                # and source minor version.
                detected_changes.extend([
                    (deg, cmdstr, baseline_info.checksum) for deg in
                    process_profile_pair(baseline_profile, target_profile, baseline_config)
                    if deg.result != PerformanceChange.NoChange
                ])
                del target_profile_queue[target_profile.config_tuple]
        print('|')

        # Store the detected degradation
        save_degradation_list_for(pcs.get_object_directory(), minor_version, detected_changes)


def degradation_in_history(head):
    """Walks through the minor version starting from the given head, checking for degradation.

    :param str head: starting point of the checked history for degradation.
    :returns: tuple (degradation result, degradation location, degradation rate)
    """
    pcs = PCS(store.locate_perun_dir_on(os.getcwd()))
    print("Running the degradation checks on all history. This might take a while!")
    for minor_version in vcs.walk_minor_versions(pcs.vcs_type, pcs.vcs_path, head):
        degradation_in_minor(minor_version.checksum)


def degradation_between_profiles(baseline_profile, target_profile, left_border="| "):
    """Checks between pair of (baseline, target) profiles, whether the can be degradation detected

    We first find the suitable strategy for the profile configuration and then call the appropriate
    wrapper function.

    :param ProfileInfo baseline_profile: baseline against which we are checking the degradation
    :param ProfileInfo target_profile: profile corresponding to the checked minor version
    :param str left_border: left border of the output
    :returns: tuple (degradation result, degradation location, degradation rate)
    """
    if not isinstance(baseline_profile, dict):
        baseline_profile = profiles.load_profile_from_file(baseline_profile.realpath, False)
    if not isinstance(target_profile, dict):
        target_profile = profiles.load_profile_from_file(target_profile.realpath, False)

    # We run all of the degradation methods suitable for the given configuration of profile
    for degradation_method in get_strategies_for_configuration(baseline_profile):
        print(left_border + "    > applying '{}' method".format(degradation_method))
        yield from utils.dynamic_module_function_call(
            'perun.check', degradation_method, degradation_method, baseline_profile, target_profile
        )


def degradation_between_files(baseline_file, target_file, minor_version):
    """Checks between pair of files (baseline, target) whether there are any changes in performance.

    :param dict baseline_file: baseline profile we are checking against
    :param dict target_file: target profile we are testing
    :param str minor_version: target minor_version
    """
    # First check if the configurations are compatible
    baseline_config = profiles.to_config_tuple(baseline_file)
    target_config = profiles.to_config_tuple(target_file)
    target_minor_version = target_file.get('origin', minor_version)
    if baseline_config != target_config:
        log.error("incompatible configurations '{}' and '{}'".format(
            baseline_config, target_config
        ) + "\n\nPerformance check does not make sense for profiles collected in different ways!")

    detected_changes = [
        (deg, profiles.config_tuple_to_cmdstr(baseline_config), target_minor_version) for deg in
        process_profile_pair(baseline_file, target_file, baseline_config, left_border='', indent=4)
        if deg.result != PerformanceChange.NoChange
    ]

    # Store the detected changes for given minor version
    pcs = PCS(store.locate_perun_dir_on(os.getcwd()))
    save_degradation_list_for(pcs.get_object_directory(), target_minor_version, detected_changes)


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
        'bmoe': 'best_model_order_equality'
    }
    if strategy in short_strings.keys():
        return short_strings[strategy]
    else:
        return strategy


def get_strategies_for_configuration(profile):
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


class DegradationInfo(object):
    """The returned results for performance check methods

    :ivar PerformanceChange result: result of the performance change, either can be optimization,
        degradation, no change, or certain type of unknown
    :ivar str type: string representing the type of the degradation, e.g. "order" degradation
    :ivar str location: location, where the degradation has happened
    :ivar str from_baseline: value or model representing the baseline, i.e. from which the new
        version was optimized or degraded
    :ivar str to_target: value or model representing the target, i.e. to which the new version was
        optimized or degraded
    :ivar str confidence_type: type of the confidence we have in the detected degradation, e.g. r^2
    :ivar float confidence_rate: value of the confidence we have in the detected degradation
    """

    def __init__(self, res, t, loc, fb, tt, ct="no", cr=0.0):
        """Each degradation consists of its results, the location, where the change has happened
        (this is e.g. the unique id of the resource, like function or concrete line), then the pair
        of best models for baseline and target, and the information about confidence.

        E.g. for models we can use coefficient of determination as some kind of confidence, e.g. the
        higher the confidence the more likely we predicted successfully the degradation or
        optimization.

        :param PerformanceChange res: result of the performance change, either can be optimization,
            degradation, no change, or certain type of unknown
        :param str t: string representing the type of the degradation, e.g. "order" degradation
        :param str loc: location, where the degradation has happened
        :param str fb: value or model representing the baseline, i.e. from which the new version was
            optimized or degraded
        :param str tt: value or model representing the target, i.e. to which the new version was
            optimized or degraded
        :param str ct: type of the confidence we have in the detected degradation, e.g. r^2
        :param float cr: value of the confidence we have in the detected degradation
        """
        self.result = res
        self.type = t
        self.location = loc
        self.from_baseline = fb
        self.to_target = tt
        self.confidence_type = ct
        self.confidence_rate = cr

    def to_storage_record(self):
        """Transforms the degradation info to a storage_record

        :return: string representation of the degradation as a stored record in the file
        """
        return "{} {} {} {} {} {} {}".format(
            self.location,
            self.result,
            self.type,
            self.from_baseline,
            self.to_target,
            self.confidence_type,
            self.confidence_rate
        )
