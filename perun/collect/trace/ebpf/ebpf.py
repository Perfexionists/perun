"""The eBPF collection process that has to be invoked with elevated sudo privileges in order to
attach the selected probes.
"""

import json
import sys
import time
import contextlib
from bcc import BPF, PerfType, PerfSWConfig, PerfHWConfig

from perun.utils.external.processes import nonblocking_subprocess
from perun.collect.trace.optimizations.structs import Optimizations, Parameters
from perun.collect.trace.threads import TimeoutThread, PeriodicThread
import perun.logic.temp as temp
import perun.utils.log as log


class BpfContext:
    """A BPF context class that stores the reference to the BPF instance, output data file and
    runtime configuration.

    :ivar config: the runtime configuration
    :ivar binary: path to the binary executable file
    :ivar optimizations: the list of enabled optimizations
    :ivar o_params: the optimization parameters
    :ivar bpf: the BPF instance
    :ivar data: the raw performance data file
    :ivar lost: the lost records counter

    :ivar iter: the Dynamic Probing check iteration
    :ivar threshold: the number of function calls that trigger probe deactivation
    :ivar re_attached: specifies whether the Dynamic Probing should attempt to reactivate
                            probes that were previously disabled.
    :ivar detached: the list of detached probes
    :ivar probes: simple data structure used by the optimization techniques
    """

    def __init__(self, runtime_config):
        # Load the runtime configuration
        self.config = BpfContext._load_config(runtime_config)
        self.binary = self.config["binary"]
        self.optimizations = self.config["optimizations"]
        self.o_params = self.config["optimization_params"]
        # Create the BPF instance
        self.usdt_context = None  # Needed for when the USDT probes are supported
        self.bpf = BPF(src_file=self.config["program_file"])
        # Open the data file for continuous write
        self.data = open(self.config["data_file"], "w")
        self.lost = 0

        # Dynamic probing related data
        self.iter = 0
        self.threshold = self.o_params.get(Parameters.PROBING_THRESHOLD.value, None)
        self.re_attach = self.o_params.get(Parameters.PROBING_REATTACH.value, None)
        self.detached = []
        self.dynamic_probes = [{}] * len(self.config["func"])
        for func in self.config["func"].values():
            self.dynamic_probes[int(func["id"])] = {
                "name": func["name"],
                "count": 0,
                "sampling": func["sample"],
                "detached": False,
                "interval": 1,
                "re_attach_at": 0,
            }

    def dynamic_probing(self):
        """Implementation of the Dynamic Probing method that periodically checks the number of
        function calls for all profiled functions.
        """
        self.iter += 1
        # Iterate all of the probes and check counter
        detachable = []
        for probe in self.dynamic_probes:
            # Find probes that have exceeded the threshold
            if probe["count"] >= self.threshold and not probe["detached"]:
                probe["detached"] = True
                detachable.append(probe)
        # And detach them
        self.detach_functions([probe["name"] for probe in detachable])

        # Also check the reattach counters
        if self.re_attach:
            attachable = []
            for idx, probe in enumerate(self.detached):
                # Find probes to reattach
                if probe["re_attach_at"] <= self.iter:
                    attachable.append(probe["name"])
                    del self.detached[idx]
            # Update the structures
            for probe in detachable:
                probe["interval"] *= 2
                probe["re_attach_at"] = self.iter + probe["interval"]
                probe["count"] = 0
                probe["detached"] = False
                self.detached.append(probe)
            # Reattach selected functions
            self.attach_functions(attachable)

    def add_count(self, func_id):
        """Update the call count for the given function.

        :param func_id: function identification
        """
        prb = self.dynamic_probes[func_id]
        prb["count"] += prb["sampling"]

    def detach_functions(self, functions):
        """Detach specified functions.

        :param functions: a collection of function names to detach
        """
        for probe in functions:
            self.bpf.detach_uprobe(name=self.binary, sym=probe)
            self.bpf.detach_uretprobe(name=self.binary, sym=probe)

    def attach_functions(self, functions):
        """Attach all of the function probes to the profiled process

        :param functions: the function names
        """
        for func in functions:
            # Attach the entry function probe
            self.bpf.attach_uprobe(name=self.binary, sym=func, fn_name=f"entry_{func}")
            # Attach the exit function probe
            self.bpf.attach_uretprobe(name=self.binary, sym=func, fn_name=f"exit_{func}")

    def attach_usdt(self, usdt_probes):
        """Attach all of the USDT probes to the supplied USDT context object

        :param usdt_probes: the USDT probes specification
        """
        for usdt in usdt_probes.values():
            # If the USDT probe has no pair, attach a single probe
            probes = [f"usdt_{usdt['name']}"]
            # Otherwise attach both entry and exit probes
            if usdt["pair"] != usdt["name"]:
                probes = [f"entry_{usdt['name']}", f"exit_{usdt['name']}"]
            for probe in probes:
                self.usdt_context.enable_probe(usdt["name"], probe)

    def attach_timer(self):
        """Attach SW CPU CLOCK timer that will switch the phases of Timed Sampling"""
        # Use single CPU to generate events only once (as opposed to every CPU generating events)
        self.bpf.attach_perf_event(
            ev_type=PerfType.SOFTWARE,
            ev_config=PerfSWConfig.CPU_CLOCK,
            fn_name="set_enabled",
            sample_freq=self.o_params[Parameters.TIMEDSAMPLE_FREQ.value],
            cpu=0,
        )

    def attach_cache_counters(self, pid):
        """Attach HW cache counters.

        :param pid: the pid of the target process
        """
        # Attach cache miss counter probe
        self.bpf.attach_perf_event(
            ev_type=PerfType.HARDWARE,
            ev_config=PerfHWConfig.CACHE_MISSES,
            fn_name="on_cache_miss",
            sample_period=1,
            pid=pid,
        )
        # Attach cache access counter probe
        self.bpf.attach_perf_event(
            ev_type=PerfType.HARDWARE,
            ev_config=PerfHWConfig.CACHE_REFERENCES,
            fn_name="on_cache_ref",
            sample_period=1,
            pid=pid,
        )

    @staticmethod
    def _load_config(config_file):
        """Load the runtime configuration from the given file.

        :param config_file: a full path to the runtime configuration file

        :return: the configuration dictionary parsed from the JSON file
        """
        with open(config_file, "r") as json_handle:
            return json.load(json_handle)


