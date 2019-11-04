""" Wrapper module for SystemTap related operations such as the script compilation, running
the SystemTap collection process and profiled command, correctly terminating the collection
processes and also properly cleaning up and releasing the used resources.
"""

import time
import os
from signal import SIGINT
from subprocess import PIPE, STDOUT, DEVNULL, TimeoutExpired

from perun.collect.trace.locks import LockType, ResourceLock, get_active_locks_for
from perun.collect.trace.watchdog import WD
from perun.collect.trace.threads import HeartbeatThread, NonBlockingTee, TimeoutThread
from perun.collect.trace.values import Res, FileSize, OutputHandling, \
    LOG_WAIT, HARD_TIMEOUT, CLEANUP_TIMEOUT, CLEANUP_REFRESH, HEARTBEAT_INTERVAL, \
    STAP_MODULE_REGEX, PS_FORMAT, STAP_PHASES

import perun.utils as utils
from perun.utils.exceptions import SystemTapStartupException, SystemTapScriptCompilationException


def systemtap_collect(executable, **kwargs):
    """Collects performance data using the SystemTap wrapper, assembled script and the
    executable.

    :param Executable executable: full collection command with arguments and workload
    :param kwargs: additional collector configuration
    """
    # Get the systemtap log, script and output files
    res = kwargs['res']
    log, script, data = res[Res.log()], res[Res.script()], res[Res.data()]

    # Check that the lock for binary is still valid and log resources with corresponding locks
    res[Res.lock_binary()].check_validity()
    WD.log_resources(*_check_used_resources(kwargs['locks_dir']))

    # Open the log file for collection
    with open(log, 'w') as logfile:
        # Assemble the SystemTap command and log it
        stap_cmd = 'sudo stap -v {} -o {}'.format(script, data)
        WD.log_variable('stap_cmd', stap_cmd)
        # Compile the script, extract the module name from the compilation log and lock it
        compile_systemtap_script(stap_cmd, logfile, **kwargs)
        _lock_kernel_module(log, **kwargs)

        # Run the SystemTap collection
        run_systemtap_collection(stap_cmd, executable, logfile, **kwargs)


def cleanup(res, **kwargs):
    """ Cleans up the SystemTap resources that are still being used.

    Specifically, terminates any still running processes - compilation, collection or the profiled
    executable - and any related spawned child processes. Unloads the kernel module if it is
    still loaded and unlocks all the resource locks.

    :param Res res: the resources object
    :param kwargs: additional configuration options
    """
    WD.info('Releasing and cleaning up the SystemTap-related resources')

    # Terminate perun related processes that are still running
    _cleanup_processes(res, kwargs['pid'])
    # Reset the resource records so that another cleanup is not necessary
    for resource_type in [Res.stap_compile(), Res.stap_collect(), Res.profiled_command()]:
        res[resource_type] = None

    # Unload the SystemTap kernel module if still loaded and unlock it
    # The kernel module should already be unloaded since terminating the SystemTap collection
    # process automatically unloads the module
    _cleanup_kernel_module(res)
    res[Res.stap_module()] = None
    res[Res.stapio()] = None


def compile_systemtap_script(command, logfile, res, **kwargs):
    """ Compiles the SystemTap script without actually running it.

    This step allows the trace collector to identify the resulting kernel module, check if
    the module is not already being used and to lock it.

    :param str command: the 'stap' compilation command to run
    :param TextIO logfile: the handle of the opened SystemTap log file
    :param Res res: the resources object
    :param kwargs: additional configuration options
    """
    WD.info('Attempting to compile the SystemTap script into a kernel module. This may take'
            'a while depending on the number of probe points.')
    # Lock the SystemTap process we're about to start
    process_lock = 'process_{}'.format(os.path.basename(kwargs['binary']))
    # No need to check the lock validity more than once since the SystemTap lock is tied
    # to the binary file which was already checked
    ResourceLock(
        LockType.SystemTap, process_lock, kwargs['pid'], kwargs['locks_dir']
    ).lock(res)

    # Run the compilation process
    # Fetch the password so that the preexec_fn doesn't halt
    utils.run_safely_external_command('sudo sleep 0')
    # Run only the first 4 phases of the stap command, before actually running the collection
    with utils.nonblocking_subprocess(
            command + ' -p 4', {'stderr': logfile, 'stdout': PIPE, 'preexec_fn': os.setpgrp},
            _terminate_process, {'proc_name': Res.stap_compile(), 'res': res}
    ) as compilation_process:
        # Store the compilation process PID and wait for the compilation to finish
        res[Res.stap_compile()] = compilation_process
        WD.debug("Compilation process: '{}'".format(compilation_process.pid))
        _wait_for_script_compilation(logfile.name, compilation_process)
        # The SystemTap seems to print the resulting kernel module into stdout
        # However this may not be universal behaviour so a backup method should be available
        res[Res.stap_module()] = compilation_process.communicate()[0].decode('utf-8')
    WD.info('SystemTap script compilation successfully finished.')


