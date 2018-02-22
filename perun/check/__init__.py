from enum import Enum

import perun.profile.factory as profiles
import perun.utils.log as log
import perun.logic.commands as commands
import perun.utils as utils
import perun.vcs as vcs

from perun.logic.pcs import pass_pcs

__author__ = 'Tomas Fiedor'


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


def print_minor_version(minor_version):
    """Helper function for printing minor version to the degradation output

    Currently printed in form of:

    * sha[:6]: desc

    :param MinorVersion minor_version: informations about minor version
    """
    print("* ", end='')
    log.cprint("{}".format(
        minor_version.checksum[:6]
    ), 'yellow', attrs=[])
    print(": {}".format(
        minor_version.desc.split("\n")[0].strip()
    ))


def print_configuration(config):
    """Helper function for printing information about configuration of given profile

    :param tuple config: configuration tuple (collector, cmd, args, workload, postprocessors)
    """
    print("  > collected by ", end='')
    log.cprint("{}".format(config[0]), 'magenta', attrs=['bold'])
    if config[4]:
        print("+", end='')
        log.cprint("{}".format(config[4]), 'magenta', attrs=['bold'])
    print(" for cmd: '$ {}'".format(" ".join(config[1:4])))


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


def print_degradation_results(degradation):
    """Helper function for printing results of degradation detection

    :param DegradationInfo degradation: results of degradation detected in given profile
    """
    print('|   - ', end='')
    # Print the actual result
    log.cprint(
        '{}'.format(CHANGE_STRINGS[degradation.result]).ljust(20),
        CHANGE_COLOURS[degradation.result], attrs=['bold']
    )
    # Print the location of the degradation
    print(' at ', end='')
    log.cprintln('{}'.format(degradation.location), 'white', attrs=['bold'])
    # Print the exact rate of degradation and the confidence (if there is any
    if degradation.result != PerformanceChange.NoChange:
        from_colour, to_colour = get_degradation_change_colours(degradation.result)
        print('|       from: ', end='')
        log.cprint('{}'.format(degradation.from_baseline), from_colour, attrs=[])
        print(' -> to: ', end='')
        log.cprint('{}'.format(degradation.to_target), to_colour, attrs=[])
        if degradation.confidence_type != 'no':
            print(' (with confidence ', end='')
            log.cprint(
                '{} = {}'.format(
                    degradation.confidence_type, degradation.confidence_rate),
                'white', attrs=['bold']
            )
            print(')', end='')
        print('')


@pass_pcs
def degradation_in_minor(pcs, minor_version):
    """Checks for degradation according to the profiles stored for the given minor version.

    :param str minor_version: representation of head point of degradation checking
    :returns: tuple (degradation result, degradation location, degradation rate)
    """
    target_profile_queue = profiles_to_queue(pcs, minor_version)
    minor_version_info = vcs.get_minor_version_info(pcs.vcs_type, pcs.vcs_path, minor_version)
    baseline_version_queue = minor_version_info.parents
    print_minor_version(minor_version_info)
    while target_profile_queue and baseline_version_queue:
        # Pop the nearest baseline
        baseline = baseline_version_queue.pop(0)

        # Enqueue the parents in BFS manner
        baseline_info = vcs.get_minor_version_info(pcs.vcs_type, pcs.vcs_path, baseline)
        baseline_version_queue.extend(baseline_info.parents)

        # Print header if there is at least some profile to check against
        baseline_profiles = profiles_to_queue(pcs, baseline)
        if baseline_profiles:
            print("|\\\n| ", end='')
            print_minor_version(baseline_info)

        # Iterate through the profiles and check degradation between those of same configuration
        for baseline_config, baseline_profile in baseline_profiles.items():
            target_profile = target_profile_queue.get(baseline_config)
            if target_profile:
                # Print information about configuration
                print("| ", end='')
                print_configuration(baseline_config)
                for degradation in degradation_between_profiles(baseline_profile, target_profile):
                    print_degradation_results(degradation)
                del target_profile_queue[target_profile.config_tuple]
        print('|')


@pass_pcs
def degradation_in_history(pcs, head):
    """Walks through the minor version starting from the given head, checking for degradation.

    :param head: starting point of the checked history for degradation.
    :returns: tuple (degradation result, degradation location, degradation rate)
    """
    for minor_version in vcs.walk_minor_versions(pcs.vcs_type, pcs.vcs_path, head):
        degradation_in_minor(minor_version.checksum)


def degradation_between_profiles(baseline_profile, target_profile):
    """Checks between pair of (baseline, target) profiles, whether the can be degradation detected

    We first find the suitable strategy for the profile configuration and then call the appropriate
    wrapper function.

    :param ProfileInfo baseline_profile: baseline against which we are checking the degradation
    :param ProfileInfo target_profile: profile corresponding to the checked minor version
    :returns: tuple (degradation result, degradation location, degradation rate)
    """
    if type(baseline_profile) is not dict:
        baseline_profile = profiles.load_profile_from_file(baseline_profile.realpath, False)
    if type(target_profile) is not dict:
        target_profile = profiles.load_profile_from_file(target_profile.realpath, False)
    degradation_method = get_strategy_for_configuration(baseline_profile)
    return utils.dynamic_module_function_call(
        'perun.check', degradation_method, degradation_method, baseline_profile, target_profile
    )


def get_strategy_for_configuration(profile):
    """Retrieves the best strategy for the given profile configuration

    :param ProfileInfo profile: Profile information with configuration tuple
    :return: method to be used for checking degradation between profiles of
        the same configuration type
    """
    return "best_model_order_equality"


class DegradationInfo(object):
    def __init__(self, res, t, loc, fb, tt, ct="no", cr=0):
        self.result = res
        self.type = t
        self.location = loc
        self.from_baseline = fb
        self.to_target = tt
        self.confidence_type = ct
        self.confidence_rate = cr

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
