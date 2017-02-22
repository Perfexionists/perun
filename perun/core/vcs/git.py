"""Git is an wrapper over git repository used within perun control system

Contains concrete implementation of the function needed by perun to extract informations and work
with version control systems.
"""

import re
import subprocess

import perun.core.logic.store as store
import perun.utils.timestamps as timestamps
import perun.utils.log as perun_log
import perun.utils as utils

from perun.utils.helpers import MinorVersion

__author__ = "Tomas Fiedor"

# Compiled helper regular expressions
parent_regex = re.compile(r"parent ([a-f0-9]{40})")
author_regex = re.compile(r"author ([^<]+) <([^>]+)> (\d+)")
description_regex = re.compile(r".*\n\n([\S\s]+)")


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
    # Read contents of head through the subprocess and git rev-parse HEAD
    proc = subprocess.Popen("git rev-parse HEAD", cwd=git_path, shell=True, stdout=subprocess.PIPE,
                            universal_newlines=True)
    git_head = proc.stdout.readlines()[0].strip()
    proc.wait()

    assert store.is_sha1(git_head)
    return git_head


def _walk_minor_versions(git_path, head):
    """Return the sorted list of minor versions starting from the given head.

    Initializes the worklist with the given head commit and then iteratively retrieve the
    minor version info, pushing the parents for further processing. At last the list
    is sorted and returned.

    Arguments:
        git_path(str): path to the git directory
        head(str): identification of the starting point (head)

    Returns:
        MinorVersion: yields stream of minor versions
    """
    worklist = [head]
    minor_versions = []

    # Recursively iterate through the parents
    while worklist:
        minor_version = worklist.pop()
        minor_version_info = _get_minor_version_info(git_path, minor_version)
        minor_versions.append(minor_version_info)
        for parent in minor_version_info.parents:
            worklist.append(parent)

    # Sort by date
    minor_versions.sort(key=lambda minor: minor.date)
    return minor_versions


def _walk_major_versions():
    """
    Returns:
        MajorVersion: yields stream of major versions
    """
    pass


def _get_minor_version_info(git_path, minor_version):
    """
    Fixme: Work with packs

    Arguments:
        git_path(str): path to the git
        minor_version(str): identification of minor_version

    Returns:
        MinorVersion: namedtuple representing the minor version (date author email checksum desc parents)
    """
    assert store.is_sha1(minor_version)

    # Check the type of the minor_version
    proc = subprocess.Popen("git cat-file -t {}".format(minor_version), cwd=git_path, shell=True,
                            stdout=subprocess.PIPE, universal_newlines=True)
    object_type = proc.stdout.readlines()[0].strip()
    proc.wait()
    if object_type != 'commit':
        perun_log.error("{} does not represent valid commit object".format(minor_version))

    # Get the contents of the commit object
    proc = subprocess.Popen("git cat-file -p {}".format(minor_version), cwd=git_path, shell=True,
                            stdout=subprocess.PIPE, universal_newlines=True)
    commit_object = "".join(proc.stdout.readlines())

    # Transform to MinorVersion named tuple
    commit_parents = parent_regex.findall(commit_object)
    commit_author_info = author_regex.search(commit_object)
    if not commit_author_info:
        perun_log.error("fatal: malform commit {}".format(minor_version))
    author, email, timestamp = commit_author_info.groups()
    date = timestamps.timestamp_to_str(int(timestamp))

    commit_description = description_regex.search(commit_object).groups()[0]
    if not commit_description:
        perun_log.error("fatal: malform commit {}".format(minor_version))

    return MinorVersion(date, author, email, minor_version, commit_description, commit_parents)


def _get_head_major_version(git_path):
    """Returns the head major branch (i.e. checked out branch).

    Runs the git branch and parses the output in order to infer the currently
    checked out branch (either local or detached head).

    Arguments:
        git_path(str): path to the git repository

    Returns:
        str: representation of the major version
    """
    proc = subprocess.Popen("git branch | sed -n '/\* /s///p'", cwd=git_path, shell=True,
                            stdout=subprocess.PIPE, universal_newlines=True)
    major_head = proc.stdout.readlines()[0].strip()
    proc.wait()

    return major_head
