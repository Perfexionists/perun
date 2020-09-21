""" The Configuration class stores the CLI configuration provided by the user.
"""

import os
import time

from perun.collect.trace.collect_engine import CollectEngine
from perun.collect.trace.systemtap.engine import SystemTapEngine
from perun.collect.trace.ebpf.engine import BpfEngine
from perun.collect.trace.probes import Probes
from perun.collect.trace.values import OutputHandling

from perun.utils.exceptions import InvalidBinaryException
from perun.utils import is_executable_elf
import perun.logic.temp as temp


class Configuration:
    """ A class that stores the Tracer configuration provided by the CLI.

    :ivar Probes probes: the collection probes configuration
    :ivar bool keep_temps: keep the temporary files after the collection is finished
    :ivar bool zip_temps: zip and store the temporary files before they are deleted
    :ivar bool verbose_trace: the raw performance data collected will be more verbose
    :ivar bool quiet: the collection progress output will be less verbose
    :ivar bool watchdog: enables detailed logging during the collection
    :ivar bool diagnostics: enables detailed surveillance mode of the collector
    :ivar OutputHandling output_handling: store or discard the profiling command stdout and stderr
    :ivar CollectEngine engine: the collection engine to be used, e.g. SystemTap or eBPF
    :ivar float or None timeout: the timeout for the profiled command or None if indefinite
    :ivar str binary: the path to the binary file to be probed
    :ivar Executable executable: the Executable object containing the profiled command, args, etc.
    :ivar str timestamp: the time of the collection start
    :ivar int pid: the PID of the Tracer process
    :ivar str files_dir: the directory path of the temporary files
    :ivar str locks_dir: the directory path of the lock files
    """
    def __init__(self, executable, **cli_config):
        """ Constructs the Configuration object from the supplied CLI configuration

        :param Executable executable: an object containing the profiled command, args, etc.
        :param cli_config: the CLI configuration
        """
        # Set the some default values if not provided
        self.keep_temps = cli_config.get('keep_temps', False)
        self.zip_temps = cli_config.get('zip_temps', False)
        self.verbose_trace = cli_config.get('verbose_trace', False)
        self.quiet = cli_config.get('quiet', False)
        self.watchdog = cli_config.get('watchdog', False)
        self.diagnostics = cli_config.get('diagnostics', False)
        self.output_handling = cli_config.get('output_handling', OutputHandling.Default.value)
        self.engine = cli_config.get('engine', CollectEngine.default())
        self.stap_cache_off = cli_config.get('stap_cache_off', False)
        self.generate_dynamic_cg = cli_config.get('generate_dynamic_cg', False)
        self.run_optimizations = {}

        # Enable some additional flags if diagnostics is enabled
        if self.diagnostics:
            self.zip_temps = True
            self.verbose_trace = True
            self.watchdog = True
            self.output_handling = OutputHandling.Capture.value

        # Transform the output handling value to the enum element
        self.output_handling = OutputHandling(self.output_handling)

        # Normalize timeout value
        self.timeout = cli_config.get('timeout', None)
        if self.timeout <= 0:
            self.timeout = None

        # Set the executable and binary
        self.binary = cli_config.get('binary', None)
        self.executable = executable
        self.libs = list(cli_config.get('libs', ''))  # TODO: perform checks
        # No runnable command was given, terminate the collection
        if self.binary is None and not self.executable.cmd:
            raise InvalidBinaryException('')
        # Otherwise copy the cmd or binary parameter
        elif not executable.cmd:
            executable.cmd = self.binary
        elif self.binary is None:
            self.binary = executable.cmd

        # Check that the binary / executable file exists and is valid
        self.binary = os.path.realpath(self.binary)
        executable.cmd = os.path.realpath(executable.cmd)
        if not os.path.exists(self.binary) or not is_executable_elf(self.binary):
            raise InvalidBinaryException(self.binary)
        elif not os.path.exists(executable.cmd):
            raise InvalidBinaryException(executable.cmd)

        # Update the configuration with some additional values
        self.timestamp = time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime())
        self.pid = os.getpid()
        self.files_dir = temp.temp_path(os.path.join('trace', 'files'))
        self.locks_dir = temp.temp_path(os.path.join('trace', 'locks'))
        # Build a name of stats file corresponding to the supplied workload and configuration
        self.__stats_name = "opt::{}-[{}]-[{}]".format(
            os.path.basename(self.binary), executable.args.replace('/', '_'),
            executable.workload.replace('/', '_')
        )

        # Build the probes configuration
        self.probes = Probes(**cli_config)

    def engine_factory(self):
        """ Instantiates the engine object based on the string representation.

        This function should be invoked separately after the Configuration object exists, so that
        the Engine object is not lost due to a received signal etc., which would prevent successful
        cleanup of engine resources.
        """
        if self.engine == 'stap':
            self.engine = SystemTapEngine(self)
        else:
            self.engine = BpfEngine(self)

    def get_functions(self):
        """Access the configuration of the function probes

        :return dict: the function probes dictionary
        """
        return self.probes.func

    def prune_functions(self, remaining):
        """ Remove function probes not present in the 'remaining' set from the instrumentation

        :param dict remaining: the set of remaining functions and their sampling configuration
        """
        for func_name in list(self.probes.func.keys()):
            if func_name not in remaining:
                del self.probes.func[func_name]
            elif func_name not in self.probes.user_func and remaining[func_name] > 1:
                self.probes.func[func_name]['sample'] = remaining[func_name]

    def get_target(self):
        """ Obtain the target executable file.

        :return str: a path to the binary executable file
        """
        return self.binary

    def get_stats_name(self, specifier=None):
        """ Create a 'stats' file name based on the specifier.

        :param str or None specifier: an additional specifier for the stats file construction.
        :return str: a full path name of the stats file (which is not created, tho)
        """
        if specifier is not None:
            return self.__stats_name + "::{}".format(specifier)
        else:
            return self.__stats_name