def run_systemtap_collection(command, executable, logfile, **kwargs):
    """ Runs the performance data collection step.

    That means starting up the SystemTap collection process and running the profiled command.

    :param str command: the 'stap' collection command
    :param Executable executable: full collection command with arguments and workload
    :param TextIO logfile: the handle of the opened SystemTap log file
    :param kwargs: additional configuration options
    """
    WD.info('Starting up the SystemTap collection process.')
    with utils.nonblocking_subprocess(
            command, {'stderr': logfile, 'preexec_fn': os.setpgrp},
            _terminate_process, {'proc_name': Res.stap_collect(), 'res': kwargs['res']}
    ) as stap:
        kwargs['res'][Res.stap_collect()] = stap
        WD.debug("Collection process: '{}'".format(stap.pid))
        _wait_for_systemtap_startup(logfile.name, stap)
        WD.info('SystemTap collection process is up and running.')
        _fetch_stapio_pid(kwargs['res'])
        run_profiled_command(executable, **kwargs)


def run_profiled_command(executable, timeout, res, **kwargs):
    """ Runs the profiled external command with arguments.

    :param Executable executable: full collection command with arguments and workload
    :param int timeout: the time limit for the collection process
    :param Res res: the resources object
    :param kwargs: additional configuration options
    """

    def _heartbeat_command(data_file):
        """ The profiled command heartbeat function that updates the user on the collection
        progress, which is measured by the size of the output data file.

        :param str data_file: the name of the output data file
        """
        WD.info("Command execution status update, collected raw data size so far: {}"
                .format(utils.format_file_size(os.stat(data_file).st_size)))

    # Set the process pipes according to the selected output handling mode
    # DEVNULL for suppress mode, STDERR -> STDOUT = PIPE for capture
    output_mode = kwargs['output_handling']
    profiled_args = {}
    if output_mode == OutputHandling.Suppress:
        profiled_args = dict(stderr=DEVNULL, stdout=DEVNULL)
    elif output_mode == OutputHandling.Capture:
        profiled_args = dict(stderr=STDOUT, stdout=PIPE, bufsize=1)

    # Start the profiled command
    WD.info("Launching the profiled command '{}'".format(executable.to_escaped_string()))
    with utils.nonblocking_subprocess(
            executable.to_escaped_string(), profiled_args,
            _terminate_process, {'proc_name': Res.profiled_command(), 'res': res}
    ) as profiled:
        # Store the command process
        res[Res.profiled_command()] = profiled
        WD.debug("Profiled command process: '{}'".format(profiled.pid))
        # Start the Heartbeat thread so that the user is periodically updated about the progress
        with HeartbeatThread(HEARTBEAT_INTERVAL, _heartbeat_command, res[Res.data()]):
            if output_mode == OutputHandling.Capture:
                # Start the 'tee' thread if the output is being captured
                NonBlockingTee(profiled.stdout, res[Res.capture()])
            # Wait indefinitely (until the process ends) or for a 'timeout' seconds
            if timeout is None:
                profiled.wait()
            else:
                time.sleep(timeout)
                WD.info('The profiled command has reached a timeout after {}s.'.format(timeout))
                return
    # Wait for the SystemTap to finish writing to the data file
    _wait_for_systemtap_data(res[Res.data()], kwargs['binary'])


