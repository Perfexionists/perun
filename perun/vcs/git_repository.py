"""Git is a wrapper over git repository used within perun control system

Contains concrete implementation of the function needed by perun to extract information and work
with version control systems.
"""

from __future__ import annotations

# Standard Imports
from typing import Optional, Iterator, Any, cast
import os

# Third-Party Imports
from git.exc import NoSuchPathError, InvalidGitRepositoryError, GitCommandError
from git.repo.base import Repo
from gitdb.exc import BadName  # type: ignore
import git

# Perun Imports
from perun.vcs.abstract_repository import AbstractRepository
from perun.utils import log as perun_log, timestamps
from perun.utils.exceptions import VersionControlSystemException
from perun.utils.structs.common_structs import MinorVersion, MajorVersion


class GitRepository(AbstractRepository):
    def __init__(self, vcs_path: str):
        self.vcs_path: str = vcs_path
        self._set_git_repo(vcs_path)

        self.parse_commit_cache: dict[str, MinorVersion] = {}
        self.minor_version_validity_cache: set[str] = set()
        self.minor_version_info_cache: dict[str, MinorVersion] = {}

    def _set_git_repo(self, vcs_path: str) -> None:
        self.valid_repo = GitRepository.contains_git_repo(vcs_path)
        if self.valid_repo:
            self.git_repo: Repo = Repo(vcs_path)

    @staticmethod
    def contains_git_repo(path: str) -> bool:
        """Checks if there is a git repo at the given @p path.

        :param path: path where we want to check if there is a git repo
        :return: true if @p path contains a git repo already
        """
        try:
            return Repo(path).git_dir is not None
        except (InvalidGitRepositoryError, NoSuchPathError):
            return False

    def init(self, vcs_init_params: dict[str, Any]) -> bool:
        """
        :param vcs_init_params: list of additional params for initialization of the vcs
        :return: true if the vcs was successfully initialized at vcs_path
        """
        dir_was_newly_created = not os.path.exists(self.vcs_path)
        try:
            Repo.init(self.vcs_path, **(vcs_init_params or {}))
        except GitCommandError as gce:
            # If by calling the init we created empty directory in vcs_path,
            # we clean up after ourselves
            if (
                os.path.exists(self.vcs_path)
                and dir_was_newly_created
                and not os.listdir(self.vcs_path)
            ):
                os.rmdir(self.vcs_path)
            perun_log.error_msg(f"while initializing git: {gce}")
            return False

        if self.valid_repo:
            perun_log.minor_status(
                f"Reinitialized {perun_log.highlight('existing')} Git repository",
                status=f"{perun_log.path_style(self.vcs_path)}",
            )
        else:
            perun_log.minor_status(
                f"Initialized {perun_log.highlight('empty')} Git repository",
                status=f"{perun_log.path_style(self.vcs_path)}",
            )
        self._set_git_repo(self.vcs_path)
        return True

    def get_minor_head(self) -> str:
        """
        Fixme: This would be better to internally use rev-parse ;)
        """
        # Read contents of head through the subprocess and git rev-parse HEAD
        try:
            git_head = str(self.git_repo.head.commit)
            return str(git_head)
        except ValueError as value_error:
            perun_log.error(f"while fetching head minor version: {value_error}")

    def walk_minor_versions(self, head: str) -> Iterator[MinorVersion]:
        """Return the sorted list of minor versions starting from the given head.

        Initializes the worklist with the given head commit and then iteratively retrieve the
        minor version info, pushing the parents for further processing. At last the list
        is sorted and returned.

        :param head: identification of the starting point (head)
        :return: yields stream of minor versions
        """
        try:
            head_commit = self.git_repo.commit(head)
        except (ValueError, BadName):
            return
        for commit in self.git_repo.iter_commits(head_commit):
            yield self.parse_commit(commit)

    def walk_major_versions(self) -> Iterator[MajorVersion]:
        """
        :return: yields stream of major versions
        :raises VersionControlSystemException: when the master head cannot be massaged
        """
        for branch in self.git_repo.branches:
            yield MajorVersion(branch.name, self.massage_parameter(branch.name))

    def parse_commit(self, commit: git.objects.Commit) -> MinorVersion:
        """
        :param commit: commit object
        :return: minor version (date author email checksum desc parents)
        """
        checksum = str(commit)
        if checksum not in self.parse_commit_cache.keys():
            commit_parents = [str(parent) for parent in commit.parents]

            commit_author_info = commit.author

            author, email = commit_author_info.name, commit_author_info.email
            timestamp = commit.committed_date
            date = timestamps.timestamp_to_str(int(timestamp))

            commit_description = str(commit.message)

            minor_version = MinorVersion(
                date, author, email, checksum, commit_description, commit_parents
            )
            self.parse_commit_cache[checksum] = minor_version
        return self.parse_commit_cache[checksum]

    def get_minor_version_info(self, minor_version: str) -> MinorVersion:
        """
        :param minor_version: identification of minor_version
        :return: minor version (date author email checksum desc parents)
        """
        if minor_version not in self.minor_version_info_cache.keys():
            minor_version_commit = self.git_repo.commit(minor_version)
            minor_version_info = self.parse_commit(minor_version_commit)
            self.minor_version_info_cache[minor_version] = minor_version_info
        return self.minor_version_info_cache[minor_version]

    def minor_versions_diff(self, baseline_minor_version: str, target_minor_version: str) -> str:
        """Create diff of two supplied minor versions.

        :param baseline_minor_version: the specification of the first minor version
            (in form of sha e.g.)
        :param target_minor_version: the specification of the second minor version
        :return: the version diff as presented by git
        """
        baseline_minor_version = baseline_minor_version or "HEAD~1"
        target_minor_version = target_minor_version or "HEAD"
        return self.git_repo.git.diff(baseline_minor_version, target_minor_version)

    def get_head_major_version(self) -> str:
        """Returns the head major branch (i.e. checked out branch).

        Runs the git branch and parses the output in order to infer the currently
        checked out branch (either local or detached head).

        :return: representation of the major version
        """
        if self.git_repo.head.is_detached:
            return str(self.git_repo.head.commit)
        else:
            return str(self.git_repo.active_branch)

    def get_default_major_version(self) -> str:
        """Returns the default major version (branch name) of the git repository.

        The default branch name may be either set in the configuration files or, if absent,
        may be obtained by listing git's logical variables.

        :returns: string representation of the default major version
        """
        config_parser = git.config.GitConfigParser()
        # The get_value function is incorrectly typed, hence we need to cast it
        default_major_v: str = cast(str, config_parser.get_value("init", "defaultBranch", ""))
        if not default_major_v:
            # The defaultBranch option is not configured, we need to check git's logical variables
            logic_vars: str = self.git_repo.git.var("-l")
            for line in logic_vars.splitlines():
                if "GIT_DEFAULT_BRANCH" in line:
                    # The line should be formatted as GIT_DEFAULT_BRANCH=<value>
                    default_major_v = line.split("=", maxsplit=1)[1]
                    break
        # If not configured anywhere, fallback to 'master' according to git source code
        return default_major_v if default_major_v else "master"

    def check_minor_version_validity(self, minor_version: str) -> None:
        """
        :param minor_version: string representing a minor version in the git
        """
        if minor_version not in self.minor_version_validity_cache:
            try:
                self.git_repo.rev_parse(str(minor_version))
                self.minor_version_validity_cache.add(minor_version)
            except (BadName, ValueError) as inner_exception:
                raise VersionControlSystemException(
                    f"minor version '{minor_version}' could not be found: {inner_exception}"
                )

    def massage_parameter(self, parameter: str, parameter_type: Optional[str] = None) -> str:
        """Parameter massaging takes a parameter and unites it to the unified context

        Given a parameter (in the context of git, this is rev), of a given parameter_type (e.g. tree,
        commit, blob, etc.) calls 'git rev-parse parameter^{parameter_type}' to translate the rev to
        be used for others.

        :return: massaged parameter
        :raises  VersionControlSystemException: when there is an error while rev-parsing the parameter
        """
        try:
            parameter += f"^{{{parameter_type}}}" if parameter_type else ""
            return str(self.git_repo.rev_parse(parameter))
        except BadName as bo_exception:
            raise VersionControlSystemException(
                f"parameter '{parameter}' could not be found: {bo_exception}"
            )
        except (IndentationError, ValueError) as ve_exception:
            raise VersionControlSystemException(
                "parameter '{}' could not be parsed: {}".format(
                    parameter.replace("{", "{{").replace("}", "}}"),
                    ve_exception.args[0].replace("{", "{{").replace("}", "}}"),
                )
            )

    def is_dirty(self) -> bool:
        """Returns true, if the repository is dirty,
        i.e. there are some uncommited changes either in index or working dir.

        :return: true if the repo is dirty, i.e. there are some changes
        """
        return self.git_repo.is_dirty()

    def save_state(self) -> tuple[bool, str]:
        """Saves stashed changes and previous head

        This returns either the real detached head commit, or the previous reference.
        This is to ensure that we are kept at the head branch and not at detached head state.

        :returns: (bool, str) the tuple of indication that some changes were stashed and the state of
            previous head.
        """
        saved_stashed_changes = False
        if self.is_dirty():
            self.git_repo.git.stash("save")
            saved_stashed_changes = True

        # If we are in state of detached head, we return the commit, otherwise we return the ref
        if self.git_repo.head.is_detached:
            return saved_stashed_changes, str(self.git_repo.head.commit)
        else:
            return saved_stashed_changes, str(self.git_repo.head.ref)

    def restore_state(self, has_saved_stashed_changes: bool, previous_state: str) -> None:
        """Restores the previous state of the repository by restoring the stashed changes and checking
        out the previous head.

        Warning! This should be used in pair with save state!

        :param has_saved_stashed_changes: if true, then we have stashed some changes
        :param previous_state: previous head of the repo
        """
        self.checkout(previous_state)
        if has_saved_stashed_changes:
            self.git_repo.git.stash("pop")

    def checkout(self, minor_version: str) -> None:
        """

        :param minor_version: newly checkout state
        """
        self.git_repo.git.checkout(minor_version)
