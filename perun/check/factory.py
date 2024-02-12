"""
Collection of global methods for detection of performance changes
"""
from __future__ import annotations

# Standard Imports
import contextlib
import distutils.util as dutils
import os
import re

from typing import Any, Iterable, Protocol, TYPE_CHECKING

# Third-Party Imports

# Perun Imports
from perun.logic import config, pcs, runner, store
from perun.select.abstract_base_selection import AbstractBaseSelection
from perun.check.methods import (
    average_amount_threshold,
    best_model_order_equality,
    exclusive_time_outliers,
    fast_check,
    integral_comparison,
    linear_regression,
    local_statistics,
    polynomial_regression,
)
from perun.utils import decorators, log
from perun.utils.structs import (
    DetectionChangeResult,
    DegradationInfo,
    PerformanceChange,
    MinorVersion,
    ModelRecord,
)
from perun.utils.exceptions import UnsupportedModuleException
import perun.profile.helpers as profiles

if TYPE_CHECKING:
    from perun.profile.factory import Profile
    from perun.profile.helpers import ProfileInfo

# Minimal confidence rate from both models to perform the detection
_MIN_CONFIDENCE_RATE = 0.15


class CallableDetectionMethod(Protocol):
    """Protocol for Callable detection method"""

    def __call__(
        self,
        uid: str,
        baseline_model: ModelRecord,
        target_model: ModelRecord,
        target_profile: Profile,
        **kwargs: Any,
    ) -> DetectionChangeResult:
        """Call Function"""


def get_supported_detection_models_strategies() -> list[str]:
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
    return [
        "best-model",
        "best-param",
        "best-nonparam",
        "all-param",
        "all-nonparam",
        "all-models",
        "best-both",
    ]


def profiles_to_queue(
    minor_version: str,
) -> dict[tuple[str, str, str, str], ProfileInfo]:
    """Retrieves the list of profiles corresponding to minor version and transforms them to map.

    The map represents both the queue and also provides the mapping of configurations to profiles.

    :param minor_version: minor version for which we are retrieving the profile queue
    :returns: dictionary mapping configurations of profiles to the actual profiles
    """
    minor_version_profiles = profiles.load_list_for_minor_version(minor_version)
    return {profile.config_tuple: profile for profile in minor_version_profiles}


@decorators.static_variables(minor_version_cache=set())
def pre_collect_profiles(minor_version: MinorVersion) -> None:
    """For given minor version, collects performance profiles according to the job matrix

    This is applied if the profiles were not already collected by this function for the given minor,
    and if the key :ckey:`degradation.collect_before_check` is set to true value.

    TODO: What if error happens during run matrix? This should be caught and solved

    :param MinorVersion minor_version: minor version for which we are collecting the data
    """
    should_precollect = dutils.strtobool(
        str(config.lookup_key_recursively("degradation.collect_before_check", "false"))
    )
    if should_precollect and minor_version.checksum not in pre_collect_profiles.minor_version_cache:
        # Set the registering after run to true for this run
        config.runtime().set("profiles.register_after_run", "true")
        # Actually collect the resources
        collect_to_log = dutils.strtobool(
            str(config.lookup_key_recursively("degradation.log_collect", "false"))
        )
        log_file = os.path.join(pcs.get_log_directory(), f"{minor_version.checksum}-precollect.log")
        out = log_file if collect_to_log else os.devnull
        with open(out, "w") as black_hole:
            with contextlib.redirect_stdout(black_hole):
                try:
                    runner.run_matrix_job([minor_version])
                except SystemExit as system_exit:
                    log.warn(
                        f"could not precollect data for {minor_version.checksum[:6]} version: {system_exit}"
                    )
        pre_collect_profiles.minor_version_cache.add(minor_version.checksum)


