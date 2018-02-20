import perun.profile.factory as profiles
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


@pass_pcs
def degradation_in_minor(pcs, minor_version):
    """Checks for degradation according to the profiles stored for the given minor version.

    :param str minor_version: representation of head point of degradation checking
    :returns: tuple (degradation result, degradation location, degradation rate)
    """
    target_profile_queue = profiles_to_queue(pcs, minor_version)
    baseline_version_queue = vcs.get_minor_version_info(pcs.vcs_type, pcs.vcs_path, minor_version).parents

    if baseline_version_queue:
        print("Checking degradation in '{}' minor version".format(minor_version))
    while target_profile_queue and baseline_version_queue:
        # Pop the nearest baseline
        baseline = baseline_version_queue.pop(0)
        baseline_profiles = profiles_to_queue(pcs, baseline)

        # Enqueue the parents in BFS manner
        baseline_version_queue.extend(
            vcs.get_minor_version_info(pcs.vcs_type, pcs.vcs_path, baseline).parents
        )

        # Iterate through the profiles and check degradation between those of same configuration
        for baseline_config, baseline_profile in baseline_profiles.items():
            target_profile = target_profile_queue.get(baseline_config)
            if target_profile:
                degradation_between_profiles(baseline_profile, target_profile)
                del target_profile_queue[target_profile.config_tuple]


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
    utils.dynamic_module_function_call(
        'perun.check', degradation_method, degradation_method, baseline_profile, target_profile
    )


def get_strategy_for_configuration(profile):
    """Retrieves the best strategy for the given profile configuration

    :param ProfileInfo profile: Profile information with configuration tuple
    :return: method to be used for checking degradation between profiles of
        the same configuration type
    """
    return "best_model_order_equality"
