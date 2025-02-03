"""The SystemTap engine implementation."""

import time
import os
from subprocess import PIPE, STDOUT, DEVNULL, TimeoutExpired

import perun.collect.trace.systemtap.parse_compact as parse_compact
import perun.collect.trace.collect_engine as engine
import perun.collect.trace.systemtap.script_compact as stap_script_compact
from perun.collect.trace.watchdog import WATCH_DOG
from perun.collect.trace.threads import PeriodicThread, NonBlockingTee, TimeoutThread
from perun.collect.trace.values import (
    FileSize,
    OutputHandling,
    check,
    RecordType,
    LOG_WAIT,
    HARD_TIMEOUT,
    CLEANUP_TIMEOUT,
    CLEANUP_REFRESH,
    HEARTBEAT_INTERVAL,
    STAP_MODULE_REGEX,
    PS_FORMAT,
    STAP_PHASES,
)

from perun.utils.common import common_kit
import perun.utils.log as perun_log
import perun.utils.metrics as metrics
from perun.utils.external import commands, processes
from perun.logic.locks import LockType, ResourceLock, get_active_locks_for
from perun.utils.exceptions import (
    SystemTapStartupException,
    SystemTapScriptCompilationException,
    SuppressedExceptions,
)


class SystemTapEngine(engine.CollectEngine):
    """The SystemTap engine class, derived from the base CollectEngine.

    :ivar script: a full path to the systemtap script file
    :ivar log: a full path to the systemtap log file
    :ivar data: a full path to the file containing the raw performance data
    :ivar capture: a full path to the file containing the captured stdout and stderr of the
                       profiled command
    :ivar lock_binary: the binary lock object
    :ivar lock_stap: the SystemTap process lock object
    :ivar lock_module: the SystemTap module lock object
    :ivar stap_compile the script compilation subprocess object
    :ivar stap_collect the SystemTap collection subprocess object
    :ivar stap_module: the name of the compiled SystemTap module
    :ivar stapio: the stapio process PID
    :ivar profiled_command the profiled command subprocess object
    """

    name = "stap"

    def __init__(self, config):
        """Creates the engine object according to the supplied configuration.

        :param config: the configuration object
        """
        super().__init__(config)
        self.script = self._assemble_file_name("script", ".stp")
        self.log = self._assemble_file_name("log", ".txt")
        self.data = self._assemble_file_name("data", ".txt")
        self.capture = self._assemble_file_name("capture", ".txt")

        # SystemTap specific dependencies
        self.__dependencies = ["stap", "lsmod", "rmmod"]

        # Locks
        binary_name = os.path.basename(self.executable.cmd)
        self.lock_binary = ResourceLock(LockType.Binary, binary_name, self.pid, self.locks_dir)
        self.lock_stap = ResourceLock(
            LockType.SystemTap,
            f"process_{binary_name}",
            self.pid,
            self.locks_dir,
        )
        self.lock_module = None

        self.stap_compile = None
        self.stap_collect = None
        self.stap_module = None
        self.stapio = None

        self.profiled_command = None

        # Create the collection files
        super()._create_collect_files([self.script, self.log, self.data, self.capture])
        # Lock the binary immediately
        self.lock_binary.lock()

    def check_dependencies(self):
        """Check that the SystemTap related dependencies are available."""
        check(self.__dependencies)

    def available_usdt(self, **_):
        """Extract USDT probe locations from the supplied binary files and libraries.

        :return: the names of the available USDT locations per binary file
        """
        # Extract the USDT probe locations from the binary
        # note: stap -l returns code '1' if there are no USDT probes
        return {
            target: list(_parse_usdt_name(_extract_usdt_probes(target))) for target in self.targets
        }

    def assemble_collect_program(self, **kwargs):
        """Assemble the SystemTap collection script according to the specified probes.

        :param kwargs: the configuration parameters
        """
        stap_script_compact.assemble_system_tap_script(self.script, **kwargs)

    def collect(self, config, **_):
        """Collects performance data using the SystemTap wrapper, assembled script and the
        executable.

        :param config: the configuration object
        """
        # Check that the lock for binary is still valid and log resources with corresponding locks
        self.lock_binary.check_validity()
        WATCH_DOG.log_resources(*_check_used_resources(self.locks_dir))

        # Open the log file for collection
        with open(self.log, "w") as logfile:
            # Assemble the SystemTap command and log it
            stap_cmd = f"sudo stap -g --suppress-time-limits -s5 -v {self.script} -o {self.data}"
            compile_cmd = stap_cmd
            if config.stap_cache_off:
                compile_cmd += " --poison-cache"
            WATCH_DOG.log_variable("stap_cmd", stap_cmd)
            # Compile the script, extract the module name from the compilation log and lock it
            self._compile_systemtap_script(compile_cmd, logfile)
            self._lock_kernel_module(self.log)

            # Run the SystemTap collection
            self._run_systemtap_collection(stap_cmd, logfile, config)

    def transform(self, **kwargs):
        """Transforms the raw performance data into the perun resources

        :param kwargs: the configuration parameters

        :return: a generator object that produces the resources
        """
        return parse_compact.trace_to_profile(self.data, **kwargs)

    def cleanup(self, config, **_):
        """Cleans up the SystemTap resources that are still being used.

        Specifically, terminates any still running processes - compilation, collection
        or the profiled executable - and any related spawned child processes.
        Unloads the kernel module if it is still loaded and unlocks all the resource locks.

        :param config: the configuration parameters
        """
        WATCH_DOG.info("Releasing and cleaning up the SystemTap-related resources")
        # Terminate perun related processes that are still running
        self._cleanup_processes()

        # Unload the SystemTap kernel module if still loaded and unlock it
        # The kernel module should already be unloaded since terminating the SystemTap collection
        # process automatically unloads the module
        self._cleanup_kernel_module()

        # Zip and delete (both optional) the temporary collect files
        self._finalize_collect_files(
            ["script", "log", "data", "capture"], config.keep_temps, config.zip_temps
        )

    def _compile_systemtap_script(self, command, logfile):
        """Compiles the SystemTap script without actually running it.

        This step allows the trace collector to identify the resulting kernel module, check if
        the module is not already being used and to lock it.

        :param command: the 'stap' compilation command to run
        :param logfile: the handle of the opened SystemTap log file
        """
        WATCH_DOG.info(
            "Attempting to compile the SystemTap script into a kernel module. "
            "This may take a while depending on the number of probe points."
        )
        # Lock the SystemTap process we're about to start
        # No need to check the lock validity more than once since the SystemTap lock is tied
        # to the binary file which was already checked
        self.lock_stap.lock()

        # Run the compilation process
        # Fetch the password so that the preexec_fn doesn't halt
        commands.run_safely_external_command("sudo sleep 0")
        # Run only the first 4 phases of the stap command, before actually running the collection
        with processes.nonblocking_subprocess(
            command + " -p 4",
            {"stderr": logfile, "stdout": PIPE, "preexec_fn": os.setpgrp},
            self._terminate_process,
            {"proc_name": "stap_compile"},
        ) as compilation_process:
            # Store the compilation process object and wait for the compilation to finish
            self.stap_compile = compilation_process
            WATCH_DOG.debug(f"Compilation process: '{compilation_process.pid}'")
            _wait_for_script_compilation(logfile.name, compilation_process)
            # The SystemTap seems to print the resulting kernel module into stdout
            # However this may not be universal behaviour so a backup method should be available
            self.stap_module = compilation_process.communicate()[0].decode("utf-8")
        WATCH_DOG.info("SystemTap script compilation successfully finished.")

    def _lock_kernel_module(self, logfile):
        """Locks the kernel module resource.

        The module name has either been obtained from the output of the SystemTap compilation
        process or it has to be extracted from the SystemTap log file.

        :param logfile: the SystemTap log file name
        """
        try:
            # The module name might have been extracted from the compilation process output
            match = STAP_MODULE_REGEX.search(self.stap_module)
        except TypeError:
            # If not, he kernel module should be in the last log line
            line = _get_last_line_of(logfile, FileSize.SHORT)[1]
            match = STAP_MODULE_REGEX.search(line)
        if not match:
            # No kernel module found, warn the user that something is not right
            WATCH_DOG.warn(
                "Unable to extract the name of the compiled SystemTap module from the log. "
                "This may cause corruption of the collected data since it cannot be ensured "
                "that this will be the only active instance of the given kernel module."
            )
            return
        # The kernel module name has the following format: 'modulename_PID'
        # The first group contains just the PID-independent module name
        self.stap_module = match.group(1)
        WATCH_DOG.debug(f"Compiled kernel module name: '{self.stap_module}'")
        # Lock the kernel module
        self.lock_module = ResourceLock(LockType.Module, self.stap_module, self.pid, self.locks_dir)
        self.lock_module.lock()

    def _run_systemtap_collection(self, command, logfile, config):
        """Runs the performance data collection step.

        That means starting up the SystemTap collection process and running the profiled command.

        :param command: the 'stap' collection command
        :param logfile: the handle of the opened SystemTap log file
        :param config: the configuration object
        """
        WATCH_DOG.info("Starting up the SystemTap collection process.")
        with processes.nonblocking_subprocess(
            command,
            {"stderr": logfile, "preexec_fn": os.setpgrp},
            self._terminate_process,
            {"proc_name": "stap_collect"},
        ) as collect_process:
            self.stap_collect = collect_process
            WATCH_DOG.debug(f"Collection process: '{collect_process.pid}'")
            _wait_for_systemtap_startup(logfile.name, collect_process)
            WATCH_DOG.info("SystemTap collection process is up and running.")
            self._fetch_stapio_pid()
            self._run_profiled_command(config)

    def _fetch_stapio_pid(self):
        """Fetches the PID of the running stapio process and stores it into resources since
        it may be needed for unloading the kernel module.
        """
        # In kernel, the module name is appended with the stapio process PID
        # Scan the running processes for the stapio process and filter out the grep itself
        proc = _extract_processes(f'ps -eo {PS_FORMAT} | grep "[s]tapio.*{self.data}"')
        # Check the results - there should be only one result
        if proc:
            if len(proc) != 1:
                # This shouldn't ever happen
                WATCH_DOG.debug(f"Multiple stapio processes found: '{proc}'")
            # Store the PID of the first record
            self.stapio = proc[0][0]
        else:
            # This also should't ever happen
            WATCH_DOG.debug("No stapio processes found")

    def _run_profiled_command(self, config):
        """Runs the profiled external command with arguments.
        :param config: the configuration object
        """

        def _heartbeat_command(data_file):
            """The profiled command heartbeat function that updates the user on the collection
            progress, which is measured by the size of the output data file.

            :param data_file: the name of the output data file
            """
            data_size = perun_log.format_file_size(os.stat(data_file).st_size)
            WATCH_DOG.info(
                f"Command execution status update, collected raw data size so far: {data_size}"
            )

        # Set the process pipes according to the selected output handling mode
        # DEVNULL for suppress mode, STDERR -> STDOUT = PIPE for capture
        profiled_args = {}
        if config.output_handling == OutputHandling.SUPPRESS:
            profiled_args = dict(stderr=DEVNULL, stdout=DEVNULL)
        elif config.output_handling == OutputHandling.CAPTURE:
            profiled_args = dict(stderr=STDOUT, stdout=PIPE, bufsize=1)

        # Start the profiled command
        WATCH_DOG.info(f"Launching the profiled command '{self.executable.to_escaped_string()}'")

        with processes.nonblocking_subprocess(
            self.executable.to_escaped_string(),
            profiled_args,
            self._terminate_process,
            {"proc_name": "profiled_command"},
        ) as profiled:
            metrics.start_timer("command_time")
            # Store the command process
            self.profiled_command = profiled
            WATCH_DOG.debug(f"Profiled command process: '{profiled.pid}'")
            # Start the periodic thread so that the user is periodically updated about the progress
            with PeriodicThread(HEARTBEAT_INTERVAL, _heartbeat_command, [self.data]):
                if config.output_handling == OutputHandling.CAPTURE:
                    # Start the 'tee' thread if the output is being captured
                    NonBlockingTee(profiled.stdout, self.capture)
                # Wait indefinitely (until the process ends) or for a 'timeout' seconds
                try:
                    profiled.wait(timeout=config.timeout)
                except TimeoutExpired:
                    WATCH_DOG.info(
                        f"The profiled command has reached a timeout after {config.timeout}s."
                    )

        metrics.end_timer("command_time")
        # Wait for the SystemTap to finish writing to the data file
        _wait_for_systemtap_data(self.data)

    def _cleanup_processes(self):
        """Attempts to terminate all collection-related processes that are still running -
        consisting of script compilation, collection and profiled command child processes.
        Also scans the system for any leftover spawned child processes and informs the user
        about them.

        Releases the resource locks for SystemTap and Binary.
        """
        procs = [self.stap_compile, self.stap_collect, self.profiled_command]
        proc_names = ["stap_compile", "stap_collect", "profiled_command"]
        try:
            # Terminate the known spawned processes
            for proc_name in proc_names:
                self._terminate_process(proc_name)

            # Fetch all processes that are still running and their PPID is tied to either the
            # perun process itself or to the known spawned processes
            pids = [proc.pid for proc in procs if proc is not None] + [self.pid]
            extractor = f"ps -o {PS_FORMAT} --ppid {','.join(map(str, pids))}"
            extracted_procs = _extract_processes(extractor)
            WATCH_DOG.log_variable("cleanup::extracted_processes", extracted_procs)

            # Inform the user about such processes
            if extracted_procs:
                WATCH_DOG.warn("Found still running spawned processes:")
                for proc_pid, _, _, cmd in extracted_procs:
                    WATCH_DOG.warn(f" PID {proc_pid}: '{cmd}'")
        finally:
            # Make sure that whatever happens, the locks are released
            # The locks shouldn't be None since they were created in __init__
            self.lock_stap.unlock()
            self.lock_binary.unlock()
            # Reset the resource records so that another cleanup is not necessary
            for proc_name in proc_names:
                setattr(self, proc_name, None)

    def _cleanup_kernel_module(self):
        """Unloads the SystemTap kernel module from the system and releases the resource lock."""
        try:
            # We might have acquired the module name but the collect process might not have started
            if self.stap_module is None or self.stapio is None:
                return

            # Form the module name which consists of the base module name and stapio PID
            module_name = f"{self.stap_module}__{self.stapio}"
            # Attempts to unload the module
            commands.run_safely_external_command(f"sudo rmmod {module_name}", check_results=False)
            if not _wait_for_resource_release(_loaded_stap_kernel_modules, [module_name]):
                WATCH_DOG.debug(f"Unloading the kernel module '{module_name}' failed")
        finally:
            # Always unlock the module
            if self.lock_module is not None:
                self.lock_module.unlock()
            # Reset the resources
            self.stap_module = None
            self.stapio = None


