"""Git is a wrapper over git repository used within perun control system

Contains concrete implementation of the function needed by perun to extract information and work
with version control systems.
"""
from __future__ import annotations

import os
import git
from git.repo.base import Repo

from git.exc import NoSuchPathError, InvalidGitRepositoryError, GitCommandError
from gitdb.exc import BadName
from typing import Optional, Iterator

import perun.utils.log as perun_log
import perun.utils.timestamps as timestamps
import perun.utils.decorators as decorators
from perun.utils.exceptions import VersionControlSystemException
from perun.utils.structs import MinorVersion, MajorVersion


from typing import Callable, Any


def contains_git_repo(path: str) -> bool:
    """Checks if there is a git repo at the given @p path.

    :param str path: path where we want to check if there is a git repo
    :returns bool: true if @p path contains a git repo already
    """
    try:
        return Repo(path).git_dir is not None
    except (InvalidGitRepositoryError, NoSuchPathError):
        return False


def create_repo_from_path(func: Callable[..., Any]) -> Callable[..., Any]:
    """Transforms the first argument---the git path---to git repo object

    :param function func: wrapped function for which we will do the lookup
    """

    def wrapper(repo_path: str | Repo, *args: Any, **kwargs: Any) -> Any:
        """Wrapper function for the decorator"""
        if isinstance(repo_path, Repo):
            return func(repo_path, *args, **kwargs)
        else:
            return func(Repo(repo_path), *args, **kwargs)

    return wrapper


def _init(vcs_path: str, vcs_init_params: dict[str, Any]) -> bool:
    """
    :param path vcs_path: path where the vcs will be initialized
    :param dict vcs_init_params: list of additional params for initialization of the vcs
    :returns bool: true if the vcs was successfully initialized at vcs_path
    """
    dir_was_newly_created = not os.path.exists(vcs_path)
    path_contains_git_repo = contains_git_repo(vcs_path)
    try:
        Repo.init(vcs_path, **(vcs_init_params or {}))
    except GitCommandError as gce:
        # If by calling the init we created empty directory in vcs_path, we clean up after ourselves
        if os.path.exists(vcs_path) and dir_was_newly_created and not os.listdir(vcs_path):
            os.rmdir(vcs_path)
        perun_log.error(f"while git init: {gce}")

    if path_contains_git_repo:
        perun_log.quiet_info(f"Reinitialized existing Git repository in {vcs_path}")
    else:
        perun_log.quiet_info(f"Initialized empty Git repository in {vcs_path}")
    return True


@create_repo_from_path
def _get_minor_head(git_repo: Repo) -> str:
    """
    Fixme: This would be better to internally use rev-parse ;)

    :param Repo git_repo: repository object of the wrapped git by perun
    """
    # Read contents of head through the subprocess and git rev-parse HEAD
    git_head = str(git_repo.head.commit)
    return str(git_head)


@create_repo_from_path
def _walk_minor_versions(git_repo: Repo, head: str) -> Iterator[MinorVersion]:
    """Return the sorted list of minor versions starting from the given head.

    Initializes the worklist with the given head commit and then iteratively retrieve the
    minor version info, pushing the parents for further processing. At last the list
    is sorted and returned.

    :param Repo git_repo: repository object for the wrapped git vcs
    :param str head: identification of the starting point (head)
    :returns MinorVersion: yields stream of minor versions
    """
    try:
        head_commit = git_repo.commit(head)
    except (ValueError, BadName):
        return
    for commit in git_repo.iter_commits(head_commit):
        yield _parse_commit(commit)


@create_repo_from_path
def _walk_major_versions(git_repo: Repo) -> Iterator[MajorVersion]:
    """
    :param Repo git_repo: wrapped git repository object
    :returns MajorVersion: yields stream of major versions
    :raises VersionControlSystemException: when the master head cannot be massaged
    """
    for branch in git_repo.branches:  # type: ignore
        yield MajorVersion(branch.name, _massage_parameter(git_repo, branch.name))


@decorators.static_variables(commit_cache=dict())
def _parse_commit(commit: git.objects.Commit) -> MinorVersion:
    """
    :param git.Commit commit: commit object
    :returns MinorVersion: namedtuple of minor version (date author email checksum desc parents)
    """
    checksum = str(commit)
    if checksum not in _parse_commit.commit_cache.keys():
        commit_parents = [str(parent) for parent in commit.parents]

        commit_author_info = commit.author

        author, email = commit_author_info.name, commit_author_info.email
        timestamp = commit.committed_date
        date = timestamps.timestamp_to_str(int(timestamp))

        commit_description = str(commit.message)

        minor_version = MinorVersion(
            date, author, email, checksum, commit_description, commit_parents
        )
        _parse_commit.commit_cache[checksum] = minor_version
    return _parse_commit.commit_cache[checksum]


