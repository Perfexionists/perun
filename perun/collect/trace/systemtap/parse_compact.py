"""Module for parsing and transforming the raw performance records from trace collector
(systemtap engine) into a perun profile.
"""

import os
import collections
import array
from multiprocessing import Process

import perun.collect.trace.processes as proc
import perun.utils.metrics as metrics
import perun.collect.trace.optimizations.resources.manager as resources
import perun.logic.stats as stats
from perun.profile.factory import Profile

from perun.collect.trace.watchdog import WATCH_DOG
import perun.collect.trace.values as vals
from perun.collect.trace.optimizations.call_graph import CallGraphResource
from perun.collect.trace.optimizations.optimization import build_stats_names
from perun.utils.common.common_kit import chunkify
from perun.utils.exceptions import (
    SignalReceivedException,
    StatsFileNotFoundException,
    SuppressedExceptions,
)


class ThreadContext:
    """Class that keeps track of function call stack, USDT hit stack, function call sequence
    map and bottom indicator per each active thread.

    :ivar start: the thread starting record
    :ivar func_stack: keeps track of the function call stack
    :ivar usdt_stack: stores stack of USDT probe hits for each probe
    :ivar seq_map: tracks sequence number for each probe that identifies the order of records
    :ivar bottom_flag: flag used to identify records that have no more callees
    :ivar depth: the current trace (call stack) depth
    """

    def __init__(self):
        self.start = {}
        self.func_stack = []
        self.usdt_stack = collections.defaultdict(list)
        self.seq_map = collections.defaultdict(int)
        self.bottom_flag = False
        self.depth = -1


class TransformContext:
    """Class that keeps track of the context information during the raw data transformation.

    :ivar verbose_trace: switches between verbose / compact trace output
    :ivar binaries: all profiled binaries (including libraries)
    :ivar workload: the workload specification of the current run
    :ivar probes: the probes specification
    :ivar probes_hit: a set of actually hit probes
    :ivar per_thread: per-thread context for function / usdt stacks, sequence maps etc
    :ivar bottom: summary of total elapsed time per bottom functions per thread
    :ivar level_times_exclusive: summary of exclusive times per trace depth
    """

    def __init__(self, probes, binaries, verbose_trace, workload):
        """
        :param probes: the probes specification
        :param binaries: all profiled binaries (including libraries)
        :param verbose_trace: switches between verbose / compact trace output
        :param workload: the workload specification of the current run
        """
        self.verbose_trace = verbose_trace
        self.binaries = binaries
        self.workload = workload
        self.probes = probes
        self.probes_hit = set()
        self.per_thread = collections.defaultdict(ThreadContext)
        # Thread -> function -> total elapsed time
        # Not included in 'per_thread' since we want to keep the values even after threads terminate
        self.bottom = collections.defaultdict(lambda: collections.defaultdict(int))

        # Thread -> level -> total exclusive time
        self.level_times_exclusive = collections.defaultdict(lambda: collections.defaultdict(int))

        # ID Map is used to map probe ID -> function name in non-verbose mode
        # and function name -> function name in verbose mode (basically a no-op)
        # TODO: temporary, solve dynamic call graph properly
        self.dyn_cg = {probe["name"]: set() for probe in self.probes.func.values()}

        # Compact dictionaries used for computing dynamic stats
        # tid -> uid -> [amounts]
        self.funcs = collections.defaultdict(
            lambda: collections.defaultdict(lambda: {"e": array.array("Q"), "i": array.array("Q")})
        )
        # pid -> [processes]
        self.processes = collections.defaultdict(list)
        self.threads = {}


def trace_to_profile(data_file, config, probes, **_):
    """Process raw data and (optionally) convert them into a Perun profile. The conversion is
    delegated to a separate process to speedup the processing task.

    :param data_file: name of the file containing raw data
    :param config: an object containing configuration parameters
    :param probes: an object containing info about probed locations
    :return: the resulting profile
    """
    # Profile should not be generated, simply process the raw data and return empty profile
    if config.no_profile:
        for _ in process_records(data_file, config, probes):
            pass
        return Profile()

    # Otherwise create resource queue (passing resources) and profile queue (passing profile)
    resource_queue = proc.SafeQueue(vals.RESOURCE_QUEUE_CAPACITY)
    profile_queue = proc.SafeQueue(1)
    # Also create a new process for transforming the resources into a profile
    profile_process = Process(target=profile_builder, args=(resource_queue, profile_queue))

    try:
        # Start the process
        profile_process.start()
        # Process and send a chunk of resources
        for res in chunkify(process_records(data_file, config, probes), vals.RESOURCE_CHUNK):
            resource_queue.write(list(res))
        resource_queue.end_of_input()
        # After all resources have been sent, wait for the resulting profile
        profile = profile_queue.read_large()

        return profile
    finally:
        # Cleanup the queues
        resource_queue.close_writer()
        profile_queue.close_reader()
        # Wait for the transformation process to finish
        profile_process.join(timeout=vals.CLEANUP_TIMEOUT)
        if profile_process.exitcode is None:
            WATCH_DOG.info(
                f"Failed to terminate the profile transformation process PID {profile_process.pid}."
            )


