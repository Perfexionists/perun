"""Helper functions for working with VCS"""
from __future__ import annotations

# Standard Imports
from typing import Callable, Any
import inspect

# Third-Party Imports

# Perun Imports
from perun.logic import pcs


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
            arg_list[minor_version_position] = pcs.vcs().get_minor_head()
            args = tuple(arg_list)
        else:
            pcs.vcs().check_minor_version_validity(args[minor_version_position])
        return func(*args, **kwargs)

    return wrapper


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
        self.saved_state, self.last_head = pcs.vcs().save_state()

    def __exit__(self, *_: Any) -> None:
        """When exiting, restores the state of the repository

        Restores the previous commit and unstashes the changes made to working directory and index.

        :param _: not used params of exit handler
        """
        pcs.vcs().restore_state(self.saved_state, self.last_head)