def get_last_line_of(file, length):
    """ Fetches the last line of a file. Based on the length of the file, the appropriate
    extraction method is chosen:
     - Short file: simply iterate the lines until the stream ends
     - Long file: open the file in binary mode, seek to the end of the file and backtrack
                  byte by byte until a newline character is found

    :param str file: the file name (path)
    :param FileSize length: the expected length of the file
    :return tuple: (line number, line content)
                   note: the line number is not available for long files
    """
    # In order to use the optimized version for long files, the file has to be opened in binary mode
    if length == FileSize.Long:
        with open(file, 'rb') as file_handle:
            try:
                file_handle.seek(-1, os.SEEK_END)
                # Skip all empty lines at the end
                while file_handle.read(1) in (b'\n', b'\r'):
                    file_handle.seek(-2, os.SEEK_CUR)
                # Go back to the first non-newline character
                file_handle.seek(-1, os.SEEK_CUR)

                # Go backwards by one byte at a time and check if it is a newline
                while file_handle.read(1) != b'\n':
                    # Check if the last read character was actually the first character in a file
                    if file_handle.tell() == 1:
                        file_handle.seek(-1, os.SEEK_CUR)
                        break
                    file_handle.seek(-2, os.SEEK_CUR)
                # Newline character found, read the whole line
                return 0, file_handle.readline().decode()
            except OSError:
                # The file might be empty or somehow broken
                return 0, ''
    # Otherwise use simple line enumeration until we hit the last one
    else:
        with open(file, 'r') as file_handle:
            last = (0, '')
            for line_num, line in enumerate(file_handle):
                last = (line_num + 1, line)
            return last


def _fetch_stapio_pid(res):
    """ Fetches the PID of the running stapio process and stores it into resources since
    it may be needed for unloading the kernel module.

    :param Res res: the resources object
    """
    # In kernel, the module name is appended with the stapio process PID
    # Scan the running processes for the stapio process and filter out the grep itself
    proc = _extract_processes(
        'ps -eo {} | grep "[s]tapio.*{}"'.format(PS_FORMAT, res[Res.data()])
    )
    # Check the results - there should be only one result
    if proc:
        if len(proc) != 1:
            # This shouldn't ever happen
            WD.debug("Multiple stapio processes found: '{}'".format(proc))
        # Store the PID of the first record
        res[Res.stapio()] = proc[0][0]
    else:
        # This also should't ever happen
        WD.debug('No stapio processes found')


def _lock_kernel_module(logfile, res, **kwargs):
    """ Locks the kernel module resource.

    The module name has either been obtained from the output of the SystemTap compilation process
    or it has to be extracted from the SystemTap log file.

    :param str logfile: the SystemTap log file name
    :param kwargs: additional configuration options
    """
    try:
        # The module name might have been extracted from the compilation process output
        match = STAP_MODULE_REGEX.search(res[Res.stap_module()])
    except TypeError:
        # If not, he kernel module should be in the last log line
        line = get_last_line_of(logfile, FileSize.Short)[1]
        match = STAP_MODULE_REGEX.search(line)
    if not match:
        # No kernel module found, warn the user that something is not right
        WD.warn('Unable to extract the name of the compiled SystemTap module from the log. '
                'This may cause corruption of the collected data since it cannot be ensured '
                'that this will be the only active instance of the given kernel module.')
        return
    # The kernel module name has the following format: 'modulename_PID'
    # The first group contains just the PID-independent module name
    kernel_module = match.group(1)
    res[Res.stap_module()] = kernel_module
    WD.debug("Compiled kernel module name: '{}'".format(kernel_module))
    # Lock the kernel module
    ResourceLock(
        LockType.Module, kernel_module, kwargs['pid'], kwargs['locks_dir']
    ).lock(res)


def _wait_for_script_compilation(logfile, stap_process):
    """ Waits for the script compilation process to finish - either successfully or not.

    An exception is raised in case of failed compilation.

    :param str logfile: the name (path) of the SystemTap log file
    :param Subprocess stap_process: the subprocess object representing the compilation process
    """
    # Start a HeartbeatThread that periodically informs the user of the compilation progress
    with HeartbeatThread(HEARTBEAT_INTERVAL, _heartbeat_stap, (logfile, 'Compilation')):
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
                WD.debug("SystemTap build process failed with exit code '{}'".format(status))
                raise SystemTapScriptCompilationException(logfile, status)


def _wait_for_systemtap_startup(logfile, stap_process):
    """ Waits for the SystemTap collection process to startup.

    The SystemTap startup may take some time and it is necessary to wait until the process is ready
    before launching the profiled command so that the command output is being collected.

    :param str logfile: the name (path) of the SystemTap log file
    :param Subprocess stap_process: the subprocess object representing the collection process
    """
    while True:
        # Check the status of the process
        # The process should be running in background - if it terminates it means that it has failed
        status = stap_process.poll()
        if status is None:
            # Check the last line of the SystemTap log file if the process is still running
            line_no, line = get_last_line_of(logfile, FileSize.Short)
            # The log file should contain at least 4 lines from the compilation and another
            # 5 lines from the startup
            if line_no >= ((2 * STAP_PHASES) - 1) and ' 5: ' in line:
                # If the line contains a mention about the 5. phase, consider the process ready
                return
            # Otherwise wait a bit before the next check
            time.sleep(LOG_WAIT)
        else:
            WD.debug("SystemTap collection process failed with exit code '{}'".format(status))
            raise SystemTapStartupException(logfile)