def profile_builder(resource_queue, profile_queue):
    """Transforms resources into a Perun profile. Should be run as a standalone process that
    obtains resources from a queue and returns the resulting profile through a queue.

    :param resource_queue: a multiprocessing queue for obtaining resources
    :param profile_queue: a multiprocessing queue for passing profile
    """
    try:
        # Create a new profile structure
        profile = Profile()

        # Build the profile
        profile_resources = resource_queue.read()
        while profile_resources is not None:
            profile.update_resources({"resources": profile_resources}, "global")
            profile_resources = resource_queue.read()
        # Pass the resulting profile back to the main process
        profile_queue.write(profile)
        profile_queue.end_of_input()
    except SignalReceivedException:
        # Interrupt signals should cause the process to properly terminate
        # We do not want to raise an exception since this runs as another process
        pass
    finally:
        # Regardless of type of termination, queue resources should be cleaned
        resource_queue.close_reader()
        profile_queue.close_writer()


def process_records(data_file, config, probes):
    """Transforms the collection output into performance resources. The
    collected time data are paired and provided as resources dictionaries.

    :param data_file: name of the collection output file
    :param config: the configuration object
    :param probes: the Probes object

    :return: generator object that produces dictionaries representing the resources
    """
    # Initialize the context
    binaries = set(map(os.path.basename, config.libs + [config.binary]))
    ctx = TransformContext(probes, binaries, config.verbose_trace, config.executable.workload)
    # Get the handlers
    handlers = _record_handlers()

    metrics.start_timer("data-processing")
    record = None
    try:
        for record in parse_records(data_file, probes, config.verbose_trace):
            try:
                # Invoke the correct handler based on the record type and return the
                # resulting resource, if any
                resource = handlers[record["type"]](record, ctx)
                if resource:
                    yield resource
            except (KeyError, IndexError):
                continue

        # Register computed metrics
        metrics.end_timer("data-processing")
        metrics.add_metric(
            "coverages",
            {
                tid: {
                    "hotspot_coverage_abs": sum(val for val in bottom.values()),
                    "hotspot_coverage_count": len(bottom.keys()),
                }
                for tid, bottom in ctx.bottom.items()
            },
        )
        metrics.add_metric("trace_level_times_exclusive", dict(ctx.level_times_exclusive))
        all_probes = set(probes.func.keys()) | set(probes.usdt.keys())
        metrics.add_metric("collected_probes", len(ctx.probes_hit & all_probes))
        config.stats_data = {"p": ctx.processes, "t": ctx.threads, "f": ctx.funcs}

        # TODO: temporary
        if config.extract_mcg:
            _build_mixed_cg_tmp(config, ctx)
        else:
            _build_alternative_cg(config, ctx)

    except Exception:
        WATCH_DOG.info("Error while processing the raw trace output")
        WATCH_DOG.debug(f"Record: {record}")
        WATCH_DOG.debug(f"Context: {ctx}")
        raise


def _build_mixed_cg_tmp(config, ctx):
    cg_stats_name, _ = build_stats_names(config)
    static_cg = resources.extract(
        resources.Resources.CALL_GRAPH_ANGR,
        stats_name=cg_stats_name,
        binary=config.get_target(),
        libs=config.libs,
        cache=False,
        restricted_search=False,
    )
    cg_map = {
        func_name: {"callees": callees} for func_name, callees in static_cg["call_graph"].items()
    }

    mixed_call_graph = CallGraphResource().add_dyn(ctx.dyn_cg, cg_map, static_cg["control_flow"])
    resources.store(
        resources.Resources.PERUN_CALL_GRAPH,
        stats_name=cg_stats_name,
        call_graph=mixed_call_graph,
        cache=False,
    )


