""" The values module contains various utility classes, enums and constants that are used in
multiple other modules across the whole trace collector.
"""

import re
import collections
from enum import IntEnum, Enum
from zipfile import ZipFile, ZIP_LZMA

from perun.collect.trace.watchdog import WD


class Res:
    """ The resource class used to store references to all of the resources that need a proper
    termination or teardown when the data collection is over (either successfully or not,
    including tha cases of signal interruption).

    The various static methods provide names of the internal dictionary items so that they can
    be easily modified in the future.

    :ivar dict _res: the internal resource dictionary
    """
    def __init__(self):
        """ Constructs the Res object
        """
        self._res = dict(
            script=None, log=None, data=None, capture=None,
            lock_binary=None, lock_stap=None, lock_module=None,
            stap_compile=None, stap_collect=None, stap_module=None, stapio=None,
            profiled_command=None
        )

    def __getitem__(self, item):
        """ Method for accessing elements using the bracket notation.

        :param str item: the resource name

        :return: the resource object or None if the resource is not initialized
        """
        return self._res[item]

    def __setitem__(self, key, value):
        """ Method for setting a resource value using the bracket notation.

        :param str key: the resource name
        :param value: the resource object to store
        """
        self._res[key] = value

    @staticmethod
    def script():
        """
        :return str: the resource key of the SystemTap script file
        """
        return 'script'

    @staticmethod
    def log():
        """
        :return str: the resource key of the SystemTap log file
        """
        return 'log'

    @staticmethod
    def data():
        """
        :return str: the resource key of the SystemTap data file
        """
        return 'data'

    @staticmethod
    def capture():
        """
        :return str: the resource key of the output capture file
        """
        return 'capture'

    @staticmethod
    def lock_binary():
        """
        :return str: the resource key of the binary lock object
        """
        return 'lock_binary'

    @staticmethod
    def lock_stap():
        """
        :return str: the resource key of the SystemTap lock object
        """
        return 'lock_stap'

    @staticmethod
    def lock_module():
        """
        :return str: the resource key of the kernel module lock object
        """
        return 'lock_module'

    @staticmethod
    def stap_compile():
        """
        :return str: the resource key of the SystemTap compilation subprocess object
        """
        return 'stap_compile'

    @staticmethod
    def stap_collect():
        """
        :return str: the resource key of the SystemTap collection subprocess object
        """
        return 'stap_collect'

    @staticmethod
    def stap_module():
        """
        :return str: the resource key of the kernel module name
        """
        return 'stap_module'

    @staticmethod
    def stapio():
        """
        :return str: the resource key of the stapio process PID
        """
        return 'stapio'

    @staticmethod
    def profiled_command():
        """
        :return str: the resource key of the profiled command subprocess object
        """
        return 'profiled_command'


class Zipper:
    """ Wrapper class for the ZipFile object that can ignore the 'write' command if zipping is
    not enabled by the user. The Zipper can be used as a context manager.

    :ivar bool __enabled: determines if the files will be actually packed or ignored
    :ivar ZipFile pack: the ZipFile handler
    :ivar str pack_name: the name of the resulting zip archive
    """
    def __init__(self, enabled, pack_name):
        """ Constructs the Zipper object

        :param bool enabled: determines if the archive will be created or not
        :param str pack_name: the name of the resulting archive
        """
        self.__enabled = enabled
        self.pack = None
        self.pack_name = pack_name

    def __enter__(self):
        """ The context manager entry guard, creates the ZipFile object if zipping is enabled

        :return Zipper: the Zipper object
        """
        if self.__enabled:
            self.pack = ZipFile(self.pack_name, 'w', compression=ZIP_LZMA).__enter__()
            WD.info("Packing the temporary files into an archive '{}'.".format(self.pack_name))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """ The context manager exit guard, the ZipFile object is properly terminated

        :param type exc_type: the type of the exception
        :param exception exc_val: the value of the exception
        :param traceback exc_tb: the exception traceback
        """
        if self.pack is not None:
            self.pack.__exit__(exc_type, exc_val, exc_tb)

    def write(self, file, arcname=None):
        """ Packs the given file as 'arcname' into the archive - or ignores the operation if the
        Zipper is not enabled.

        :param str file: the file path to archive
        :param str arcname: the name of the file in the archive
        """
        if self.__enabled and file is not None:
            self.pack.write(file, arcname=arcname)
            WD.debug("Temporary file '{}' packed as '{}'.".format(file, arcname))


class FileSize(IntEnum):
    """ File sizes represented as a constants, used mainly to select appropriate algorithms based
    on the size of a file.
    """
    Short = 0
    Long = 1


class RecordType(IntEnum):
    """ Reference numbers of the various types of probes used in the collection script.
    """
    FuncBegin = 0
    FuncEnd = 1
    StaticSingle = 2
    StaticBegin = 3
    StaticEnd = 4
    Corrupt = 9


class OutputHandling(Enum):
    """ The handling of the output from the profiled command. Possible modes:
        - default: the output is displayed in the terminal as usual
        - capture: the output is being captured into a file as well as displayed in the terminal
          (note that buffering causes a delay in the terminal output
        - suppress: redirects the output to the DEVNULL so nothing is stored or displayed
    """
    Default = 'default'
    Capture = 'capture'
    Suppress = 'suppress'

    @staticmethod
    def to_list():
        """ Convert the handling options to a list of strings.

        :return list: the options represented as strings
        """
        return [handling.value for handling in OutputHandling]


# The trace record template
TraceRecord = collections.namedtuple(
    'record', ['type', 'offset', 'name', 'timestamp', 'thread', 'sequence']
)

# The list of required dependencies
DEPENDENCIES = ['ps', 'grep', 'awk', 'nm', 'stap', 'lsmod', 'rmmod']
# The set of supported strategies by the trace collector
STRATEGIES = ['userspace', 'all', 'u_sampled', 'a_sampled', 'custom']

STAP_PHASES = 5  # The number of SystemTap startup phases
LOCK_SUFFIX_LEN = 7  # Suffix length of the lock files
MICRO_TO_SECONDS = 1000000.0  # The conversion constant for collected time records
DEFAULT_SAMPLE = 20  # The default global sampling for 'sample' strategies if not set by user
SUFFIX_DELIMITERS = ('_', '-')  # The set of supported delimiters between probe and its suffix
PS_FORMAT = 'pid,ppid,pgid,cmd'  # The format specification for an output from the 'ps' utility

# Various sleep / wait related constants
HARD_TIMEOUT = 20  # Avoid endless loops with hard timeout value that breaks certain loops
LOG_WAIT = 1  # Sleep value used during periodic SystemTap log checking
HEARTBEAT_INTERVAL = 30  # Periodically inform user about progress each INTERVAL seconds (roughly)
CLEANUP_TIMEOUT = 2  # The timeout for the cleanup operations
CLEANUP_REFRESH = 0.2  # The refresh interval for cleaning up the resources

# The regex to match the SystemTap module name out of the log and extract the non-PID dependent part
STAP_MODULE_REGEX = re.compile(r"(stap_[A-Fa-f0-9]+)_\d+\.ko")