def _extract_usdt_probes(binary):
    """Load USDT probes from the binary file using the SystemTap.

    :param binary: path to the binary file

    :return: the decoded standard output
    """
    out, _ = commands.run_safely_external_command(
        f'sudo stap -l \'process("{binary}").mark("*")\'', check_results=False
    )
    return out.decode("utf-8")


def _parse_usdt_name(usdt_list):
    """Cut the USDT probe location name from the extract output.

    :param usdt_list: the extraction output

    :return: generator object that provides the usdt probe locations
    """
    for probe in usdt_list.splitlines():
        # The location is present between the '.mark("' and '")' substrings
        location = probe.rfind('.mark("')
        if location != -1:
            yield probe[location + len('.mark("') : -2]


def _get_last_line_of(file, length):
    """Fetches the last line of a file. Based on the length of the file, the appropriate
    extraction method is chosen:
     - Short file: simply iterate the lines until the stream ends
     - Long file: open the file in binary mode, seek to the end of the file and backtrack
                  byte by byte until a newline character is found

    :param file: the file name (path)
    :param length: the expected length of the file
    :return: (line number, line content)
                   note: the line number is not available for long files
    """
    # In order to use the optimized version for long files, the file has to be opened in binary mode
    if length == FileSize.LONG:
        with open(file, "rb") as file_handle:
            try:
                file_handle.seek(-1, os.SEEK_END)
                # Skip all empty lines at the end
                while file_handle.read(1) in (b"\n", b"\r"):
                    file_handle.seek(-2, os.SEEK_CUR)
                # Go back to the first non-newline character
                file_handle.seek(-1, os.SEEK_CUR)

                # Go backwards by one byte at a time and check if it is a newline
                while file_handle.read(1) != b"\n":
                    # Check if the last read character was actually the first character in a file
                    if file_handle.tell() == 1:
                        file_handle.seek(-1, os.SEEK_CUR)
                        break
                    file_handle.seek(-2, os.SEEK_CUR)
                # Newline character found, read the whole line
                return 0, file_handle.readline().decode()
            except OSError:
                # The file might be empty or somehow broken
                return 0, ""
    # Otherwise use simple line enumeration until we hit the last one
    else:
        with open(file, "r") as file_handle:
            last = (0, "")
            for line_num, line in enumerate(file_handle):
                last = (line_num + 1, line)
            return last