def _build_alternative_cg(config, ctx):
    """Builds the dynamic and mixed CGR and stores them into the stats directory.
    The mixed CG still uses the statically obtained Call Graph to combine with the dynamic one
    in order to retrieve more general Call Graph structure.

    :param config: the configuration object
    :param ctx: the parsing context which contains caller-callee relationships
    """
    cg_stats_name, _ = build_stats_names(config)

    # Extract the saved static Call Graph
    try:
        static_cg = stats.get_stats_of(cg_stats_name, ["perun_cg"])["perun_cg"]
    except StatsFileNotFoundException:
        return

    # Extract dynamic and mixed Call Graphs if available
    prefix = [("dynamic", "d"), ("mixed", "m")]
    cgs = {}
    for cg_type, cg_prefix in prefix:
        cgs[cg_type] = {}
        with SuppressedExceptions(StatsFileNotFoundException):
            cgr = stats.get_stats_of(cg_prefix + cg_stats_name, ["perun_cg"])["perun_cg"]
            cgs[cg_type] = cgr["call_graph"]["cg_map"]
    if not cgs["mixed"]:
        # If no mixed call graph is found, use static for initial merge
        cgs["mixed"] = static_cg["call_graph"]["cg_map"]
    cfg = static_cg["control_flow"]

    # Build the mixed Call Graph Resource using the static and dynamic call graphs
    mixed_call_graph = CallGraphResource().add_dyn(ctx.dyn_cg, cgs["mixed"], cfg)
    # Build the dynamic Call Graph Resource using only the dynamic call graph
    dynamic_call_graph = CallGraphResource().add_dyn(ctx.dyn_cg, cgs["dynamic"], cfg)

    # Store the new call graph versions
    resources.store(
        resources.Resources.PERUN_CALL_GRAPH,
        stats_name="m" + cg_stats_name,
        call_graph=mixed_call_graph,
        cache=False,
    )
    resources.store(
        resources.Resources.PERUN_CALL_GRAPH,
        stats_name="d" + cg_stats_name,
        call_graph=dynamic_call_graph,
        cache=False,
    )


def _record_handlers():
    """Mapping of a raw data record type to its corresponding function handler.

    :return: the mapping dictionary
    """
    return {
        vals.RecordType.PROCESS_BEGIN.value: _record_process_begin,
        vals.RecordType.PROCESS_END.value: _record_process_end,
        vals.RecordType.THREAD_BEGIN: _record_thread_begin,
        vals.RecordType.THREAD_END: _record_thread_end,
        vals.RecordType.FUNC_BEGIN.value: _record_func_begin,
        vals.RecordType.FUNC_END.value: _record_func_end,
        vals.RecordType.USDT_BEGIN.value: _record_usdt_begin,
        vals.RecordType.USDT_END.value: _record_usdt_end,
        vals.RecordType.USDT_SINGLE.value: _record_usdt_single,
        vals.RecordType.CORRUPT.value: _record_corrupt,
    }


def _record_corrupt(_, __):
    """Corrupted records are simply discarded.

    :return: empty dictionary
    """
    return {}


def _record_process_begin(record, ctx):
    """Handler for process begin probe. We delegate the action to the thread handler.

    :param record: the parsed raw data record
    :param ctx: the parsing context object

    :return: empty dictionary
    """
    return _record_thread_begin(record, ctx)


def _record_process_end(record, ctx):
    """Handler for the process termination probe that generates special process context record.

    :param record: the parsed raw data record
    :param ctx: the parsing context object

    :return: process resource
    """
    # The .begin and .end probes are sometimes triggered by other spawned processes, filter them
    if record["id"] not in ctx.binaries:
        # Remove the per-thread record for the given tid
        del ctx.per_thread[record["tid"]]
        return {}

    # The process ending probe can also be fired when a thread is forcefully terminated by the
    # process and not properly joined / exited
    # We can distinguish those two cases by comparing the PID and TID
    resource = _record_thread_end(record, ctx)
    if record["tid"] == record["pid"]:
        resource["uid"] = "!ProcessResource!"
        resource["ppid"] = record["ppid"]
        ctx.processes[resource["pid"]].append((resource["ppid"], resource["amount"]))
    return resource


def _record_thread_begin(record, ctx):
    """Handler for thread begin probe that creates a new thread context.

    :param record: the parsed raw data record
    :param ctx: the parsing context object

    :return: empty dictionary
    """
    ctx.per_thread[record["tid"]].start = record
    return {}


