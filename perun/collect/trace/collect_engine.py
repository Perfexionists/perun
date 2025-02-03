"""The collection itself is done by a so-called 'engine'. Each engine must implement the same
mandatory methods so that it can be used in a generic way. This is ensured by the abstract class
CollectEngine which is used as a base class for all future engines.
"""

import os
from abc import ABC, abstractmethod
from signal import SIGINT
from subprocess import TimeoutExpired

import perun.logic.temp as temp
from perun.utils.external import commands
from perun.logic.pcs import get_log_directory
from perun.collect.trace.values import CLEANUP_TIMEOUT, Zipper
from perun.collect.trace.watchdog import WATCH_DOG


# TODO: rethink the interface signatures to conform to LSP
class CollectEngine(ABC):
    """The base abstract class for all the collection engines. Stores some of the configuration
    parameters for easier access.

    :ivar binary: the path to the binary file to be probed
    :ivar libs: list of additional dynamic libraries to profile
    :ivar targets: list of binary and libraries to profile
    :ivar executable: the Executable object containing the profiled command, args, etc.
    :ivar timestamp: the time of the collection start
    :ivar pid: the PID of the Tracer process
    :ivar files_dir: the directory path of the temporary files
    :ivar locks_dir: the directory path of the lock files
    """

    # Set the supported engines
    _supported = ["stap", "ebpf"]

    def __init__(self, config):
        """Initializes the default engine parameters.

        :param config: the configuration object
        """
        super().__init__()
        self.binary = config.binary
        self.libs = config.libs
        self.targets = [self.binary] + self.libs
        self.executable = config.executable
        self.timestamp = config.timestamp
        self.pid = config.pid
        self.files_dir = config.files_dir
        self.locks_dir = config.locks_dir

    @abstractmethod
    def check_dependencies(self):
        """Check that the specific dependencies for a given engine are satisfied."""

    @abstractmethod
    def available_usdt(self, **kwargs):
        """List the available USDT probes within the given binary files and libraries using
        an engine-specific approach.

        :param kwargs: the required parameters

        :return: a list of the USDT probe names per binary file
        """

    @abstractmethod
    def assemble_collect_program(self, **kwargs):
        """Assemble the collection program that specifies the probes and the handlers, if needed.

        :param kwargs: the required parameters
        """

    @abstractmethod
    def collect(self, **kwargs):
        """Collect the raw performance data using the assembled collection program and other
        parameters.

        :param kwargs: the required parameters
        """

    @abstractmethod
    def transform(self, **kwargs):
        """Transform the raw performance data into a resources as used in the profiles.

        :param kwargs: the required parameters

        :return: a generator object that produces the resources
        """

    @abstractmethod
    def cleanup(self, **kwargs):
        """Cleans up all the engine-related resources such as files, processes, locks, etc.

        :param kwargs: the required parameters
        """

    @staticmethod
    def available():
        """Lists all the available and supported engines.

        :return: the names of the supported engines.
        """
        return CollectEngine._supported

    @staticmethod
    def default():
        """Provide the default collection engine.

        :return: the name of the default engine
        """
        return CollectEngine._supported[0]

    def _assemble_file_name(self, name, suffix):
        """Builds a full path to a temporary file name using the tmp/ directory within perun.

        :param name: the name of the temporary file
        :param suffix: the suffix of the file

        :return: the full path to the temporary file
        """
        return os.path.join(
            self.files_dir,
            f"collect_{name}_{self.timestamp}_{self.pid}{suffix}",
        )

    @staticmethod
    def _create_collect_files(paths):
        """Creates the requested temporary files.

        :param paths: the list of file paths to create
        """
        for path in paths:
            temp.touch_temp_file(path, protect=True)
            WATCH_DOG.debug(f"Temporary file '{path}' successfully created")

    def _finalize_collect_files(self, files, keep_temps, zip_temps):
        """Zip and delete the temporary collect files.

        :param files: the name of the object attribute that contains the file path
        :param keep_temps: specifies if the temporary files should be kept or deleted
        :param zip_temps: specifies if the temporary files should be zipped or not
        """
        pack_name = os.path.join(
            get_log_directory(),
            "trace",
            f"collect_files_{self.timestamp}_{self.pid}.zip.lzma",
        )
        with Zipper(zip_temps, pack_name) as temp_pack:
            for file_name in files:
                file = getattr(self, file_name)
                if file is not None:
                    # If zipping is disabled in the configuration, the pack.write does nothing
                    temp_pack.write(file, os.path.basename(file))
                    if not keep_temps:
                        temp.delete_temp_file(file, force=True)
                        WATCH_DOG.debug(f"Temporary file '{file}' deleted")
                    setattr(self, file_name, None)
            WATCH_DOG.end_session(temp_pack)

    def _terminate_process(self, proc_name):
        """Terminates the given subprocess (identified by the proc_name).

        The process has to terminated by a 'sudo kill' operation since it has been probably invoked
        with 'sudo' rights (this may or may not be true for the user-supplied command) and thus
        the subprocess.terminate() would fail due to insufficient permission.

        The subprocess.wait() is then needed to get rid of the resulting zombie process (since the
        perun process holds a reference to the subprocess until wait() or poll() is used).

        :param proc_name: the name of the process as used in the engine class
        """
        # Check if the process is registered
        proc = getattr(self, proc_name)
        if proc is None:
            return

        # Attempt to terminate the process if it's still running
        if proc.poll() is None:
            WATCH_DOG.debug(
                f"Attempting to terminate the '{proc_name}' subprocess with PID '{proc.pid}'"
            )
            commands.run_safely_external_command(
                f"sudo kill -{SIGINT} {proc.pid}", check_results=False
            )
            # The wait is needed to get rid of the resulting zombie process
            try:
                proc.wait(timeout=CLEANUP_TIMEOUT)
                WATCH_DOG.debug("Successfully terminated the subprocess")
            except TimeoutExpired:
                # However the process hasn't terminated, report to the user
                WATCH_DOG.warn(
                    f"Failed to terminate the '{proc_name}' subprocess with PID '{proc.pid}', "
                    "manual termination is advised"
                )
