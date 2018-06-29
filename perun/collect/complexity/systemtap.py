"""Module wrapping SystemTap related operations such as:
    - SystemTap script assembling
    - starting the SystemTap with generated script
    - killing the SystemTap process
    - collected data transformation to profile format
    - etc.

This module serves basically as SystemTap controller.
"""

import shutil
import shlex
import os
from subprocess import TimeoutExpired, CalledProcessError
from enum import IntEnum

import perun.utils as utils


# Collection statuses
class Status(IntEnum):
    OK = 0
    STAP = 1
    STAP_DEP = 2
    EXCEPT = 3


def systemtap_collect(script, cmd, args, **kwargs):
    # Create the output and log file for collection
    script_path, script_dir, _ = utils.get_path_dir_file(script)
    output = script_dir + 'collect_record_{0}.txt'.format(kwargs['timestamp'])
    log = script_dir + 'collect_log_{0}.txt'.format(kwargs['timestamp'])

    with open(log, 'w') as logfile:
        # Start the SystemTap process
        print('Starting the SystemTap process... ', end='')
        stap_runner, code = start_systemtap_in_background(script, output, logfile, **kwargs)
        if code != Status.OK:
            return code, None
        print('Done')

        # Run the command that is supposed to be profiled
        print('SystemTap up and running, execute the profiling target... ', end='')
        try:
            run_profiled_command(cmd, args)
        except CalledProcessError:
            # Critical error during profiled command, make sure we terminate the collector
            kill_systemtap_in_background(stap_runner)
            raise
        print('Done')

        # Terminate SystemTap process
        print('Data collection complete, terminating the SystemTap process... ', end='')
        kill_systemtap_in_background(stap_runner)
        print('Done')
        return Status.Ok, output


def start_systemtap_in_background(stap_script, output, log, **_):
    # Resolve the systemtap path
    stap = shutil.which('stap')
    if not stap:
        return Status.STAP_DEP

    # Basically no-op, but requesting root password so os.setpgrp does not halt due to missing password
    utils.run_safely_external_command('sudo sleep 0')
    # The setpgrp is needed for killing the root process which spawns child processes
    process = utils.start_nonblocking_process(
        'sudo stap -v {0} -o {1}'.format(shlex.quote(stap_script), shlex.quote(output)),
        universal_newlines=True, stderr=log, preexec_fn=os.setpgrp
    )
    # Wait until systemtap process is ready or error occurs
    return process, _wait_for_systemtap_startup(log.name, process)


def kill_systemtap_in_background(stap_process):
    utils.run_safely_external_command('sudo kill {0}'.format(os.getpgid(stap_process.pid)))


def run_profiled_command(cmd, args):
    if args != '':
        full_command = '{0} {1}'.format(shlex.quote(cmd), args)
    else:
        full_command = shlex.quote(cmd)
    utils.run_safely_external_command(full_command, False)


def _wait_for_systemtap_startup(logfile, stap_process):
    with open(logfile, 'r') as scanlog:
        while True:
            try:
                # Take a break before the next status check
                stap_process.wait(timeout=1)
                # The process actually terminated which means that error occurred
                return Status.STAP
            except TimeoutExpired:
                # Check process status and reload the log file
                scanlog.seek(0)
                # Read the last line of logfile and return if the systemtap is ready
                last = ''
                for line in scanlog:
                    last = line
                if last == 'Pass 5: starting run.\n':
                    return Status.OK