def _record_thread_end(record, ctx):
    """Handler for thread end probe that produces thread resource and cleans up thread context.

    :param record: the parsed raw data record
    :param ctx: the parsing context object

    :return: thread resource
    """
    # Build thread resource with additional PID attribute
    thread_start = ctx.per_thread[record["tid"]].start
    resource = _build_resource(thread_start, record, "!ThreadResource!", ctx.workload)
    resource["pid"] = record["pid"]
    # Remove the thread context
    del ctx.per_thread[record["tid"]]
    ctx.threads[resource["tid"]] = (resource["pid"], resource["amount"])
    return resource


def _record_func_begin(record, ctx):
    """Handler for the entry function probes.

    :param record: the parsed raw data record
    :param ctx: the parsing context object

    :return: empty dictionary
    """
    record["callee_tmp"] = 0
    record["callee_time"] = 0
    ctx.probes_hit.add(record["id"])
    tid_ctx = ctx.per_thread[record["tid"]]
    try:
        # Register new timestamp for exclusive time computation
        parent_func = tid_ctx.func_stack[-1]
        if parent_func["callee_tmp"]:
            # Handle cases where we somehow lost return probe, overapproximate the exclusive time
            parent_func["callee_time"] += record["timestamp"] - parent_func["callee_tmp"]
        parent_func["callee_tmp"] = record["timestamp"]

        # Update the dynamic call graph structure
        caller_record = tid_ctx.func_stack[-1]
        ctx.dyn_cg[caller_record["id"]].add(record["id"])
    except IndexError:
        pass
    # Add the record to the trace stack
    tid_ctx.bottom_flag = True
    tid_ctx.depth += 1
    tid_ctx.func_stack.append(record)
    return {}


def _record_func_end(record, ctx):
    """Handler for the exit function probes.

    :param record: the parsed raw data record
    :param ctx: the parsing context object

    :return: profile resource dictionary or empty dictionary if matching failed
    """
    resource = {}
    record_tid = record["tid"]
    thread_ctx = ctx.per_thread[record_tid]
    stack = thread_ctx.func_stack
    matching_record = {}
    # In most cases, the record matches the top record in the stack
    depth_diff = 1
    if stack and record["id"] == stack[-1]["id"] and record["timestamp"] > stack[-1]["timestamp"]:
        matching_record = stack.pop()
    # However, if not, then traverse the whole stack and attempt to find matching record
    else:
        for idx, stack_item in enumerate(reversed(stack)):
            if record["id"] == stack_item["id"] and record["timestamp"] > stack_item["timestamp"]:
                depth_diff = idx
                stack[:] = stack[: len(stack) - idx]
                matching_record = stack.pop()
                break
    if matching_record:
        # Compute the exclusive time
        resource = _build_resource(matching_record, record, record["id"], ctx.workload)
        try:
            prev_entry = stack[-1]["callee_tmp"]
            if prev_entry:
                stack[-1]["callee_time"] += record["timestamp"] - prev_entry
                stack[-1]["callee_tmp"] = 0
        except IndexError:
            pass
        resource["exclusive"] = resource["amount"] - matching_record["callee_time"]
        ctx.level_times_exclusive[record_tid][thread_ctx.depth] += resource["exclusive"]
        # Compute the bottom time
        if thread_ctx.bottom_flag:
            ctx.bottom[record_tid][record["id"]] += resource["amount"]
        thread_ctx.bottom_flag = False
        thread_ctx.depth -= depth_diff
        func = ctx.funcs[resource["tid"]][resource["uid"]]
        func["e"].append(abs(resource["exclusive"]))
        func["i"].append(abs(resource["amount"]))
    return resource


def _record_usdt_single(record, ctx):
    """Handler for the single USDT probes (not paired).

    :param record: the parsed raw data record
    :param ctx: the parsing context object

    :return: profile resource dictionary or empty dictionary if no resource could be created
    """
    ctx.probes_hit.add(record["id"])
    matching_record, usdt_uid = _pair_usdt(ctx, record)
    return _build_resource(matching_record, record, usdt_uid, ctx.workload)


def _record_usdt_begin(record, ctx):
    """Handler for the entry USDT probes (paired).

    :param record: the parsed raw data record
    :param ctx: the parsing context object

    :return: empty dictionary
    """
    ctx.probes_hit.add(record["id"])
    ctx.per_thread[record["tid"]].usdt_stack[record["id"]].append(record)
    return {}


def _record_usdt_end(record, ctx):
    """Handler for the exit USDT probes (paired).

    :param record: the parsed raw data record
    :param ctx: the parsing context object

    :return: profile resource dictionary
    """
    # Obtain the corresponding probe pair and matching record
    matching_record, usdt_uid = _pair_usdt(ctx, record, ctx.probes.usdt_reversed[record["id"]])
    return _build_resource(matching_record, record, usdt_uid, ctx.workload)


