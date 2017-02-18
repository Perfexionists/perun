"""Git is an wrapper over git repository used within perun control system

Contains concrete implementation of the function needed by perun to extract informations and work
with version control systems.
"""

import perun.utils.log as perun_log
import perun.utils as utils

__author__ = "Tomas Fiedor"


def _init(vcs_path, vcs_init_params):
    """
    Arguments:
        vcs_path(path): path where the vcs will be initialized
        vcs_init_params(list): list of additional params for initialization of the vcs

    Returns:
        bool: true if the vcs was successfully initialized at vcs_path
    """
    commands = ["git", "init"]
    if vcs_init_params is not None:
        commands.extend(vcs_init_params)

    if utils.run_external_command(commands):
        perun_log.warn("Error while initializing git directory")
        return False

    return True


def _get_minor_head(git_path):
    """
    Arguments:
        git_path(path): path to git, where we are obtaining head for minor version
    """
    perun_log.msg_to_stdout("Retrieving HEAD from {}".format(git_path), 2)
    # FIXME: Temporal return value
    return "2ae3bfa80f009b21b3a1ca2472bcd8d5d8bbbb27"