def _wait_for_systemtap_data(datafile, binary):
    """ Waits until the collection process has finished writing the profiling output to the
    data file. This can be checked by observing the last line of the data file where the
    ending marker 'end <binary>' should be present.

    :param str datafile: the name (path) of the data file
    :param str binary: the binary file that is profiled
    """
    # Start the TimeoutThread so that the waiting is not indefinite
    WD.info('The profiled command has terminated, waiting for the process to finish writing '
            'output to the data file.')
    with TimeoutThread(HARD_TIMEOUT) as timeout:
        while not timeout.reached():
            # Periodically scan the last line of the data file
            # The file can be potentially very long, use the optimized method to get the last line
            last_line = get_last_line_of(datafile, FileSize.Long)[1]
            if last_line.startswith('end {}'.format(binary)):
                WD.info('The data file is fully written.')
                return
            time.sleep(LOG_WAIT)
        # Timeout reached
        WD.info('Timeout reached while waiting for the collection process to fully write output '
                'into the output data file.')


def _heartbeat_stap(logfile, phase):
    """ The SystemTap heartbeat function that scans the log file and reports the last record.

    :param str logfile: the SystemTap log file name (path)
    :param str phase: the SystemTap phase (compilation or collection)
    """
    # Report log line count and the last record
    WD.info("{} status update: 'log lines count' ; 'last log line'".format(phase))
    WD.info("'{}' ; '{}'".format(*get_last_line_of(logfile, FileSize.Short)))


def _cleanup_processes(res, pid):
    """ Attempts to terminate all collection-related processes that are still running - consisting
    of script compilation, collection and profiled command child processes. Also scans the system
    for any leftover spawned child processes and informs the user about them.

    Releases the resource locks for SystemTap and Binary.

    :param Res res: the resources object
    :param int pid: the PID of the
    """
    try:
        # Terminate the known spawned processes
        proc_names = [Res.stap_compile(), Res.stap_collect(), Res.profiled_command()]
        for proc_name in proc_names:
            _terminate_process(proc_name, res)

        # Fetch all processes that are still running and their PPID is tied to either the
        # perun process itself or to the known spawned processes
        processes = [res[proc].pid for proc in proc_names if res[proc] is not None] + [pid]
        extractor = 'ps -o {} --ppid {}'.format(PS_FORMAT, ','.join(map(str, processes)))
        extracted_procs = _extract_processes(extractor)
        WD.log_variable('cleanup::extracted_processes', extracted_procs)

        # Inform the user about such processes
        if extracted_procs:
            WD.warn("Found still running spawned processes:")
            for proc_pid, _, _, cmd in extracted_procs:
                WD.warn(" PID {}: '{}'".format(proc_pid, cmd))
    finally:
        # Make sure that whatever happens, the locks are released
        ResourceLock.unlock(res[Res.lock_stap()], res)
        ResourceLock.unlock(res[Res.lock_binary()], res)


def _terminate_process(proc_name, res):
    """ Terminates the given subprocess (identified by the Res name).

    The process has to terminated by a 'sudo kill' operation since it has been probably invoked
    with 'sudo' rights (this may or may not be true for the user-supplied command) and thus
    the subprocess.terminate() would fail due to insufficient permission.

    The subprocess.wait() is then needed to get rid of the resulting zombie process (since the
    perun process holds a reference to the subprocess until wait() or poll() is used).

    :param str proc_name: the name of the process as used in the Res class
    :param Res res: the resources object
    """
    # Check if the process is registered
    proc = res[proc_name]
    if proc is None:
        return

    # Attempt to terminate the process if it's still running
    if proc.poll() is None:
        WD.debug("Attempting to terminate the '{}' subprocess with PID '{}'"
                 .format(proc_name, proc.pid))
        utils.run_safely_external_command('sudo kill -{} {}'.format(SIGINT, proc.pid), False)
        # The wait is needed to get rid of the resulting zombie process
        try:
            proc.wait(timeout=CLEANUP_TIMEOUT)
            WD.debug("Successfully terminated the subprocess")
        except TimeoutExpired:
            # However the process hasn't terminated, report to the user
            WD.warn("Failed to terminate the '{}' subprocess with PID '{}', manual termination "
                    "is advised".format(proc_name, proc.pid))


