"""Wrapper over version control systems used for generic lookup of the concrete implementations.

VCS module contains modules with concrete implementations of the wrappers over the concrete version
control systems. It tries to enforce simplicity and lightweight approach in an implementation of
the wrapper.

Inside the wrapper are defined function that are used for lookup of the concrete implementations
depending on the chosen type/module, like e.g. git, svn, etc.
"""
from __future__ import annotations

# Standard Imports
from typing import Callable, Any, Iterator, TYPE_CHECKING, Optional
import inspect

# Third-Party Imports

# Perun Imports
from perun.logic import pcs
from perun.utils import decorators, log as perun_log
from perun.utils.common import common_kit

if TYPE_CHECKING:
    from perun.utils.structs import MinorVersion, MajorVersion


def lookup_minor_version(func: Callable[..., Any]) -> Callable[..., Any]:
    """If the minor_version is not given by the caller, it looks up the HEAD in the repo.

    If the @p func is called with minor_version parameter set to None,
    then this decorator performs a lookup of the minor_version corresponding
    to the head of the repository.

    :param function func: decorated function for which we will look up the minor_version
    :returns function: decorated function, with minor_version translated or obtained
    """
    f_args, _, _, _, *_ = inspect.getfullargspec(func)
    minor_version_position = f_args.index("minor_version")

    def wrapper(*args: Any, **kwargs: Any) -> Callable[..., Any]:
        """Inner wrapper of the function"""
        # if the minor_version is None, then we obtain the minor head for the wrapped type
        if minor_version_position < len(args) and args[minor_version_position] is None:
            # note: since tuples are immutable we have to do this workaround
            arg_list = list(args)
            arg_list[minor_version_position] = get_minor_head()
            args = tuple(arg_list)
        else:
            check_minor_version_validity(args[minor_version_position])
        return func(*args, **kwargs)

    return wrapper


def get_minor_head() -> str:
    """Returns the string representation of head of current major version, i.e.
    for git this returns the massaged HEAD reference.

    This function is called mainly during the outputs of ``perun log`` and
    ``perun status`` but also during the automatic generation of profiles
    (either by ``perun run`` or ``perun collect``), where the retrieved
    identification is used as :preg:`origin`.

    :returns: unique string representation of current head (usually in SHA)
    :raises ValueError: if the head cannot be retrieved from the current
        context
    """
    try:
        vcs_type, vcs_url = pcs.get_vcs_type_and_url()
        return common_kit.dynamic_module_function_call(
            "perun.vcs", vcs_type, "_get_minor_head", vcs_url
        )
    except ValueError as value_error:
        perun_log.error(f"while fetching head minor version: {value_error}")
        return ""


def init(vcs_init_params: dict[str, Any]) -> bool:
    """Calls the implementation of initialization of wrapped underlying version
    control system.

    The initialization should take care of both reinitialization of existing
    version control system instances and newly created instances. Init is
    called during the ``perun init`` command from command line interface.

    :param dict vcs_init_params: dictionary of keyword arguments passed to
        initialization method of the underlying vcs module
    :return: true if the underlying vcs was successfully initialized
    """
    vcs_type, vcs_path = pcs.get_vcs_type_and_url()
    perun_log.msg_to_stdout(
        f"Initializing {vcs_type} version control params {vcs_path} and {vcs_init_params}",
        1,
    )
    return common_kit.dynamic_module_function_call(
        "perun.vcs", vcs_type, "_init", vcs_path, vcs_init_params
    )


def walk_minor_versions(head_minor_version: str) -> Iterator[MinorVersion]:
    """Generator of minor versions for the given major version, which yields
    the ``MinorVersion`` named tuples containing the following information:
    ``date``, ``author``, ``email``, ``checksum`` (i.e. the hash representation
    of the minor version), ``commit_description`` and ``commit_parents`` (i.e.
    other minor versions).

    Minor versions are walked through this function during the ``perun log``
    command.

    :param str head_minor_version: the root minor versions which is the root
        of the walk.
    :returns: iterable stream of minor version representation
    """
    vcs_type, vcs_path = pcs.get_vcs_type_and_url()
    perun_log.msg_to_stdout(f"Walking minor versions of type {vcs_type}", 1)
    return common_kit.dynamic_module_function_call(
        "perun.vcs", vcs_type, "_walk_minor_versions", vcs_path, head_minor_version
    )