@create_repo_from_path
def _get_minor_version_info(git_repo: Repo, minor_version: str) -> MinorVersion:
    """
    :param Repo git_repo: wrapped repository of the perun
    :param str minor_version: identification of minor_version
    :returns MinorVersion: namedtuple of minor version (date author email checksum desc parents)
    """
    minor_version_commit = git_repo.commit(minor_version)
    return _parse_commit(minor_version_commit)


@create_repo_from_path
def _minor_versions_diff(
    git_repo: Repo, baseline_minor_version: str, target_minor_version: str
) -> str:
    """Create diff of two supplied minor versions.

    :param Repo git_repo: wrapped repository of the perun
    :param str baseline_minor_version: the specification of the first minor version
        (in form of sha e.g.)
    :param str target_minor_version: the specification of the second minor version
    :return str: the version diff as presented by git
    """
    baseline_minor_version = baseline_minor_version or "HEAD~1"
    target_minor_version = target_minor_version or "HEAD"
    return git_repo.git.diff(baseline_minor_version, target_minor_version)


@create_repo_from_path
def _get_head_major_version(git_repo: Repo) -> str:
    """Returns the head major branch (i.e. checked out branch).

    Runs the git branch and parses the output in order to infer the currently
    checked out branch (either local or detached head).

    :param Repo git_repo: wrapped repository object
    :returns str: representation of the major version
    """
    if git_repo.head.is_detached:
        return str(git_repo.head.commit)
    else:
        return str(git_repo.active_branch)


@create_repo_from_path
def _check_minor_version_validity(git_repo: Repo, minor_version: str) -> None:
    """
    :param Repo git_repo: wrapped repository object
    :param str minor_version: string representing a minor version in the git
    """
    try:
        git_repo.rev_parse(str(minor_version))
    except (BadName, ValueError) as inner_exception:
        raise VersionControlSystemException(
            "minor version '{}' could not be found: {}",
            minor_version,
            str(inner_exception),
        )


@create_repo_from_path
def _massage_parameter(git_repo: Repo, parameter: str, parameter_type: Optional[str] = None) -> str:
    """Parameter massaging takes a parameter and unites it to the unified context

    Given a parameter (in the context of git, this is rev), of a given parameter_type (e.g. tree,
    commit, blob, etc.) calls 'git rev-parse parameter^{parameter_type}' to translate the rev to
    be used for others.

    :param Repo git_repo: wrapped git repository
    :returns str: massaged parameter
    :raises  VersionControlSystemException: when there is an error while rev-parsing the parameter
    """
    try:
        parameter += "^{{{0}}}".format(parameter_type) if parameter_type else ""
        return str(git_repo.rev_parse(parameter))
    except BadName as bo_exception:
        raise VersionControlSystemException(
            "parameter '{}' could not be found: {}".format(parameter, str(bo_exception))
        )
    except (IndentationError, ValueError) as ve_exception:
        raise VersionControlSystemException(
            "parameter '{}' could not be parsed: {}".format(
                parameter.replace("{", "{{").replace("}", "}}"),
                ve_exception.args[0].replace("{", "{{").replace("}", "}}"),
            )
        )


@create_repo_from_path
def _is_dirty(git_repo: Repo) -> bool:
    """Returns true, if the repository is dirty, i.e. there are some uncommited changes either in
    index or working dir.

    :param Repo git_repo: wrapped git repository
    :return: true if the repo is dirty, i.e. there are some changes
    """
    return git_repo.is_dirty()


@create_repo_from_path
def _save_state(git_repo: Repo) -> tuple[bool, str]:
    """Saves stashed changes and previous head

    This returns either the real detached head commit, or the previous reference. This is to ensure
    that we are kept at the head branch and not at detached head state.

    :param Repo git_repo: git repository
    :returns: (bool, str) the tuple of indication that some changes were stashed and the state of
        previous head.
    """
    saved_stashed_changes = False
    if _is_dirty(git_repo):
        git_repo.git.stash("save")
        saved_stashed_changes = True

    # If we are in state of detached head, we return the commit, otherwise we return the ref
    if git_repo.head.is_detached:
        return saved_stashed_changes, str(git_repo.head.commit)
    else:
        return saved_stashed_changes, str(git_repo.head.ref)


@create_repo_from_path
def _restore_state(git_repo: Repo, has_saved_stashed_changes: bool, previous_state: str) -> None:
    """Restores the previous state of the repository by restoring the stashed changes and checking
    out the previous head.

    Warning! This should be used in pair with save state!

    :param Repo git_repo: git repository
    :param bool has_saved_stashed_changes: if true, then we have stashed some changes
    :param str previous_state: previous head of the repo
    """
    _checkout(git_repo, previous_state)
    if has_saved_stashed_changes:
        git_repo.git.stash("pop")


@create_repo_from_path
def _checkout(git_repo: Repo, minor_version: str) -> None:
    """

    :param Repo git_repo: git repository
    :param str minor_version: newly checkout state
    """
    git_repo.git.checkout(minor_version)
