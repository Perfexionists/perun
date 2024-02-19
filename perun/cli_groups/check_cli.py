"""Group of CLI commands used for detecting degradations in VCS history"""
from __future__ import annotations

# Standard Imports
from typing import Any, TYPE_CHECKING, Optional

# Third-Party Imports
import click

# Perun Imports
from perun.logic import pcs, config as perun_config
from perun.utils import log
from perun.utils.common import cli_kit, common_kit
import perun.check.factory as check

if TYPE_CHECKING:
    from perun.profile.factory import Profile


@click.group("check")
@click.option(
    "--force",
    "-f",
    is_flag=True,
    default=False,
    help=(
        "Force comparison of the selected profiles even if their configuration"
        "does not match. This may be necessary when, e.g., different project"
        "versions build binaries with version information in their name"
        "(python3.10 and python3.11), thus failing the consistency check. "
    ),
)
@click.option(
    "--compute-missing",
    "-c",
    callback=cli_kit.set_config_option_from_flag(
        perun_config.runtime, "degradation.collect_before_check"
    ),
    is_flag=True,
    default=False,
    help=(
        "whenever there are missing profiles in the given point of history"
        " the matrix will be rerun and new generated profiles assigned."
    ),
)
@click.option(
    "--models-type",
    "-m",
    nargs=1,
    required=False,
    multiple=False,
    type=click.Choice(check.get_supported_detection_models_strategies()),
    default=check.get_supported_detection_models_strategies()[0],
    help=(
        "The detection models strategies predict the way of executing "
        "the detection between two profiles, respectively between relevant "
        "kinds of its models. Available only in the following detection "
        "methods: Integral Comparison (IC) and Local Statistics (LS)."
    ),
)
def check_group(**_: Any) -> None:
    """Applies for the points of version history checks for possible performance changes.

    This command group either runs the checks for one point of history (``perun check head``) or for
    the whole history (``perun check all``). For each minor version (called the `target`) we iterate
    over the registered profiles and try to find a predecessor minor version (called the
    `baseline`) with profile of the same configuration (by configuration we mean the tuple of
    collector, postprocessors, command, arguments and workloads) and run the checks according to the
    rules set in the configurations.

    The rules are specified as an ordered list in the configuration by
    :ckey:`degradation.strategies`, where the keys correspond to the configuration (or the type) and
    key `method` specifies the actual method used for checking for performance changes. The applied
    methods can then be either specified by the full name or by its short string consisting of all
    first letter of the function name.

    The example of configuration snippet that sets rules and strategies for one project can be as
    follows:

    .. code-block:: yaml

        \b

        degradation:
          apply: first
          strategies:
            - type: mixed
              postprocessor: regression_analysis
              method: bmoe
            - cmd: mybin
              type: memory
              method: bmoe
            - method: aat

    Currently, we support the following methods:

        \b

        1. Best Model Order Equality (BMOE)
        2. Average Amount Threshold (AAT)
        3. Polynomial Regression (PREG)
        4. Linear Regression (LREG)
        5. Fast Check (FAST)
        6. Integral Comparison (INT)
        7. Local Statistics (LOC)
        8. Exclusive Time Outliers (ETO)

    """
    should_precollect = common_kit.strtobool(
        str(perun_config.lookup_key_recursively("degradation.collect_before_check", "false"))
    )
    precollect_to_log = common_kit.strtobool(
        str(perun_config.lookup_key_recursively("degradation.log_collect", "false"))
    )
    if should_precollect:
        log.major_info("Precollecting Profiles")
        collect_before_check = log.in_color("degradation.collect_before_check", "white", ["bold"])
        log.minor_success(f"{log.highlight(collect_before_check)}", "true")
        log.minor_info("Missing profiles will be now collected")
        log.increase_indent()
        log.minor_info(f"Run {log.cmd_style('perun config edit')} to modify the job matrix")
        log.decrease_indent()
        if precollect_to_log:
            log_directory = log.in_color(pcs.get_log_directory(), "white", ["bold"])
            log.minor_status(
                "The progress will be stored in log", status=log.path_style(log_directory)
            )
        else:
            log.minor_info(f"The progress will be redirected to {log.highlight('black hole')}")


