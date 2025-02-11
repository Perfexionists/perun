"""The 'locks' module provides the necessary features for locking some of the resources
used by the trace collector. Namely the resources contained within the LockType enum.

The locks are needed to ensure that certain resources are not re-used by another running
perun process which could introduce output data corruption, e.g. when the same binary file
is used by two instances of trace collector, the output data could get mixed in both of the
output files - the same would happen if one SystemTap kernel module is used by two different
SystemTap instances etc.

The locks are represented by an object which can - upon the locking operation - create a
corresponding lock file in the .perun directory. The locking should not be perceived as it is
typically (semaphores, monitors or other locking primitives) used in a multiprocess /
multithread programs - here we are dealing with potentially multiple unrelated and not
connected perun processes that may be attempting to use the same resource. Thus the files
are used as a mean to communicate with other running trace collectors that certain resources
should not be used.

However, since the locks are stored in a .perun directory, the scope of the locks is limited
to the corresponding perun instance and does not cover the whole system, i.e. two perun
processes originating from different perun instances will not be able to successfully lock
their resources against each other.
"""

from __future__ import annotations

# Standard Imports
from enum import Enum
from typing import Optional
import os

# Third-Party Imports

# Perun Imports
from perun.logic import temp
from perun.collect.trace.values import LOCK_SUFFIX_LEN, PS_FORMAT
from perun.collect.trace.watchdog import WATCH_DOG
from perun.utils.exceptions import (
    ResourceLockedException,
    InvalidTempPathException,
    SuppressedExceptions,
)
from perun.utils.external import commands


class LockType(Enum):
    """Specifies different lock types that are used in the trace collector.

    Each lock has its own unique suffix to prevent lock file overwriting in case
    of e.g. cleverly chosen binary names.
    """

    Binary = ".b_lock"
    Module = ".m_lock"
    SystemTap = ".s_lock"

    @classmethod
    def suffix_to_type(cls, suffix: str) -> Optional["LockType"]:
        """Transforms the given suffix into the corresponding LockType item.

        :param suffix: the suffix to transform
        :return: corresponding LockType or None if the suffix has none
        """
        for resource in cls:
            if resource.value == suffix:
                return resource
        return None


class ResourceLock:
    """A class for locking certain resources (given by the LockType enum) used by the trace
    collector.

    :ivar name: the name of the lock (e.g. the name of the profiled binary file)
    :ivar type: the type of the resource that is being locked
    :ivar pid: the PID of the locking process
    :ivar locks_dir: the path to the .perun directory where lock files are stored
    :ivar file: the full path of the resulting lock file
    """

    __slots__ = ["name", "type", "pid", "locks_dir", "file"]

    def __init__(
        self, resource_type: LockType, resource_name: str, pid: int, locks_dir: str
    ) -> None:
        """Construct lock object

        :param resource_type: the type of the resource to lock
        :param resource_name: the name of the lock (e.g. the name of the profiled binary file)
        :param pid: the PID of the locking process
        :param locks_dir: the path to the .perun directory where lock files are stored
        """
        self.name = resource_name
        self.type = resource_type
        self.pid = pid
        self.locks_dir = locks_dir
        self.file = os.path.join(locks_dir, f"{self.name}:{self.pid}{self.type.value}")

    @classmethod
    def fromfile(cls, lock_file: str) -> Optional["ResourceLock"]:
        """Construct ResourceLock object from a lock file

        :param lock_file: the path of the lock file
        :return: the lock object or None if the file does not represent a lock
        """
        with SuppressedExceptions(ValueError):
            # Get the resource name and pid
            name, rest = os.path.basename(lock_file).rsplit(":", maxsplit=1)
            pid = int(rest[:-LOCK_SUFFIX_LEN])
            # Transform the suffix into a LockResourceType
            resource_type = LockType.suffix_to_type(rest[-LOCK_SUFFIX_LEN:])
            if resource_type:
                return cls(resource_type, name, pid, os.path.dirname(lock_file))
        return None

    def lock(self) -> None:
        """Actually locks the resource represented by the lock object."""
        WATCH_DOG.debug(f"Attempting to lock a resource '{self.name}' with pid '{self.pid}'")

        # Lock the resource first
        temp.touch_temp_dir(self.locks_dir)
        temp.touch_temp_file(self.file, protect=True)
        # Check that no other currently running profiling process has locked the same resource
        # The check should be done again later since data race might have happened
        self.check_validity()

        WATCH_DOG.debug(f"Resource locked: '{self.file}'")

    def unlock(self) -> None:
        """Unlocks the resource represented by the lock object."""
        # Attempt to delete the lock file if it was not deleted before
        self.delete_file()

    def check_validity(self) -> None:
        """Checks the validity of the lock, i.e. if there are no other lock files representing the
        same resource (e.g. the profiled binary). If a collision is encountered, an exception
        is raised.
        """
        WATCH_DOG.debug(
            f"Checking lock validity for a resource '{self.name}' with pid '{self.pid}'"
        )

        # Iterate all the lock files related to the resource + resource type
        for active_lock in get_active_locks_for(self.locks_dir, [self.name], [self.type]):
            # Ignore the self lock file
            if active_lock.pid == self.pid:
                continue

            # Check if the resource is actually locked by a running perun process
            if _is_running_perun_process(active_lock.pid):
                WATCH_DOG.debug(
                    f"Resource '{self.name}' already locked by a process '{active_lock.pid}'"
                )
                raise ResourceLockedException(self.name, active_lock.pid)
            # If not, remove the lock file and report the obsolete lock
            WATCH_DOG.info(
                "Encountered obsolete lock file that should have been deleted during teardown: "
                f"Resource '{self.name}', pid '{active_lock.pid}'. Attempting to remove the lock."
            )
            active_lock.delete_file()

        WATCH_DOG.debug(f"Lock for '{self.name}:{self.pid}' is valid")

    def delete_file(self) -> None:
        """Attempts to remove the lock file from the file system."""
        try:
            if os.path.exists(self.file):
                WATCH_DOG.debug(f"Attempting to remove a lock file '{self.file}'")
                temp.delete_temp_file(self.file, force=True)
                WATCH_DOG.debug(f"Lock file '{self.file}' removed")
        except (InvalidTempPathException, OSError) as exc:
            # Issue a warning only if the file still exists after a deletion attempt
            if temp.exists_temp_file(self.file):
                WATCH_DOG.warn(f"Failed to delete resource lock file '{exc}'")