def degradation_in_minor(
    minor_version: str, quiet: bool = False
) -> list[tuple[DegradationInfo, str, str]]:
    """Checks for degradation according to the profiles stored for the given minor version.

    :param str minor_version: representation of head point of degradation checking
    :param bool quiet: if set to true then nothing will be printed
    :returns: list of found changes
    """
    log.major_info(f"Checking Version {minor_version}")
    selection: AbstractBaseSelection = pcs.selection()
    minor_version_info = pcs.vcs().get_minor_version_info(minor_version)

    # Precollect profiles for all near versions
    pre_collect_profiles(minor_version_info)
    for parent_version in selection.get_parents(minor_version_info):
        pre_collect_profiles(parent_version)

    profile_queue = profiles_to_queue(minor_version)
    detected_changes = []

    for target_config, target_profile_info in profile_queue.items():
        # Iterate through the profiles and check degradation between those of same configuration
        target_prof = store.load_profile_from_file(target_profile_info.realpath, False, True)
        cmdstr = profiles.config_tuple_to_cmdstr(target_config)

        for baseline_info, baseline_profile_info in selection.get_profiles(
            minor_version_info, target_prof
        ):
            baseline_prof = store.load_profile_from_file(
                baseline_profile_info.realpath, False, True
            )
            for deg in degradation_between_profiles(baseline_prof, target_prof, "best-model"):
                if deg.result != PerformanceChange.NoChange:
                    detected_changes.append((deg, cmdstr, baseline_info.checksum))

    # Store the detected degradation
    store.save_degradation_list_for(pcs.get_object_directory(), minor_version, detected_changes)
    if not quiet:
        log.print_list_of_degradations(detected_changes)
    return detected_changes


@log.print_elapsed_time
def degradation_in_history(head: str) -> list[tuple[DegradationInfo, str, str]]:
    """Walks through the minor version starting from the given head, checking for degradation.

    :param str head: starting point of the checked history for degradation.
    :returns: tuple (degradation result, degradation location, degradation rate)
    """
    log.major_info("Checking Whole History")
    log.minor_info("This might take a while")
    detected_changes = []
    version_selection: AbstractBaseSelection = pcs.selection()
    with log.History(head) as history:
        for minor_version in pcs.vcs().walk_minor_versions(head):
            history.progress_to_next_minor_version(minor_version)
            newly_detected_changes = []
            if version_selection.should_check_version(minor_version):
                newly_detected_changes = degradation_in_minor(minor_version.checksum, True)
                log.print_short_change_string(
                    log.count_degradations_per_group(newly_detected_changes)
                )
            else:
                log.skipped()
            history.finish_minor_version(minor_version, newly_detected_changes)
            log.print_list_of_degradations(newly_detected_changes)
            detected_changes.extend(newly_detected_changes)
            history.flush(with_border=True)
    log.newline()
    log.print_short_summary_of_degradations(detected_changes)
    return detected_changes


def degradation_between_profiles(
    baseline_profile: Profile, target_profile: Profile, models_strategy: str
) -> Iterable[DegradationInfo]:
    """Checks between a pair of (baseline, target) profiles, whether there can be degradation detected

    We first find the suitable strategy for the profile configuration and then call the appropriate
    wrapper function.

    :param ProfileInfo baseline_profile: baseline against which we are checking the degradation
    :param ProfileInfo target_profile: profile corresponding to the checked minor version
    :param str models_strategy: name of detection models strategy to obtains relevant model kinds
    :returns: tuple (degradation result, degradation location, degradation rate)
    """
    # We run all degradation methods suitable for the given configuration of profile
    for degradation_method in get_strategies_for(baseline_profile):
        yield from run_degradation_check(
            degradation_method, baseline_profile, target_profile, models_strategy=models_strategy
        )


