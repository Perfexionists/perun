"""Git is an wrapper over git repository used within perun control system

Contains concrete implementation of the function needed by perun to extract informations and work
with version control systems.
"""

import subprocess

import perun.core.logic.store as store
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
    Fixme: This would be better to internally use rev-parse ;)
    Arguments:
        git_path(path): path to git, where we are obtaining head for minor version
    """
    perun_log.msg_to_stdout("Retrieving HEAD from {}".format(git_path), 2)

    # Read contents of head through the subprocess and git rev-parse HEAD
    proc = subprocess.Popen("git rev-parse HEAD", cwd=git_path, shell=True, stdout=subprocess.PIPE,
                            universal_newlines=True)
    git_head = proc.stdout.readlines()[0].strip()
    proc.wait()

    assert store.is_sha1(git_head)
    return git_head