@check_group.command("head")
@click.argument(
    "head_minor",
    required=False,
    metavar="<hash>",
    nargs=1,
    callback=cli_kit.lookup_minor_version_callback,
    default="HEAD",
)
def check_head(head_minor: str = "HEAD") -> None:
    """Checks for changes in performance between specified minor version (or current `head`)
    and its predecessor minor versions.

    The command iterates over the registered profiles of the specified `minor version`
    (`target`; e.g. the `head`), and tries to find the nearest predecessor minor version
    (`baseline`), where the profile with the same configuration as the tested target profile exists.
    When it finds such a pair, it runs the check according to the strategies set in the
    configuration (see :ref:`degradation-config` or :doc:`config`).

    By default, the ``hash`` corresponds to the `head` of the current project.
    """
    check.degradation_in_minor(head_minor)


@check_group.command("all")
@click.argument(
    "minor_head",
    required=False,
    metavar="<hash>",
    nargs=1,
    callback=cli_kit.lookup_minor_version_callback,
    default="HEAD",
)
def check_all(minor_head: str = "HEAD") -> None:
    """Checks for changes in performance for the specified interval of version history.

    The command crawls through the whole history of project versions starting from the specified
    ``<hash>`` and for registered profiles (corresponding to some `target` minor version)
    tries to find a suitable predecessor profile (corresponding to some `baseline` minor version)
    and runs the performance check according to the set of strategies set in the configuration
    (see :ref:`degradation-config` or :doc:`config`).
    """
    check.degradation_in_history(minor_head)


@check_group.command("profiles")
@click.argument(
    "baseline_profile",
    required=True,
    metavar="<baseline>",
    nargs=1,
    callback=cli_kit.lookup_any_profile_callback,
)
@click.argument(
    "target_profile",
    required=True,
    metavar="<target>",
    nargs=1,
    callback=cli_kit.lookup_any_profile_callback,
)
@click.option(
    "--minor",
    "-m",
    nargs=1,
    default=None,
    is_eager=True,
    callback=cli_kit.lookup_minor_version_callback,
    metavar="<hash>",
    help="Will check the index of different minor version <hash> during the profile lookup.",
)
@click.pass_context
def check_profiles(
    ctx: click.Context,
    baseline_profile: Profile,
    target_profile: Profile,
    minor: Optional[str],
    **_: str,
) -> None:
    """Checks for changes in performance between two profiles.

    The command checks for the changes between two isolate profiles, that can be stored in pending
    profiles, registered in index, or be simply stored in filesystem. Then for the pair of profiles
    <baseline> and <target> the command runs the performance check according to the set of
    strategies set in the configuration (see :ref:`degradation-config` or :doc:`config`).

    <baseline> and <target> profiles will be looked up in the following steps:

        1. If profile is in form ``i@i`` (i.e, an `index tag`), then `ith`
           record registered in the minor version <hash> index will be used.

        2. If profile is in form ``i@p`` (i.e., an `pending tag`), then
           `ith` profile stored in ``.perun/jobs`` will be used.

        3. Profile is looked-up within the minor version <hash> index for a
           match. In case the <profile> is registered there, it will be used.

        4. Profile is looked-up within the ``.perun/jobs`` directory. In case
           there is a match, the found profile will be used.

        5. Otherwise, the directory is walked for any match. Each found match
           is asked for confirmation by user.

    """
    assert ctx.parent is not None and f"impossible happened: {ctx} has no parent"
    check.degradation_between_files(
        baseline_profile,
        target_profile,
        minor,
        ctx.parent.params["models_type"],
        ctx.parent.params["force"],
    )
