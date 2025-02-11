"""The watchdog module provides logging features for the trace collector.

The watchdog redirects messages to a console as well as to a log file depending on the selected
type of message (warn, info, debug). The debug messages will be stored only in the log file whereas
both info and warn messages will also be displayed to the user on the console.

If the watchdog is not enabled, then certain messages can still be shown to the user using the
perun logging module.
"""

import logging
import os
import pprint

import perun.logic.pcs as pcs
from perun.utils.common import common_kit
import perun.utils.log as perun_log


class Watchdog:
    """Logger class for the trace collector. Allows to log various events, warnings, milestones,
    variables etc. Useful especially for diagnostic purposes.

    :ivar __enabled: enables or disables the watchdog logging (not the console outputs tho)
    :ivar __logger: the internal handle to the Logger object
    :ivar logfile: path to (name of) the logging file
    :ivar pid: the PID of the process that is using the watchdog
    :ivar timestamp: the startup timestamp of the process using the watchdog
    :ivar quiet: suppress the info console outputs
    :ivar debug_format: the format of the debug messages
    :ivar __debug_format_len: the approximate length of the resulting format
    :ivar info_format: the format of the info messages
    """

    def __init__(self):
        """Constructor"""
        self.__enabled = False
        self.__logger = None
        self.logfile = None
        self.pid = None
        self.timestamp = None
        self.quiet = None
        self.debug_format = "%(process)d--%(asctime)s--%(message)s"
        self.__debug_format_len = 32
        self.info_format = "%(asctime)s--%(message)s"

    def start_session(self, enabled, pid, timestamp, quiet):
        """Initializes new watchdog session, i.e. creates the logger object and configures it.

        :param enabled: determines if the watchdog should be logging to a log file
        :param pid: the PID of the process that is using the watchdog
        :param timestamp: the startup timestamp of the process using the watchdog
        :param quiet: suppress the info console outputs
        """
        # Do nothing (except the 'quiet' value) if the watchdog should be disabled
        self.__enabled = enabled
        self.quiet = quiet
        if not self.__enabled:
            return

        # Store some configuration values
        self.pid = pid
        self.timestamp = timestamp
        self.logfile = os.path.join(
            pcs.get_log_directory(), "trace", f"trace_{timestamp}_{pid}.txt"
        )

        # Get the logger object and disable propagation to the root logger
        self.__logger = logging.getLogger(f"trace_wd.{timestamp}.{pid}")
        self.__logger.propagate = False

        # Prepare the directory for trace logs if it does not exist yet
        common_kit.touch_dir(os.path.split(self.logfile)[0])
        # Create the file handler, log all the DEBUG messages for detailed diagnostic
        file_handler = logging.FileHandler(self.logfile)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(self.debug_format))
        # Create the console handler for outputting detailed progress steps
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter(self.info_format))
        # Register the handlers
        self.__logger.addHandler(file_handler)
        self.__logger.addHandler(console_handler)

        # Log the initial message
        self.info(f"Watchdog successfully started for trace PID '{pid}'.")

    def end_session(self, zipper=None):
        """End the current watchdog session and optionally zip the log file.

        :param zipper: the zipper object
        """
        # Terminate the session only if it's running
        if self.__enabled:
            self.info(f"Watchdog successfully terminated for trace PID '{self.pid}'.")
            self.__enabled = False
        # Optionally pack the file and remove it from the file system
        if zipper.pack is not None:
            zipper.write(self.logfile, os.path.basename(self.logfile))
            os.remove(self.logfile)

    def header(self, msg):
        """Prints the message in a 'header' style that should visually separate blocks of log
        records. This is achieved by adding an underline consisting of '=' under the message.

        The message is printed out to the log file as well as to the terminal.

        :param msg: the header message
        """
        if self.__enabled:
            # Create a debug message
            self.__logger.debug(msg + "\n" + ("=" * (len(msg) + self.__debug_format_len)))
        # Use the colored output for console
        perun_log.cprintln(msg + "\n" + ("=" * len(msg)), "white")

    def warn(self, msg, always=True):
        """Prints the message as a warning. The warning is displayed to the user even if the
        watchdog is not enabled - as long as the always parameter is set to True.

        :param msg: the warning message
        :param always: show the warning regardless of enabled / disabled watchdog
        """
        if not self.__enabled:
            if always:
                perun_log.warn(msg)
        else:
            self.__logger.warning(msg)

    def info(self, msg, always=True):
        """Prints the info message. The message is displayed on the terminal as well as stored in
        the log file. If the 'quiet' flag is set, the message will not be displayed on the terminal.

        :param msg: the info message
        :param always: show the message on terminal even if watchdog is disabled, however,
                            the quiet flag can override this parameter
        :return:
        """
        if not self.__enabled:
            if always and not self.quiet:
                perun_log.write(msg)
        else:
            # Transform the info message to a debug message if quiet is set
            if self.quiet:
                self.__logger.debug(msg)
            else:
                self.__logger.info(msg)

    def debug(self, msg):
        """Prints the debug message. The message is only stored in the log file if the watchdog is
        enabled.

        :param msg: the debug message
        """
        if self.__enabled:
            self.__logger.debug(msg)

    def log_variable(self, name, data):
        """Logs the given variable name and content into the log file.

        :param name: the name of the variable that will be displayed in the log
        :param data: the variable value
        """
        if self.__enabled:
            # pretty print the variable so that it is easily readable
            formatted_data = pprint.pformat(data, indent=2)
            self.__logger.debug("Variable '%s':\n%s", name, formatted_data)

    def log_probes(self, func_count, usdt_count, script):
        """Logs the SystemTap probe records and metrics, such as size of the script, # of probe
        locations etc.

        :param func_count: number of function probes
        :param usdt_count: number of USDT probes
        :param script: path to the SystemTap script
        """
        if not self.__enabled:
            return

        self.info(
            f"SystemTap script '{script}', size '{perun_log.format_file_size(os.stat(script).st_size)}'"
        )
        self.info(f"Number of function locations: '{func_count}', usdt locations: '{usdt_count}'")
        self.info(f"Number of probe points in the script: '{_count_script_probes(script)}'")

    def log_resources(self, processes, modules):
        """Logs the SystemTap and perun related resources that are being used on the system,
        such as the SystemTap processes and SystemTap kernel modules.

        :param processes: list of locked and lockless running processes, i.e.
                                             processes with or without existing lock file
        :param modules: list of locked and lockless kernel modules, i.e.
                                             SystemTap modules with or without existing lock file
        """
        locked_stap, lockless_stap = processes
        locked_modules, lockless_modules = modules
        warn_template = (
            "{} that are either not linked to any, or running from another, perun "
            "instance (project) found: '{}'. Removing them is recommended in order to "
            "avoid possible performance data corruption"
        )
        # Always show the warning regardless if the watchdog is enabled
        if lockless_stap:
            self.warn(
                warn_template.format(
                    "Active SystemTap processes",
                    [pgid for (_, _, pgid, _), _ in lockless_stap],
                )
            )
        if lockless_modules:
            self.warn(
                warn_template.format(
                    "Loaded SystemTap kernel modules",
                    [mod for mod, _ in lockless_modules],
                )
            )

        # The additional details should be only displayed if the watchdog is on
        self.log_variable("locked_stap", locked_stap)
        self.log_variable("lockless_stap", lockless_stap)
        self.log_variable("locked_modules", locked_modules)
        self.log_variable("lockless_modules", lockless_modules)


WATCH_DOG = Watchdog()


def _count_script_probes(script_path):
    """Counts the number of probe locations in the given SystemTap script.

    :param script_path: path to the script file
    :return: the number of probe locations in the script
    """
    with open(script_path, "r") as script:
        script_content = script.read()
    return script_content.count('probe process("')
