"""The eBPF engine implementation."""

import os
import json

import perun.utils.log as log
import perun.collect.trace.collect_engine as engine
import perun.collect.trace.ebpf.program as program
import perun.logic.temp as temp
import perun.utils.metrics as metrics
from perun.collect.trace.watchdog import WATCH_DOG
from perun.utils.external import environment, processes

try:
    import bcc
except ImportError:
    log.error(
        "Missing BCC frontend library for eBPF. Please refer to the Perun install instructions "
        "to resolve this issue or use a different collection engine"
    )


class BpfEngine(engine.CollectEngine):
    """The eBPF engine class, derived from the abstract CollectEngine class.

    :ivar program: a full path to the file that stores the generated eBPF collection program
    :ivar runtime_conf: a full path to the file that is used to configure the eBPF process
    :ivar data: a full path to the file that stores the raw performance data
    :ivar ebpf_process a subprocess object of the running eBPF process
    """

    name = "ebpf"

    def __init__(self, config):
        """Constructs the engine object.

        :param config: the collection parameters stored in the configuration object
        """
        super().__init__(config)
        self.program = self._assemble_file_name("program", ".c")
        self.runtime_conf = self._assemble_file_name("runtime_conf", ".json")
        self.data = self._assemble_file_name("data", ".txt")
        self.ebpf_process = None
        # Create the temporary collect files
        super()._create_collect_files([self.program, self.runtime_conf, self.data])

    def check_dependencies(self):
        """Checks the specific eBPF requirements and dependencies.

        The dependencies check is done indirectly by importing the bcc python module
        - if it exists, then the OS should already support the eBPF.
        """

    def available_usdt(self, **_):
        """Extracts the names of the available USDT probes within the binary files and libraries.

        Inspired by: https://github.com/iovisor/bcc/blob/master/tools/tplist.py

        :return: a list of the found USDT probe names per binary file
        """
        return {
            target: list(
                {probe.name.decode("utf-8") for probe in bcc.USDT(path=target).enumerate_probes()}
            )
            for target in self.targets
        }

    def assemble_collect_program(self, **kwargs):
        """Assemble the eBPF collection program.

        :param kwargs: the collection and probes configuration
        """
        program.assemble_ebpf_program(self.program, **kwargs)

    def collect(self, config, probes, **_):
        """Run the performance data collection according to the engine capabilities.

        :param config: the collection configuration object
        :param probes: the probes specification
        """
        # Create the runtime configuration file for the ebpf process with elevated privileges
        self._build_runtime_conf(config, probes)

        WATCH_DOG.info("Starting up the eBPF collection process.")
        # Run the new ebpf process with sudo privileges
        current_interpreter = environment.get_current_interpreter("3.6+")
        with processes.nonblocking_subprocess(
            f"sudo {current_interpreter} {_get_ebpf_file()} {self.runtime_conf}",
            {},
        ) as ebpf_proc:
            WATCH_DOG.info(f"The eBPF process is running, pid {ebpf_proc.pid}.")
            self.ebpf_process = ebpf_proc
            # Wait for the process to finish
            ebpf_proc.wait()
        command_time = temp.read_temp("ebpf:profiled_command.json")
        metrics.add_metric("command_time", command_time)
        WATCH_DOG.info("The eBPF collection process terminated.")

    def transform(self, probes, config, **_):
        """Transform the raw performance data to the perun profile resources.

        :param probes: the probes specification
        :param config: the collection configuration

        :return: a generator object that provides profile resources
        """
        WATCH_DOG.info("Transforming the raw performance data into a perun profile format")
        func_map = [{}] * (len(probes.func.keys()) + 1)
        # Every function probe keeps track of the current call sequence and sample value
        for func_probe in probes.func.values():
            func_map[func_probe["id"]] = {
                "name": func_probe["name"],
                "sample": func_probe["sample"],
                "seq": 0,
            }
        func_map[-1] = {"name": "timed_sampling_event", "sample": 1, "seq": 0}
        workload = config.executable.workload

        with open(self.data, "r") as raw_data:
            for line in raw_data:
                # Partition and convert the line
                pid, func_id, _, amount = list(map(int, line.split()))
                # Create the profile resource
                yield {
                    "amount": amount,
                    "uid": func_map[func_id]["name"],
                    "type": "mixed",
                    "subtype": "time delta",
                    "workload": workload,
                    "thread": pid,
                    "call-order": func_map[func_id]["seq"],
                    # 'call-time': call_time}
                }

                # Update the sequence number
                func_map[func_id]["seq"] += func_map[func_id]["sample"]
        _count_funcs(func_map, probes.func)

    def cleanup(self, config, **_):
        """Safely clean up any resource that is still in use, e.g. the eBPF collection process or
        temporary collect files.

        :param config: the collection configuration
        """
        WATCH_DOG.info("Cleaning up the eBPF-related resources.")
        # Terminate the eBPF process if it is still running
        self._terminate_process("ebpf_process")

        # Zip and delete (both optional) the temporary collect files
        self._finalize_collect_files(
            ["program", "runtime_conf", "data"], config.keep_temps, config.zip_temps
        )

    def _build_runtime_conf(self, config, probes):
        """Create the runtime configuration as a json-formatted file.

        :param config: the supplied collection configuration
        :param probes: the probes specification
        """
        with open(self.runtime_conf, "w") as config_handle:
            # Store the parameters that are needed by the separate eBPF process
            tracer_config = {
                "func": probes.func,
                "program_file": self.program,
                "data_file": self.data,
                "binary": config.binary,
                "command": config.executable.to_escaped_string(),
                "timeout": config.timeout,
                "optimizations": config.run_optimizations,
                "optimization_params": config.run_optimization_parameters,
            }
            json.dump(tracer_config, config_handle, indent=2)


def _get_ebpf_file():
    """Fetch the full path to the ebpf file that collects the performance data.

    :return: a full path to the ebpf.py file
    """
    return os.path.join(os.path.dirname(__file__), "ebpf.py")


def _count_funcs(func_map, probe_funcs):
    collected_funcs = set(val["name"] for val in func_map if val["seq"] >= 1)
    collected_funcs &= set(probe_funcs.keys())
    metrics.add_metric("collected_func", len(collected_funcs))