def walk_major_versions() -> Iterator[MajorVersion]:
    """Generator of major versions for the current wrapped repository.

    This function is currently unused, but will be needed in the future.

    :returns: iterable stream of major version representation
    """
    vcs_type, vcs_path = pcs.get_vcs_type_and_url()
    perun_log.msg_to_stdout(f"Walking major versions of type {vcs_type}", 1)
    return common_kit.dynamic_module_function_call(
        "perun.vcs", vcs_type, "_walk_major_versions", vcs_path
    )


@decorators.singleton_with_args
def get_minor_version_info(minor_version: str) -> MinorVersion:
    """Yields the specification of concrete minor version in form of
    the ``MinorVersion`` named tuples containing the following information:
    ``date``, ``author``, ``email``, ``checksum`` (i.e. the hash representation
    of the minor version), ``commit_description`` and ``commit_parents`` (i.e.
    other minor versions).

    This function is a non-generator alternative of
    :func:`perun.vcs.walk_minor_versions` and is used during the ``perun
    status`` output to display the specifics of minor version.

    :param str minor_version: the specification of minor version (in form of
        sha e.g.) for which we are retrieving the details
    :returns: minor version named tuple
    """
    vcs_type, vcs_path = pcs.get_vcs_type_and_url()
    perun_log.msg_to_stdout(
        f"Getting minor version info of type {vcs_type} and args {vcs_path}, {minor_version}",
        1,
    )
    return common_kit.dynamic_module_function_call(
        "perun.vcs", vcs_type, "_get_minor_version_info", vcs_path, minor_version
    )


def minor_versions_diff(baseline_minor_version: str, target_minor_version: str) -> str:
    """Returns the git diff of two specified minor versions.

    :param str baseline_minor_version: the specification of the first minor version (in form of sha e.g.)
    :param str target_minor_version: the specification of the second minor version
    """
    vcs_type, vcs_path = pcs.get_vcs_type_and_url()
    perun_log.msg_to_stdout(
        f"Showing minor version diff of type {vcs_type} and args {vcs_path}, "
        f"{baseline_minor_version}:{target_minor_version}",
        1,
    )
    return common_kit.dynamic_module_function_call(
        "perun.vcs",
        vcs_type,
        "_minor_versions_diff",
        vcs_path,
        baseline_minor_version,
        target_minor_version,
    )


def get_head_major_version() -> str:
    """Returns the string representation of current major version of the
    wrapped repository.

    Major version is displayed during the ``perun status`` output, which shows
    the current working major version of the project.

    :returns: string representation of the major version
    """
    vcs_type, vcs_path = pcs.get_vcs_type_and_url()
    perun_log.msg_to_stdout(f"Getting head major version of type {vcs_type}", 1)
    return common_kit.dynamic_module_function_call(
        "perun.vcs", vcs_type, "_get_head_major_version", vcs_path
    )


@decorators.singleton_with_args
def check_minor_version_validity(minor_version: str) -> None:
    """Checks whether the given minor version specification corresponds to the
    wrapped version control system, and is not in wrong format.

    Minor version validity is mostly checked during the lookup of the minor
    versions from the command line interface.

    :param str minor_version: the specification of minor version (in form of
        sha e.g.) for which we are checking the validity
    :raises VersionControlSystemException: when the given minor version is
        invalid in the context of the wrapped version control system.
    """
    vcs_type, vcs_path = pcs.get_vcs_type_and_url()
    common_kit.dynamic_module_function_call(
        "perun.vcs", vcs_type, "_check_minor_version_validity", vcs_path, minor_version
    )