def run_degradation_check(
    degradation_method: str, baseline_profile: Profile, target_profile: Profile, **kwargs: Any
) -> Iterable[DegradationInfo]:
    """Factory for running degradations checks

    Constructs from string an Checker object and runs the check method
    """
    if degradation_method == "average_amount_threshold":
        yield from average_amount_threshold.AverageAmountThreshold().check(
            baseline_profile, target_profile, **kwargs
        )
    elif degradation_method == "best_model_order_equality":
        yield from best_model_order_equality.BestModelOrderEquality().check(
            baseline_profile, target_profile, **kwargs
        )
    elif degradation_method == "exclusive_time_outliers":
        yield from exclusive_time_outliers.ExclusiveTimeOutliers().check(
            baseline_profile, target_profile, **kwargs
        )
    elif degradation_method == "fast_check":
        yield from fast_check.FastCheck().check(baseline_profile, target_profile, **kwargs)
    elif degradation_method == "integral_comparison":
        yield from integral_comparison.IntegralComparison().check(
            baseline_profile, target_profile, **kwargs
        )
    elif degradation_method == "linear_regression":
        yield from linear_regression.LinearRegression().check(
            baseline_profile, target_profile, **kwargs
        )
    elif degradation_method == "local_statistics":
        yield from local_statistics.LocalStatistics().check(
            baseline_profile, target_profile, **kwargs
        )
    elif degradation_method == "polynomial_regression":
        yield from polynomial_regression.PolynomialRegression().check(
            baseline_profile, target_profile, **kwargs
        )
    else:
        raise UnsupportedModuleException(f"{degradation_method}")


@log.print_elapsed_time
def degradation_between_files(
    baseline_file: Profile,
    target_file: Profile,
    minor_version: str,
    models_strategy: str,
    force: bool = False,
) -> None:
    """Checks between a pair of files (baseline, target) whether there are any changes in performance.

    :param dict baseline_file: baseline profile we are checking against
    :param dict target_file: target profile we are testing
    :param str minor_version: targ minor_version
    :param str models_strategy: name of detection models strategy to obtains relevant model kinds
    :param bool force: force profiles check despite different configurations
    :returns None: no return value
    """
    log.major_info("Checking two compatible profiles")
    # First check if the configurations are compatible
    baseline_config = profiles.to_config_tuple(baseline_file)
    target_config = profiles.to_config_tuple(target_file)
    target_minor_version = target_file.get("origin", minor_version)
    if not force:
        if baseline_config != target_config:
            log.error(
                f"incompatible configurations '{baseline_config}' and '{target_config}'\n\n"
                f"Performance check does not make sense for profiles collected in different ways!"
            )

    detected_changes = []
    for deg in degradation_between_profiles(baseline_file, target_file, models_strategy):
        if deg.result != PerformanceChange.NoChange:
            detected_changes.append(
                (deg, profiles.config_tuple_to_cmdstr(baseline_config), target_minor_version)
            )

    # Store the detected changes for given minor version
    store.save_degradation_list_for(
        pcs.get_object_directory(), target_minor_version, detected_changes
    )
    log.newline()
    log.print_list_of_degradations(detected_changes)
    log.print_short_summary_of_degradations(detected_changes)


def is_rule_applicable_for(rule: dict[str, Any], configuration: Profile) -> bool:
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
        if key == "method":
            continue
        if key == "postprocessor":
            postprocessors = [post["name"] for post in configuration["postprocessors"]]
            if value not in postprocessors:
                return False
        elif key == "collector":
            if configuration["collector_info"]["name"] != value:
                return False
        elif configuration["header"].get(key, None) != value:
            return False
    return True


def parse_strategy(strategy: str) -> str:
    """Translates the given string to the real name of the strategy---callable function.

    This handles short names for the degradation strategies.

    :param str strategy: name of the strategy
    :return:
    """
    short_strings = {
        "aat": "average_amount_threshold",
        "bmoe": "best_model_order_equality",
        "preg": "polynomial_regression",
        "lreg": "linear_regression",
        "fast": "fast_check",
        "int": "integral_comparison",
        "loc": "local_statistics",
        "eto": "exclusive_time_outliers",
    }
    return short_strings.get(strategy, strategy)


