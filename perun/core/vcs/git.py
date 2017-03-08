"""Git is an wrapper over git repository used within perun control system

Contains concrete implementation of the function needed by perun to extract informations and work
with version control systems.
"""

import git

import perun.core.logic.store as store
import perun.utils.timestamps as timestamps
import perun.utils.log as perun_log

from perun.utils.helpers import MinorVersion

__author__ = "Tomas Fiedor"


def create_repo_from_path(func):
    """Transforms the first argument---the git path---to git repo object

    Arguments:
        func(function): wrapped function for which we will do the lookup
    """
    def wrapper(repo_path, *args, **kwargs):
        """Wrapper function for the decorator"""
        return func(git.Repo(repo_path), *args, **kwargs)
    return wrapper


def _init(vcs_path, vcs_init_params):
    """
    Arguments:
        vcs_path(path): path where the vcs will be initialized
        vcs_init_params(dict): list of additional params for initialization of the vcs

    Returns:
        bool: true if the vcs was successfully initialized at vcs_path
    """
    if not git.Repo.init(vcs_path, **(vcs_init_params or {})):
        perun_log.warn("Error while initializing git directory")
        return False

    perun_log.quiet_info("Initialized empty Git repository in {}".format(vcs_path))
    return True


@create_repo_from_path
def _get_minor_head(git_repo):
    """
    Fixme: This would be better to internally use rev-parse ;)
    Arguments:
        git_repo(git.Repo): repository object of the wrapped git by perun
    """
    # Read contents of head through the subprocess and git rev-parse HEAD
    try:
        git_head = str(git_repo.head.commit)
        assert store.is_sha1(git_head)
        return git_head
    except ValueError:
        return ""


@create_repo_from_path
def _walk_minor_versions(git_repo, head):
    """Return the sorted list of minor versions starting from the given head.

    Initializes the worklist with the given head commit and then iteratively retrieve the
    minor version info, pushing the parents for further processing. At last the list
    is sorted and returned.

    Arguments:
        git_repo(git.Repo): repository object for the wrapped git vcs
        head(str): identification of the starting point (head)

    Returns:
        MinorVersion: yields stream of minor versions
    """
    head_commit = git_repo.commit(head)
    for commit in git_repo.iter_commits(head_commit):
        yield _parse_commit(commit)


@create_repo_from_path
def _walk_major_versions(git_repo):
    """
    Arguments:
        git_repo(git.Repo): wrapped git repository object
    Returns:
        MajorVersion: yields stream of major versions
    """
    for branch in git_repo.branches():
        yield str(branch)


def _parse_commit(commit):
    """
    Arguments:
        commit(git.Commit): commit object

    Returns:
        MinorVersion: namedtuple representing the minor version (date author email checksum desc parents)
    """
    checksum = str(commit)
    commit_parents = [str(parent) for parent in commit.parents]

    commit_author_info = commit.author
    if not commit_author_info:
        perun_log.error("fatal: malform commit {}".format(checksum))

    author, email = commit_author_info.name, commit_author_info.email
    timestamp = commit.committed_date
    date = timestamps.timestamp_to_str(int(timestamp))

    commit_description = str(commit.message)
    if not commit_description:
        perun_log.error("fatal: malform commit {}".format(checksum))

    return MinorVersion(date, author, email, checksum, commit_description, commit_parents)


@create_repo_from_path
def _get_minor_version_info(git_repo, minor_version):
    """
    Arguments:
        git_repo(git.Repo): wrapped repository of the perun
        minor_version(str): identification of minor_version

    Returns:
        MinorVersion: namedtuple representing the minor version (date author email checksum desc parents)
    """
    assert store.is_sha1(minor_version)

    minor_version_commit = git_repo.commit(minor_version)
    if not minor_version_commit:
        perun_log.error("{} does not represent valid commit object".format(minor_version))
    return _parse_commit(minor_version_commit)


@create_repo_from_path
def _get_head_major_version(git_repo):
    """Returns the head major branch (i.e. checked out branch).

    Runs the git branch and parses the output in order to infer the currently
    checked out branch (either local or detached head).

    Arguments:
        git_repo(git.Repo): wrapped repository object

    Returns:
        str: representation of the major version
    """
    return str(git_repo.active_branch)