def _extract_processes(extract_command):
    """ Extracts and sorts the running processes according to the extraction command.

    :param str extract_command: the processes extraction command

    :return list: a list of (PID, PPID, PGID, CMD) records representing the corresponding
                  attributes of the extracted processes
    """
    procs = []
    out = utils.run_safely_external_command(extract_command, False)[0].decode('utf-8')
    for line in out.splitlines():
        process_record = line.split()

        # Skip the optional first header line
        if process_record[0] == 'PID':
            continue

        # Get the (PID, PPID, PGID, CMD) tuples representing the running parent stap processes
        pid, ppid, pgid = int(process_record[0]), int(process_record[1]), int(process_record[2])
        cmd = ' '.join(process_record[3:])

        # Skip self (the extracting process)
        if extract_command in cmd:
            continue
        procs.append((pid, ppid, pgid, cmd))
    return procs


def _cleanup_kernel_module(res):
    """ Unloads the SystemTap kernel module from the system and releases the resource lock.

    :param Res res: the resources object
    """
    try:
        # We might have acquired the module name but the collect process might not have been started
        if res[Res.stap_module()] is None or res[Res.stapio()] is None:
            return

        # Form the module name which consists of the base module name and stapio PID
        module_name = '{}__{}'.format(res[Res.stap_module()], res[Res.stapio()])
        # Attempts to unload the module
        utils.run_safely_external_command('sudo rmmod {}'.format(module_name), False)
        if not _wait_for_resource_release(_loaded_stap_kernel_modules, [module_name]):
            WD.debug("Unloading the kernel module '{}' failed".format(module_name))
    finally:
        # Always unlock the module
        ResourceLock.unlock(res[Res.lock_module()], res)


def _loaded_stap_kernel_modules(module=None):
    """Extracts the names of all the SystemTap kernel modules - or a specific one - that
    are currently loaded.

    :param str module: the name of the specific module to lookup or None for all of them

    :return list: the list of names of loaded systemtap kernel modules
    """
    # Build the extraction command
    module_filter = 'stap_' if module is None else module
    extractor = 'lsmod | grep {} | awk \'{{print $1}}\''.format(module_filter)

    # Run the command and save the found modules
    out, _ = utils.run_safely_external_command(extractor, False)
    # Make sure that we have a list of unique modules
    modules = set()
    for line in out.decode('utf-8').splitlines():
        modules.add(line)
    return list(modules)


def _wait_for_resource_release(check_function, function_args):
    """ Waits for a resource to be released. The state of the resource is tested by the
    check function invoked with the function args.

    :param function check_function: the function for checking the resource
    :param function_args: the arguments for the check function

    :return bool: True if the resource has been released, False otherwise
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
    """ Scans the system for currently running SystemTap processes and loaded kernel modules. Then
    pairs the results with known locks in order to find out which resources are properly locked
    and which aren't, i.e. if there is a possibility of corrupted output data despite using the
    locks.

    :param str locks_dir: the directory of the lock files
    :return tuple: (locked processes, processes without locks),
                   (locked kernel modules, kernel modules without locks)
    """

    def _match(resources, resource_locks, condition):
        """ Match the resources with the active resource locks based on the condition.

        :param list resources: the list of resource names
        :param list resource_locks: the list of lock objects
        :param function condition: the condition that determines if a resource is tied to a lock
        :return tuple: (list of locked resources, list of resources not tied to a lock)
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
    processes = _extract_processes('ps -eo {} | awk \'$4" "$5 == "sudo stap"\''.format(PS_FORMAT))
    modules = _loaded_stap_kernel_modules()

    # Partition the locks into Systemtap and module locks
    stap_locks, mod_locks = utils.partition_list(
        active_locks, lambda lock: lock.type == LockType.SystemTap
    )

    # Match the locks and resources
    # Specifically, systamtap processes are locked using PPID (i.e. the parent perun process)
    locked_proc, lockless_proc = _match(
        processes, stap_locks, lambda proc, lock: lock.pid == proc[1]
    )
    # Module locks are tied to their name
    locked_mod, lockless_mod = _match(
        modules, mod_locks, lambda module, lock: lock.name == module
    )
    return (locked_proc, lockless_proc), (locked_mod, lockless_mod)