# A global instance of the context class since the BPF event callback needs to access it
BPF_CTX = BpfContext(sys.argv[1])

_BPF_SLEEP = 1
_BPF_POLL_SLEEP = 500


def ebpf_runner():
    """Attaches the probes to the given program locations (functions, usdt, cache events, ...)
    and runs the profiled command to gather the performance data.
    """
    timed_sampling_on = Optimizations.TIMED_SAMPLING.value in BPF_CTX.optimizations
    dynamic_probing_on = Optimizations.DYNAMIC_PROBING.value in BPF_CTX.optimizations

    # Attach the probes
    BPF_CTX.attach_functions([probe["name"] for probe in BPF_CTX.config["func"].values()])
    if timed_sampling_on:
        BPF_CTX.attach_timer()
    # TODO: the USDT and cache locations are not working properly as of now
    # _attach_usdt(u, conf['usdt'])
    # _attach_counters(bpf, wrapper_pid)

    # Give BPF time to properly attach all the probes
    time.sleep(_BPF_SLEEP)

    # Multiple context managers are used (some even conditionally), thus a CM stack is used
    with contextlib.ExitStack() as cm_stack:
        # Spawn a timeout thread
        timeout = cm_stack.enter_context(TimeoutThread(BPF_CTX.config["timeout"]))
        # Spawn a dynamic probing thread if needed
        if dynamic_probing_on:
            cm_stack.enter_context(PeriodicThread(0.5, BPF_CTX.dynamic_probing, []))
        # Run the profiled command
        profiled = cm_stack.enter_context(nonblocking_subprocess(BPF_CTX.config["command"], {}))
        start_time = time.time()

        # Get the BPF output buffer and read the performance data
        BPF_CTX.bpf["records"].open_perf_buffer(_print_event, page_cnt=128, lost_cb=_log_lost)
        try:
            while profiled.poll() is None and not timeout.reached():
                BPF_CTX.bpf.perf_buffer_poll(_BPF_POLL_SLEEP)
        except KeyboardInterrupt:
            profiled.terminate()
        end_time = time.time()
        profiled_time = end_time - start_time
    # Wait until all the raw data is written to the data file
    # TODO: temporary hack, not sure how to do it better
    while True:
        # Attempt to poll the records until timeout is hit, i.e. no more records in buffer
        poll_start = time.time()
        BPF_CTX.bpf.perf_buffer_poll(_BPF_POLL_SLEEP)
        poll_duration = time.time() - poll_start
        if poll_duration * 1000 > _BPF_POLL_SLEEP * 0.25:
            break
    time.sleep(_BPF_SLEEP)
    log.write(f"Lost: {BPF_CTX.lost} records")
    BPF_CTX.data.close()
    temp.store_temp("ebpf:profiled_command.json", profiled_time, json_format=True)


def _print_event(_, data, __):
    """A callback function used when a new performance data is received through the buffer.
    Also keeps track of how many times each function was called so that dynamic probing
    can be leveraged.

    :param data: the data part of the performance event
    """
    # Obtain the raw performance record produced by the eBPF process
    duration = BPF_CTX.bpf["records"].event(data)
    BPF_CTX.add_count(duration.id)
    BPF_CTX.data.write(
        f"{duration.pid} {duration.id} {duration.entry_ns} {duration.exit_ns - duration.entry_ns}\n"
    )


def _log_lost(lost):
    """Tracks the number of lost eBPF records due to the internal buffer being full and other
    issues.

    :param lost: the number of lost records
    """
    BPF_CTX.lost += lost


if __name__ == "__main__":
    ebpf_runner()