def _wait_for_script_compilation(logfile, stap_process):
    """Waits for the script compilation process to finish - either successfully or not.

    An exception is raised in case of failed compilation.

    :param logfile: the name (path) of the SystemTap log file
    :param stap_process: the subprocess object representing the compilation process
    """
    # Start a HeartbeatThread that periodically informs the user of the compilation progress
    with PeriodicThread(HEARTBEAT_INTERVAL, _heartbeat_stap, [logfile, "Compilation"]):
        while True:
            # Check the status of the process
            status = stap_process.poll()
            if status is None:
                # The compilation process has not finished yet, take a small break
                time.sleep(LOG_WAIT)
            elif status == 0:
                # The process has successfully finished
                return
            else:
                # The stap process terminated with non-zero code which means failure
                WATCH_DOG.debug(f"SystemTap build process failed with exit code '{status}'")
                raise SystemTapScriptCompilationException(logfile, status)


def _wait_for_systemtap_startup(logfile, stap_process):
    """Waits for the SystemTap collection process to startup.

    The SystemTap startup may take some time and it is necessary to wait until the process is ready
    before launching the profiled command so that the command output is being collected.

    :param logfile: the name (path) of the SystemTap log file
    :param stap_process: the subprocess object representing the collection process
    """
    while True:
        # Check the status of the process
        # The process should be running in background - if it terminates it means that it has failed
        status = stap_process.poll()
        if status is None:
            # Check the last line of the SystemTap log file if the process is still running
            line_no, line = _get_last_line_of(logfile, FileSize.SHORT)
            # The log file should contain at least 4 lines from the compilation and another
            # 5 lines from the startup
            if line_no >= ((2 * STAP_PHASES) - 1) and " 5: " in line:
                # If the line contains a mention about the 5. phase, consider the process ready
                return
            # Otherwise wait a bit before the next check
            time.sleep(LOG_WAIT)
        else:
            WATCH_DOG.debug(f"SystemTap collection process failed with exit code '{status}'")
            raise SystemTapStartupException(logfile)


