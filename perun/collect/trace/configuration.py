"""The Configuration class stores the CLI configuration provided by the user."""

import os
import time

from perun.collect.trace.collect_engine import CollectEngine
from perun.collect.trace.systemtap.engine import SystemTapEngine
from perun.collect.trace.probes import Probes
from perun.collect.trace.values import OutputHandling

from perun.utils.exceptions import InvalidBinaryException
from perun.utils.external.executable import find_executable
from perun.logic import temp


class Configuration:
    """A class that stores the Tracer configuration provided by the CLI.

    :ivar probes: the collection probes configuration
    :ivar keep_temps: keep the temporary files after the collection is finished
    :ivar zip_temps: zip and store the temporary files before they are deleted
    :ivar verbose_trace: the raw performance data collected will be more verbose
    :ivar quiet: the collection progress output will be less verbose
    :ivar watchdog: enables detailed logging during the collection
    :ivar diagnostics: enables detailed surveillance mode of the collector
    :ivar output_handling: store or discard the profiling command stdout and stderr
    :ivar engine: the collection engine to be used, e.g. SystemTap or eBPF
    :ivar stap_cache_off: specifies if systemtap cache should be enabled or disabled
    :ivar generate_dynamic_cg: specifies whether dynamic CG should be reconstructed from trace
    :ivar no_profile: disables profile generation
    :ivar run_optimizations: list of run-phase optimizations that are enabled
    :ivar run_optimization_parameters: optimization parameter name -> value mapping
    :ivar timeout: the timeout for the profiled command or None if indefinite
    :ivar binary: the path to the binary file to be probed
    :ivar executable: the Executable object containing the profiled command, args, etc.
    :ivar libs: additional libraries that are profiled with the given binary
    :ivar timestamp: the time of the collection start
    :ivar pid: the PID of the Tracer process
    :ivar files_dir: the directory path of the temporary files
    :ivar locks_dir: the directory path of the lock files
    :ivar stats_data: compactly stores data necessary for building dynamic stats
    """

    def __init__(self, executable, **cli_config):
        """Constructs the Configuration object from the supplied CLI configuration

        :param executable: an object containing the profiled command, args, etc.
        :param cli_config: the CLI configuration
        """
        # Set the some default values if not provided
        self.keep_temps = cli_config.get("keep_temps", False)
        self.zip_temps = cli_config.get("zip_temps", False)
        self.verbose_trace = cli_config.get("verbose_trace", False)
        self.quiet = cli_config.get("quiet", False)
        self.watchdog = cli_config.get("watchdog", False)
        self.diagnostics = cli_config.get("diagnostics", False)
        self.output_handling = cli_config.get("output_handling", OutputHandling.DEFAULT.value)
        self.engine = cli_config.get("engine", CollectEngine.default())
        self.stap_cache_off = cli_config.get("stap_cache_off", False)
        self.generate_dynamic_cg = cli_config.get("generate_dynamic_cg", False)
        self.no_profile = cli_config.get("no_profile", False)
        self.cg_extraction = cli_config.get("only_extract_cg", False)
        # TODO: temporary
        self.maximum_threads = cli_config.get("max_simultaneous_threads", 5)
        self.extract_mcg = cli_config.get("extract_mixed_cg", False)
        self.no_ds_update = cli_config.get("no_ds_update", False)
        # The run optimization values should be provided by the Optimization module, if enabled
        self.run_optimizations = []
        self.run_optimization_parameters = {}

        # Enable some additional flags if diagnostics is enabled
        if self.diagnostics:
            self.zip_temps = True
            self.verbose_trace = True
            self.watchdog = True
            self.output_handling = OutputHandling.CAPTURE.value

        # Transform the output handling value to the enum element
        self.output_handling = OutputHandling(self.output_handling)

        # Normalize timeout value
        self.timeout = cli_config.get("timeout", None)
        if self.timeout <= 0:
            self.timeout = None

        # Set the executable and binary
        self.binary = find_executable(cli_config.get("binary", None))
        self.executable = executable
        self.executable.cmd = find_executable(self.executable.cmd)
        self.libs = list(cli_config.get("libs", ""))
        self._resolve_executables()

        # Update the configuration with some additional values
        self.timestamp = time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime())
        self.pid = os.getpid()
        self.files_dir = temp.temp_path(os.path.join("trace", "files"))
        self.locks_dir = temp.temp_path(os.path.join("trace", "locks"))

        # Build the probes configuration
        self.probes = Probes(self.binary, self.libs, **cli_config)
        self.stats_data = {}

    def engine_factory(self):
        """Instantiates the engine object based on the string representation.

        This function should be invoked separately after the Configuration object exists, so that
        the Engine object is not lost due to a received signal etc., which would prevent successful
        cleanup of engine resources.
        """
        if self.engine == "stap":
            self.engine = SystemTapEngine(self)
        else:
            # Import on demand since eBPF support is optional
            import perun.collect.trace.ebpf.engine as bpf

            self.engine = bpf.BpfEngine(self)

    def get_functions(self):
        """Access the configuration of the function probes

        :return: the function probes dictionary
        """
        return self.probes.func

    def prune_functions(self, remaining):
        """Remove function probes not present in the 'remaining' set from the instrumentation

        :param remaining: the set of remaining functions and their sampling configuration
        """
        for func_name in list(self.probes.func.keys()):
            if func_name not in remaining:
                del self.probes.func[func_name]
            elif func_name not in self.probes.user_func and remaining[func_name] > 1:
                self.probes.func[func_name]["sample"] = remaining[func_name]

    def set_run_optimization(self, optimizations, parameters):
        """Allows the Optimization module to set run optimizations and their parameters
        directly in the Configuration object.

        :param optimizations: list of optimization names
        :param parameters: optimization parameter name -> parameter value
        """
        self.run_optimizations = optimizations
        self.run_optimization_parameters = parameters

    def get_target(self):
        """Obtain the target executable file.

        :return: a path to the binary executable file
        """
        return self.binary

    def _resolve_executables(self):
        """Check that all of the supplied executables (command, binary, libraries)
        are accessible and executable, and obtain their real paths (absolute and no symlinks)
        """
        # No runnable command was given, terminate the collection
        if self.binary is None and not self.executable.cmd:
            raise InvalidBinaryException("")
        # Otherwise copy the cmd or binary parameter
        if not self.executable.cmd:
            self.executable.cmd = self.binary
        elif self.binary is None:
            self.binary = self.executable.cmd

        # Check that all of the supplied libraries exist and are executable
        resolved_libs = []
        for lib in self.libs:
            lib = find_executable(lib)
            if lib is not None:
                resolved_libs.append(lib)
        self.libs = resolved_libs