def get_active_locks_for(
    locks_dir: str,
    names: Optional[list[str]] = None,
    resource_types: Optional[list[LockType]] = None,
    pids: Optional[list[int]] = None,
) -> list[ResourceLock]:
    """Lists the active locks, i.e. the lock files in the locks_dir that match the supplied
    constraints in terms of resource name, type and PIDs. If the constraint is set to None, then
    it is simply ignored.

    :param locks_dir: the directory where to look for the lock files
    :param names: the list of resource names to look for
    :param resource_types: the types of locks to look for
    :param pids: the PIDs to look for

    :return: the list of ResourceLock objects
    """

    def is_matching(
        name: Optional[str], r_type: Optional[LockType], lock_pid: Optional[int]
    ) -> bool:
        """Checks the given parameters and compares them with the filtering constraints.

        :param name: the resource name to check
        :param r_type: the type of resource lock
        :param lock_pid: the pid of the lock

        :return: true if the parameters are conforming to the filtering rules
        """
        return (
            (names is None or name in names)
            and (pids is None or lock_pid in pids)
            and (resource_types is None or r_type in resource_types)
        )

    locks = []
    for lock_file in temp.list_all_temps(locks_dir):
        # Get a ResourceLock object from the lock file
        lock = ResourceLock.fromfile(lock_file)
        if lock is not None and is_matching(lock.name, lock.type, lock.pid):
            # Store the lock object ff it is valid and matching lock
            locks.append(lock)
    return locks


def _is_running_perun_process(pid: int) -> bool:
    """Checks if the given PID represents a currently running perun process,

    :param pid: the PID of the process

    :return: true if the PID belongs to a running perun process, false otherwise
    """
    # Request information about process with the given PID
    WATCH_DOG.debug(f"Checking the details of a process '{pid}'")
    query = f"ps -o {PS_FORMAT} -p {pid}"
    result = (
        commands.run_safely_external_command(query, check_results=False)[0]
        .decode("utf-8")
        .splitlines()
    )
    WATCH_DOG.log_variable(f"process::{pid}", result)
    # If no such process exists then the output contains only header line
    if len(result) < 2:
        return False
    # Otherwise take the CMD record in the second line and test if it is related to perun
    command = result[1].strip().split()[3:]
    return "perun" in command