def _wait_for_systemtap_data(datafile):
    """Waits until the collection process has finished writing the profiling output to the
    data file. This can be checked by observing the last line of the data file where the
    ending sentinel should be present.

    :param datafile: the name (path) of the data file
    """
    # Start the TimeoutThread so that the waiting is not indefinite
    WATCH_DOG.info(
        "The profiled command has terminated, waiting for the process to finish writing output "
        "to the data file."
    )
    with TimeoutThread(HARD_TIMEOUT) as timeout:
        while not timeout.reached():
            with SuppressedExceptions(IndexError, ValueError):
                # Periodically scan the last line of the data file
                # The file can be potentially long, use the optimized method to get the last line
                last_line = _get_last_line_of(datafile, FileSize.LONG)[1]
                if int(last_line.split()[0]) == RecordType.PROCESS_END.value:
                    WATCH_DOG.info("The data file is fully written.")
                    return
            time.sleep(LOG_WAIT)
        # Timeout reached
        WATCH_DOG.info(
            "Timeout reached while waiting for the collection process to fully write output "
            "into the output data file."
        )


def _heartbeat_stap(logfile, phase):
    """The SystemTap heartbeat function that scans the log file and reports the last record.

    :param logfile: the SystemTap log file name (path)
    :param phase: the SystemTap phase (compilation or collection)
    """
    # Report log line count and the last record
    WATCH_DOG.info(f"{phase} status update: 'log lines count' ; 'last log line'")
    lineno, line = _get_last_line_of(logfile, FileSize.SHORT)
    WATCH_DOG.info(f"'{lineno}' ; '{line}'")