def massage_parameter(parameter: str, parameter_type: Optional[str] = None) -> str:
    """Conversion function for massaging (or unifying different representations
    of objects) the parameters for version control systems.

    Massaging is mainly executed during from the command line interface, when
    one can e.g. use the references (like ``HEAD``) to specify concrete minor
    versions. Massing then unifies e.g. the references or proper hash
    representations, to just one representation for internal processing.

    :param str parameter: vcs parameter (e.g. revision, minor or major version)
        which will be massaged, i.e. transformed to unified representation
    :param str parameter_type: more detailed type of the parameter
    :returns: string representation of parameter
    """
    vcs_type, vcs_path = pcs.get_vcs_type_and_url()
    return common_kit.dynamic_module_function_call(
        "perun.vcs", vcs_type, "_massage_parameter", vcs_path, parameter, parameter_type
    )


def is_dirty() -> bool:
    """Tests whether the wrapped repository is dirty.

    By dirty repository we mean a repository that has either a submitted changes to its index (i.e.
    we are in the middle of commit) or any unsubmitted changes to tracked files in the current
    working directory.

    Note that this is crucial for performance testing, as any uncommited changes may skew
    the profiled data and hence the resulting profiles would not correctly represent the performance
    of minor versions.

    :return: whether the given repository is dirty or not
    """
    vcs_type, vcs_path = pcs.get_vcs_type_and_url()
    return common_kit.dynamic_module_function_call("perun.vcs", vcs_type, "_is_dirty", vcs_path)


class CleanState:
    """Helper with wrapper, which is used to execute instances of commands with clean state of VCS.

    This is needed e.g. when we are collecting new data, and the repository is dirty with changes,
    then we use this CleanState to keep those changes, have a clean state (or maybe even checkout
    different version) and then collect correctly the data. The previous state is then restored
    """

    __slots__ = ["saved_state", "last_head"]

    def __init__(self) -> None:
        """Creates a with wrapper for a corresponding VCS"""
        self.saved_state: bool = False
        self.last_head: str = ""

    def __enter__(self) -> None:
        """When entering saves the state of the repository

        We save the uncommited/unsaved changes (e.g. to stash) and also we remember the previous
        head, which will be restored at the end.
        """
        self.saved_state, self.last_head = save_state()

    def __exit__(self, *_: Any) -> None:
        """When exiting, restores the state of the repository

        Restores the previous commit and unstashes the changes made to working directory and index.

        :param _: not used params of exit handler
        """
        restore_state(self.saved_state, self.last_head)


def save_state() -> tuple[bool, str]:
    """Saves the state of the repository in case it is dirty.

    When saving the state of the repository one should store the uncommited changes to
    the working directory and index. Any issues while this process happens should be handled by
    user itself, hence no workarounds and mending should take place in this function.

    :returns: (bool, str) the tuple of indication that some changes were stashed and the state of
        previous head.
    """
    # Todo: Check the vcs.fail_when_dirty and log error in the case
    vcs_type, vcs_path = pcs.get_vcs_type_and_url()
    return common_kit.dynamic_module_function_call("perun.vcs", vcs_type, "_save_state", vcs_path)


def restore_state(saved: bool, state: str) -> None:
    """Restores the previous state of the repository

    When restoring the state of the repository one should pop the stored changes from the stash
    and reapply them on the current directory. This make sure, that after the performance testing,
    the project is in the previous state and developer can continue with his work.

    :param bool saved: whether the stashed was something
    :param str state: the previous state of the repository
    """
    vcs_type, vcs_path = pcs.get_vcs_type_and_url()
    common_kit.dynamic_module_function_call(
        "perun.vcs", vcs_type, "_restore_state", vcs_path, saved, state
    )


def checkout(minor_version: str) -> None:
    """Checks out the new working directory corresponding to the given minor version.

    According to the supplied minor version, this command should remake the working directory,
    so it corresponds to the state defined by the minor version.

    :param str minor_version: minor version that will be checked out
    """
    vcs_type, vcs_path = pcs.get_vcs_type_and_url()
    massaged_minor_version = massage_parameter(minor_version)
    common_kit.dynamic_module_function_call(
        "perun.vcs", vcs_type, "_checkout", vcs_path, massaged_minor_version
    )