def _pair_usdt(ctx, record, pair=None):
    """Obtain matching USDT record for the given record. The matching record is either specified
    by the record ID (for single USDT) or pairing name (for paired USDT, i.e., distinct entry and
    exit probes).

    :param ctx: the parsing context object
    :param record: the parsed raw data record
    :param pair: ID of the paired probe
    :return:
    """
    # Get the probe stack
    stack = ctx.per_thread[record["tid"]].usdt_stack[record["id"] if pair is None else pair]
    try:
        # Get the matching record and create resource UID
        matching_record = stack.pop()
        return matching_record, f"{matching_record['id']}#{record['id']}"
    except IndexError:
        # No matching record found
        return {}, ""
    finally:
        # For single USDT probes we need to store the record for future pairing
        if pair is not None:
            stack.append(record)


def _build_resource(record_entry, record_exit, uid, workload):
    """Creates the profile resource from the entry and exit records.

    :param record_entry: the entry raw data record
    :param record_exit: the exit raw data record
    :param uid: the resource UID
    :param workload: the collection workload

    :return: the resulting profile resource
    """
    if not record_entry:
        return {}
    # Can also contain exclusive
    return {
        "amount": record_exit["timestamp"] - record_entry["timestamp"],
        "timestamp": record_entry["timestamp"],
        "call-order": record_entry["seq"],
        "uid": uid,
        "tid": record_entry["tid"],
        "type": "mixed",
        "subtype": "time delta",
        "location": record_entry["loc"],
        "workload": workload,
    }


def parse_records(file_name, probes, verbose_trace):
    """Parse the raw data line by line, each line represented as a dictionary of components.

    :param file_name: name of the file containing raw collection data
    :param probes: class containing probed locations
    :param verbose_trace: flag indicating whether the raw data are verbose or not

    :return: a generator object that returns parsed raw data lines
    """
    # ID (numeric id or name) -> (NAME, SAMPLE)
    dict_key = "name" if verbose_trace else "id"
    probe_map = {
        str(probe[dict_key]): (
            probe["name"],
            probe["sample"],
            os.path.basename(probe["lib"]),
        )
        for probe in list(probes.func.values()) + list(probes.usdt.values())
    }
    # TID -> UID -> SEQUENCE
    seq_map = collections.defaultdict(lambda: collections.defaultdict(int))

    with open(file_name, "r") as trace:
        cnt = 0
        while True:
            try:
                cnt += 1
                line = trace.readline()
                if not line:
                    break
                # The line should contain the following values:
                # 'type' 'tid' ['pid'] ['ppid'] 'timestamp';'probe id'
                # where thread records have 'pid' and process records have 'pid', 'ppid'
                major_components = line.split(";")
                minor_components = major_components[0].split()
                record_type = int(minor_components[0])
                record_tid = int(minor_components[1])
                probe_id = major_components[1].rstrip("\n")
                record_id, probe_step, probe_lib = probe_map.get(probe_id, (probe_id, 0, probe_id))
                # 'loc' default value is for process records
                record = {
                    "type": record_type,
                    "tid": record_tid,
                    "timestamp": int(minor_components[-1]),
                    "id": record_id,
                    "seq": 0,
                    "loc": probe_lib,
                }
                if record_type in vals.SEQUENCED_RECORDS:
                    # Sequenced records need to update their sequence number
                    record["seq"] = seq_map[record_tid][record_id]
                    seq_map[record_tid][record_id] += probe_step
                elif record_type in vals.THREAD_RECORDS:
                    # TYPE TID PID TIMESTAMP ID
                    record["pid"] = int(minor_components[2])
                elif record_type in vals.PROCESS_RECORDS:
                    # TYPE TID PID PPID TIMESTAMP ID
                    record["pid"] = int(minor_components[2])
                    record["ppid"] = int(minor_components[3])
                yield record
            # In case there is any issue with parsing, return corrupted trace record
            # We want to catch any error since parsing should be bullet-proof and should not crash
            except Exception:
                corrupted_line = line.rstrip("\n")
                WATCH_DOG.info(f"Corrupted data record on ln {cnt}: {corrupted_line}")
                yield {
                    "type": vals.RecordType.CORRUPT.value,
                    "tid": -1,
                    "timestamp": -1,
                    "id": -1,
                }
        WATCH_DOG.info(f"Parsed {cnt} records")
        metrics.add_metric("records_count", cnt)