def _extract_processes(extract_command):
    """Extracts and sorts the running processes according to the extraction command.

    :param extract_command: the processes extraction command

    :return: a list of (PID, PPID, PGID, CMD) records representing the corresponding
                  attributes of the extracted processes
    """
    procs = []
    out = commands.run_safely_external_command(extract_command, check_results=False)[0].decode(
        "utf-8"
    )
    for line in out.splitlines():
        process_record = line.split()

        # Skip the optional first header line
        if process_record[0] == "PID":
            continue

        # Get the (PID, PPID, PGID, CMD) tuples representing the running parent stap processes
        pid, ppid, pgid = (
            int(process_record[0]),
            int(process_record[1]),
            int(process_record[2]),
        )
        cmd = " ".join(process_record[3:])

        # Skip self (the extracting process)
        if extract_command in cmd:
            continue
        procs.append((pid, ppid, pgid, cmd))
    return procs


def _loaded_stap_kernel_modules(module=None):
    """Extracts the names of all the SystemTap kernel modules - or a specific one - that
    are currently loaded.

    :param module: the name of the specific module to lookup or None for all of them

    :return: the list of names of loaded systemtap kernel modules
    """
    # Build the extraction command
    module_filter = "stap_" if module is None else module
    extractor = f"lsmod | grep {module_filter} | awk '{{print $1}}'"

    # Run the command and save the found modules
    out, _ = commands.run_safely_external_command(extractor, check_results=False)
    # Make sure that we have a list of unique modules
    modules = set()
    for line in out.decode("utf-8").splitlines():
        modules.add(line)
    return list(modules)


