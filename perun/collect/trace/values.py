"""The values module contains various utility classes, enums and constants that are used in
multiple other modules across the whole trace collector.
"""

import dataclasses
import re
import collections
import shutil
from enum import IntEnum, Enum
from zipfile import ZipFile, ZIP_LZMA

from perun.collect.trace.watchdog import WATCH_DOG
from perun.utils.exceptions import MissingDependencyException


class Strategy(Enum):
    """The supported probe extraction strategies."""

    USERSPACE = "userspace"
    ALL = "all"
    USERSPACE_SAMPLED = "u_sampled"
    ALL_SAMPLED = "a_sampled"
    CUSTOM = "custom"

    @staticmethod
    def supported():
        """Convert the strategy options to a list of strings.

        :return: the strategies represented as strings
        """
        return [strategy.value for strategy in Strategy]

    @staticmethod
    def default():
        """Provide the default extraction strategy as a string value.

        :return: the default strategy name
        """
        return Strategy.CUSTOM.value


class Zipper:
    """Wrapper class for the ZipFile object that can ignore the 'write' command if zipping is
    not enabled by the user. The Zipper can be used as a context manager.

    :ivar __enabled: determines if the files will be actually packed or ignored
    :ivar pack: the ZipFile handler
    :ivar pack_name: the name of the resulting zip archive
    """

    def __init__(self, enabled, pack_name):
        """Constructs the Zipper object

        :param enabled: determines if the archive will be created or not
        :param pack_name: the name of the resulting archive
        """
        self.__enabled = enabled
        self.pack = None
        self.pack_name = pack_name

    def __enter__(self):
        """The context manager entry guard, creates the ZipFile object if zipping is enabled

        :return: the Zipper object
        """
        if self.__enabled:
            self.pack = ZipFile(self.pack_name, "w", compression=ZIP_LZMA).__enter__()
            WATCH_DOG.info(f"Packing the temporary files into an archive '{self.pack_name}'.")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """The context manager exit guard, the ZipFile object is properly terminated

        :param exc_type: the type of the exception
        :param exc_val: the value of the exception
        :param exc_tb: the exception traceback
        """
        if self.pack is not None:
            self.pack.__exit__(exc_type, exc_val, exc_tb)

    def write(self, file, arcname=None):
        """Packs the given file as 'arcname' into the archive - or ignores the operation if the
        Zipper is not enabled.

        :param file: the file path to archive
        :param arcname: the name of the file in the archive
        """
        if self.__enabled and file is not None:
            self.pack.write(file, arcname=arcname)
            WATCH_DOG.debug(f"Temporary file '{file}' packed as '{arcname}'.")


class FileSize(IntEnum):
    """File sizes represented as a constants, used mainly to select appropriate algorithms based
    on the size of a file.
    """

    SHORT = 0
    LONG = 1


class RecordType(IntEnum):
    """Reference numbers of the various types of probes used in the collection script."""

    FUNC_BEGIN = 0
    FUNC_END = 1
    USDT_SINGLE = 2
    USDT_BEGIN = 3
    USDT_END = 4
    THREAD_BEGIN = 5
    THREAD_END = 6
    PROCESS_BEGIN = 7
    PROCESS_END = 8
    CORRUPT = 9


class OutputHandling(Enum):
    """The handling of the output from the profiled command. Possible modes:
    - default: the output is displayed in the terminal as usual
    - capture: the output is being captured into a file as well as displayed in the terminal
      (note that buffering causes a delay in the terminal output
    - suppress: redirects the output to the DEVNULL so nothing is stored or displayed
    """

    DEFAULT = "default"
    CAPTURE = "capture"
    SUPPRESS = "suppress"

    @staticmethod
    def to_list():
        """Convert the handling options to a list of strings.

        :return: the options represented as strings
        """
        return [handling.value for handling in OutputHandling]


def check(dependencies):
    """Checks that all the required dependencies are present on the system.
    Otherwise an exception is raised.
    """
    # Check that all the dependencies are present
    WATCH_DOG.debug(f"Checking that all the dependencies '{dependencies}' are present")
    for dependency in dependencies:
        if not shutil.which(dependency):
            WATCH_DOG.debug(f"Missing dependency command '{dependency}' detected")
            raise MissingDependencyException(dependency)
    WATCH_DOG.debug("Dependencies check successfully completed, no missing dependency")


@dataclasses.dataclass
class TraceRecord:
    __slots__ = ["type", "offset", "name", "timestamp", "thread", "sequence"]

    type: RecordType
    offset: int
    name: str
    timestamp: int
    thread: int
    sequence: int


# The list of required dependencies
GLOBAL_DEPENDENCIES = ["ps", "grep", "awk", "nm"]

STAP_PHASES = 5  # The number of SystemTap startup phases
LOCK_SUFFIX_LEN = 7  # Suffix length of the lock files
MICRO_TO_SECONDS = 1000000.0  # The conversion constant for collected time records
NANO_TO_SECONDS = 1000000000.0  # The conversion constant for collected time records
DEFAULT_SAMPLE = 20  # The default global sampling for 'sample' strategies if not set by user
SUFFIX_DELIMITERS = ("_", "-")  # The set of supported delimiters between probe and its suffix
PS_FORMAT = "pid,ppid,pgid,cmd"  # The format specification for an output from the 'ps' utility

# Various sleep / wait related constants
HARD_TIMEOUT = 20  # Avoid endless loops with hard timeout value that breaks certain loops
LOG_WAIT = 1  # Sleep value used during periodic SystemTap log checking
HEARTBEAT_INTERVAL = 30  # Periodically inform user about progress each INTERVAL seconds (roughly)
CLEANUP_TIMEOUT = 2  # The timeout for the cleanup operations
CLEANUP_REFRESH = 0.2  # The refresh interval for cleaning up the resources

# Multiprocessing Queue constants
RESOURCE_CHUNK = 10000  # Number of resources transported as one element through a queue
RESOURCE_QUEUE_CAPACITY = 10  # Maximum capacity of the resources queue
QUEUE_TIMEOUT = 0.2  # The timeout for blocking operations of a queue

# The regex to match the SystemTap module name out of the log and extract the non-PID dependent part
STAP_MODULE_REGEX = re.compile(r"(stap_[A-Fa-f0-9]+)_\d+\.ko")

# Categorize record types into probe, thread and process sets since all those records have
# different number of values
PROBE_RECORDS = {
    int(RecordType.FUNC_BEGIN),
    int(RecordType.FUNC_END),
    int(RecordType.USDT_SINGLE),
    int(RecordType.USDT_BEGIN),
    int(RecordType.USDT_END),
}
THREAD_RECORDS = {int(RecordType.THREAD_BEGIN), int(RecordType.THREAD_END)}
PROCESS_RECORDS = {int(RecordType.PROCESS_BEGIN), int(RecordType.PROCESS_END)}
SEQUENCED_RECORDS = {
    int(RecordType.FUNC_BEGIN),
    int(RecordType.USDT_SINGLE),
    int(RecordType.USDT_BEGIN),
}