def get_strategies_for(profile: Profile) -> Iterable[str]:
    """Retrieves the best strategy for the given profile configuration

    :param Profile profile: Profile information with configuration tuple
    :return: method to be used for checking degradation between profiles of
        the same configuration type
    """
    # Retrieve the application strategy
    application_strategy = config.lookup_key_recursively("degradation.apply", default="all")

    # Retrieve all strategies from configuration
    strategies = config.gather_key_recursively("degradation.strategies")
    already_applied_strategies = []
    first_applied = False
    for strategy in strategies:
        if (
            (application_strategy == "all" or not first_applied)
            and is_rule_applicable_for(strategy, profile)
            and "method" in strategy.keys()
            and strategy["method"] not in already_applied_strategies
        ):
            first_applied = True
            method = parse_strategy(strategy["method"])
            already_applied_strategies.append(method)
            yield method


def run_detection_with_strategy(
    detection_method: CallableDetectionMethod,
    baseline_profile: Profile,
    target_profile: Profile,
    models_strategy: str,
) -> Iterable[DegradationInfo]:
    """
    The wrapper for running detection methods for all kinds of models.

    According to the given `models_strategy` this function obtains the relevant
    models from both given profiles and subsequently calls the function, that
    ensure the executing of detection between them. In the end, this function
    returns the structure `DegradationInfo` with the detected information.

    :param callable detection_method: method to execute the detection logic with the call template
    :param Profile baseline_profile: baseline profile against which we are checking the degradation
    :param Profile target_profile: target profile corresponding to the checked minor version
    :param str models_strategy: name of detection models strategy to obtains relevant model kinds
    :returns: tuple - degradation result (structure DegradationInfo)
    """
    if models_strategy in ("all-models", "best-both"):
        partial_strategies = (
            ["all-param", "all-nonparam"]
            if models_strategy == "all-models"
            else ["best-param", "best-nonparam"]
        )
        for partial_strategy in partial_strategies:
            for degradation_info in run_detection_with_strategy(
                detection_method, baseline_profile, target_profile, partial_strategy
            ):
                yield degradation_info
    else:
        baseline_models = baseline_profile.all_filtered_models(models_strategy)
        target_models = target_profile.all_filtered_models(models_strategy)
        for degradation_info in _run_detection_for_models(
            detection_method,
            baseline_profile,
            baseline_models,
            target_profile,
            target_models,
            models_strategy=models_strategy,
        ):
            yield degradation_info


def _run_detection_for_models(
    detection_method: CallableDetectionMethod,
    baseline_profile: Profile,
    baseline_models: dict[str, ModelRecord],
    target_profile: Profile,
    target_models: dict[str, ModelRecord],
    **kwargs: Any,
) -> Iterable[DegradationInfo]:
    """
    The runner of detection methods for a set of models pairs (base and targ).

    The method performs the degradation check between two relevant models, obtained from
    the given set of models. According to the match of the UIDs of the models is called
    the detection method, that returns a dictionary with information about the changes
    from the comparison of these models. This method subsequently return the structure
    DegradationInfo with relevant items about detected changes between compared models.

    :param callable detection_method: method to execute the detection logic with the call template
    :param Profile baseline_profile: base profile against which we are checking the degradation
    :param dict baseline_models: set of models to comparison from base profile
    :param Profile target_profile: targ profile corresponding to the checked minor version
    :param dict target_models: set of models to comparison from targ profile
    :param kwargs: contains name of detection models strategy to obtains relevant model kinds
    :return: tuple - degradation result (structure DegradationInfo)
    """
    uid_flag = kwargs["models_strategy"] in ("all-param", "all-nonparam")
    for uid, target_model in target_models.items():
        baseline_model = baseline_models.get(uid)

        if (
            baseline_model
            and round(min(baseline_model.r_square, target_model.r_square), 2)
            >= _MIN_CONFIDENCE_RATE
        ):
            change_result = detection_method(
                uid,
                baseline_model,
                target_model,
                baseline_profile=baseline_profile,
                target_profile=target_profile,
            )

            yield DegradationInfo(
                res=change_result.result,
                loc=re.sub(baseline_model.type + "$", "", uid) if uid_flag else uid,
                fb=baseline_model.type,
                tt=target_model.type,
                rd=change_result.relative_rate,
                ct="r_square",
                cr=round(min(baseline_model.r_square, target_model.r_square), 2),
                pi=change_result.partial_intervals,
            )