def _wait_for_resource_release(check_function, function_args):
    """Waits for a resource to be released. The state of the resource is tested by the
    check function invoked with the function args.

    :param check_function: the function for checking the resource
    :param function_args: the arguments for the check function

    :return: True if the resource has been released, False otherwise
    """
    # Check the state of the resource once before starting the timeout thread
    time.sleep(CLEANUP_REFRESH)
    if not check_function(*function_args):
        return True
    # The resource is still active, periodically check the state
    with TimeoutThread(CLEANUP_TIMEOUT) as timeout:
        while not timeout.reached():
            if not check_function(*function_args):
                return True
            time.sleep(CLEANUP_REFRESH)
    # Despite all the waiting, the resource is still active
    return False


def _check_used_resources(locks_dir):
    """Scans the system for currently running SystemTap processes and loaded kernel modules. Then
    pairs the results with known locks in order to find out which resources are properly locked
    and which aren't, i.e. if there is a possibility of corrupted output data despite using the
    locks.

    :param locks_dir: the directory of the lock files
    :return: (locked processes, processes without locks),
                   (locked kernel modules, kernel modules without locks)
    """

    def _match(resources, resource_locks, condition):
        """Match the resources with the active resource locks based on the condition.

        :param resources: the list of resource names
        :param resource_locks: the list of lock objects
        :param condition: the condition that determines if a resource is tied to a lock
        :return: (list of locked resources, list of resources not tied to a lock)
        """
        locked, lockless = [], []
        for resource in resources:
            # Find all the locks that are matching the resource
            matching_locks = [lock for lock in resource_locks if condition(resource, lock)]
            record = (resource, matching_locks)
            # Save the resource as locked or lockless
            if matching_locks:
                locked.append(record)
            else:
                lockless.append(record)
        return locked, lockless

    # First list relevant lock files and then resources (in case some resource is closed in-between)
    # since locks without corresponding resource are not a big issue unlike the other way around.
    active_locks = get_active_locks_for(
        locks_dir, resource_types=[LockType.Module, LockType.SystemTap]
    )
    processes = _extract_processes(f'ps -eo {PS_FORMAT} | awk \'$4" "$5 == "sudo stap"\'')
    modules = _loaded_stap_kernel_modules()

    # Partition the locks into Systemtap and module locks
    stap_locks, mod_locks = common_kit.partition_list(
        active_locks, lambda lock: lock.type == LockType.SystemTap
    )

    # Match the locks and resources
    # Specifically, systamtap processes are locked using PPID (i.e. the parent perun process)
    locked_proc, lockless_proc = _match(
        processes, stap_locks, lambda proc, lock: lock.pid == proc[1]
    )
    # Module locks are tied to their name
    locked_mod, lockless_mod = _match(modules, mod_locks, lambda module, lock: lock.name == module)
    return (locked_proc, lockless_proc), (locked_mod, lockless_mod)
