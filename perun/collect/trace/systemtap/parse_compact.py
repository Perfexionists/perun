""" Module for parsing and transforming the raw performance records from trace collector
(systemtap engine) into a perun profile.
"""

import os
import collections

import perun.utils.metrics as metrics
import perun.collect.optimizations.resources.manager as resources

from perun.collect.trace.watchdog import WATCH_DOG
from perun.collect.trace.values import RecordType
from perun.collect.optimizations.call_graph import CallGraphResource


class ThreadContext:
    """ Class that keeps track of function call stack, USDT hit stack, function call sequence
    map and bottom indicator per each active thread.

    :ivar list func_stack: keeps track of the function call stack
    :ivar dict usdt_stack: stores stack of USDT probe hits for each probe
    :ivar dict seq_map: tracks sequence number for each probe that identifies the order of records
    :ivar bool bottom_flag: flag used to identify records that have no more callees
    """
    def __init__(self):
        self.func_stack = []
        self.usdt_stack = collections.defaultdict(list)
        self.seq_map = collections.defaultdict(int)
        self.bottom_flag = False


class TransformContext:
    """ Class that keeps track of the context information during the raw data transformation.

    :ivar bool verbose_trace: switches between verbose / compact trace output
    :ivar str binary: path of the profiled binary file
    :ivar str workload: the workload specification of the current run
    :ivar Probes probes: the probes specification
    :ivar set timestamp_set: the set of encountered timestamps, used to detect duplicities in data
    :ivar ThreadContext per_thread: per-thread context for function / usdt stacks, sequence maps etc
    :ivar dict bottom: summary of total elapsed time per bottom records per thread
    :ivar dict id_map: mapping between probe ID (name) and probe names
    :ivar dict step_map: probe -> sampling value mapping
    """
    def __init__(self, probes, binary, verbose_trace, workload):
        """
        :param Probes probes: the probes specification
        :param str binary: path of the profiled binary file
        :param bool verbose_trace: switches between verbose / compact trace output
        :param str workload: the workload specification of the current run
        """
        self.verbose_trace = verbose_trace
        self.binary = binary
        self.workload = workload
        self.probes = probes
        self.timestamp_set = set()
        self.per_thread = collections.defaultdict(ThreadContext)
        # Thread -> function -> total elapsed time
        # Not included in 'per_thread' since we want to keep the values even after threads terminate
        self.bottom = collections.defaultdict(lambda: collections.defaultdict(int))

        # ID Map is used to map probe ID -> function name in non-verbose mode
        # and function name -> function name in verbose mode (basically a no-op)
        dict_key = 'name' if self.verbose_trace else 'id'
        self.id_map = {
            str(probe[dict_key]): probe['name']
            for probe in list(self.probes.func.values()) + list(self.probes.usdt.values())
        }
        # Step Map keeps track of the sampling value per each function
        # Used to compute the sequence property
        self.step_map = {
            str(probe[dict_key]): probe['sample']
            for probe in list(self.probes.func.values()) + list(self.probes.usdt.values())
        }
        # TODO: temporary, solve dynamic call graph properly
        self.dyn_cg = {probe['name']: set() for probe in self.probes.func.values()}


def trace_to_profile(data_file, config, probes, **_):
    """Transforms the collection output into the performance resources. The
    collected time data are paired and provided as resources dictionaries.

    :param str data_file: name of the collection output file
    :param Configuration config: the configuration object
    :param Probes probes: the Probes object

    :return iterable: generator object that produces dictionaries representing the resources
    """
    # Initialize just in case the trace doesn't have begin sentinel
    ctx = TransformContext(probes, config.binary, config.verbose_trace, config.executable.workload)
    handlers = _record_handlers(config.generate_dynamic_cg)
    with open(data_file, 'r') as trace:
        cnt, line = 0, ''
        record = None
        try:
            # Process the raw data trace line by line
            for cnt, line in enumerate(trace):
                # Some records might be correctly parsed even though they are corrupted,
                # E.g., correct record structure with malformed probe id - thus try/except is needed
                # --- Performance Critical --- do not use the SuppressedExceptions context manager
                try:
                    # Parse the trace output line
                    record = parse_record(line)
                    # Initial checks that this is not a duplicate record
                    if record['timestamp'] in ctx.timestamp_set:
                        if record['type'] != RecordType.Corrupt:
                            WATCH_DOG.debug('Duplicate timestamp detected: {} {}'
                                            .format(record['timestamp'], record['id']))
                        continue
                    ctx.timestamp_set.add(record['timestamp'])
                    # Invoke the correct handler based on the record type and return the
                    # resulting resource, if any
                    resource = handlers[record['type']](record, ctx)
                    if resource:
                        yield resource
                except (KeyError, IndexError):
                    continue
            WATCH_DOG.info('Processed {} records'.format(cnt))
            # Add the computed hotspot coverage to the tracked metric
            metrics.add_metric('coverages', {tid: {
                'hotspot_coverage_abs': sum(val for val in bottom.values()),
                'hotspot_coverage_count': len([name for name in bottom.keys()])
            } for tid, bottom in ctx.bottom.items()})
            # TODO: temporary
            _build_dynamic_cg(config, ctx)
        except Exception:
            WATCH_DOG.info('Error while parsing the raw trace output')
            # Log the status in case of unhandled exception
            WATCH_DOG.log_trace_stack(
                line, cnt, ctx, record['tid'] if record is not None else -1
            )
            raise


def _build_dynamic_cg(config, ctx):
    """ Builds the dynamic CG and stores it into the stats directory.
    The dynamic CG still uses the statically obtained Call Graph to combine with the dynamic one
    in order to retrieve more general Call Graph structure.

    :param Configuration config: the configuration object
    :param TransformContext ctx: the parsing context which contains caller-callee relationships
    """
    if config.generate_dynamic_cg:
        cg_stats_name = config.get_stats_name('call_graph')
        # Extract the static Call Graph using Angr
        _cg = resources.extract(
            resources.Resources.CallGraphAngr, stats_name=cg_stats_name,
            binary=config.get_target(), cache=False, libs=config.libs,
            restricted_search=False
        )
        # Build the combined Call Graph using the static and dynamic call graphs
        call_graph = CallGraphResource().from_dyn(
            ctx.dyn_cg, _cg, config.get_functions().keys()
        )

        # Store the new call graph version
        resources.store(
            resources.Resources.PerunCallGraph, stats_name=cg_stats_name,
            call_graph=call_graph, cache=False
        )


def _record_handlers(cg_reconstruction):
    """ Mapping of a raw data record type to its corresponding function handler.

    :param bool cg_reconstruction: use different handler for function probes that also reconstructs
                                   the dynamic call graph

    :return dict: the mapping dictionary
    """
    func_begin = _record_func_begin if not cg_reconstruction else _record_func_begin_reconstruction
    return {
        RecordType.SentinelBegin.value: _record_sentinel_begin,
        RecordType.SentinelEnd.value: _record_sentinel_end,
        RecordType.FuncBegin.value: func_begin,
        RecordType.FuncEnd.value: _record_func_end,
        RecordType.USDTBegin.value: _record_usdt_begin,
        RecordType.USDTEnd.value: _record_usdt_end,
        RecordType.USDTSingle.value: _record_usdt_single,
        RecordType.Corrupt.value: _record_corrupt
    }


def _record_corrupt(_, __):
    """ Corrupted records are simply discarded.

    :return dict: empty dictionary
    """
    return {}


def _record_sentinel_begin(_, __):
    """ Handler for begin sentinel probe that is a no-op.

    :return dict: empty dictionary
    """
    return {}


def _record_sentinel_end(record, ctx):
    """ Handler for the terminating sentinel that checks if 'main' probe was properly terminated.

    :param dict record: the parsed raw data record
    :param TransformContext ctx: the parsing context object

    :return dict: empty dictionary
    """
    # The .begin and .end probes are sometimes triggered by other spawned processes, filter them
    resource = {}
    if record['id'] == os.path.basename(ctx.binary):
        # TODO: change this to actually track END - BEGIN duration and use it as a backup main
        # Make sure that the 'main' record is terminated if abrupt termination happens
        for func in ctx.per_thread[record['tid']].func_stack:
            # There is still an unprocessed main record
            if ctx.id_map[func['id']] == 'main':
                resource = _build_resource(func, record, ctx.id_map[func['id']], ctx)
                break
        metrics.add_metric('abrupt_termination_' + str(record['tid']), bool(resource))
    del ctx.per_thread[record['tid']]
    return resource


def _record_func_begin(record, ctx):
    """ Handler for the entry function probes.

    :param dict record: the parsed raw data record
    :param TransformContext ctx: the parsing context object

    :return dict: empty dictionary
    """
    # Increase the sequence counter
    _inc_sequence_number(record, ctx)
    ctx.per_thread[record['tid']].bottom_flag = True
    # Add the record to the trace stack
    ctx.per_thread[record['tid']].func_stack.append(record)
    return {}


def _record_func_begin_reconstruction(record, ctx):
    """ Handler for the entry function probes that also reconstructs the dynamic call graph.

    :param dict record: the parsed raw data record
    :param TransformContext ctx: the parsing context object

    :return dict: empty dictionary
    """
    record_tid = record['tid']
    # Increase the sequence counter
    _inc_sequence_number(record, ctx)
    ctx.per_thread[record_tid].bottom_flag = True
    # Update the dynamic call graph structure
    try:
        caller_record = ctx.per_thread[record_tid].func_stack[-1]
        caller_uid = ctx.id_map[caller_record['id']]
        callee_uid = ctx.id_map[record['id']]
        ctx.dyn_cg[caller_uid].add(callee_uid)
    except IndexError:
        pass
    # Add the record to the trace stack
    ctx.per_thread[record_tid].func_stack.append(record)
    return {}


def _record_func_end(record, ctx):
    """ Handler for the exit function probes.

    :param dict record: the parsed raw data record
    :param TransformContext ctx: the parsing context object

    :return dict: profile resource dictionary or empty dictionary if matching failed
    """
    record_tid = record['tid']
    stack = ctx.per_thread[record_tid].func_stack
    matching_record = {}
    # In most cases, the record matches the top record in the stack
    if stack and record['id'] == stack[-1]['id'] and record['timestamp'] > stack[-1]['timestamp']:
        matching_record = stack.pop()
    # However, if not, then traverse the whole stack and attempt to find matching record
    else:
        for idx, stack_item in enumerate(reversed(stack)):
            if record['id'] == stack_item['id'] and record['timestamp'] > stack_item['timestamp']:
                stack[:] = stack[:len(stack) - idx]
                matching_record = stack.pop()
                break
    if matching_record:
        # Compute the bottom time
        uid = ctx.id_map[record['id']]
        if ctx.per_thread[record_tid].bottom_flag:
            ctx.bottom[record_tid][uid] += (record['timestamp'] - matching_record['timestamp'])
        matching_record = _build_resource(matching_record, record, uid, ctx)
        ctx.per_thread[record_tid].bottom_flag = False
    return matching_record


def _record_usdt_single(record, ctx):
    """ Handler for the single USDT probes (not paired).

    :param dict record: the parsed raw data record
    :param TransformContext ctx: the parsing context object

    :return dict: profile resource dictionary or empty dictionary if no resource could be created
    """
    _inc_sequence_number(record, ctx)
    stack = ctx.per_thread[record['tid']].usdt_stack[record['id']]
    # If this is the first record of this USDT probe, add it to the stack
    if not stack:
        stack.append(record)
        return {}
    # Pair with itself and
    # add the record into the trace stack to correctly measure time between each two hits
    matching_record = stack.pop()
    stack.append(record)
    return _build_resource(
        matching_record, record,
        ctx.id_map[matching_record['id']] + '#' + ctx.id_map[record['id']], ctx
    )


def _record_usdt_begin(record, ctx):
    """ Handler for the entry USDT probes (paired).

    :param dict record: the parsed raw data record
    :param TransformContext ctx: the parsing context object

    :return dict: empty dictionary
    """
    # Increment the sequence counter and add the record to the stack
    _inc_sequence_number(record, ctx)
    ctx.per_thread[record['tid']].usdt_stack[record['id']].append(record)
    return {}


def _record_usdt_end(record, ctx):
    """ Handler for the exit USDT probes (paired).

    :param dict record: the parsed raw data record
    :param TransformContext ctx: the parsing context object

    :return dict: profile resource dictionary
    """
    # Obtain the corresponding probe pair and matching record
    pair = ctx.probes.usdt_reversed[record['id']]
    matching_record = ctx.per_thread[record['tid']].usdt_stack[pair].pop()
    # Create the resource
    return _build_resource(
        matching_record, record,
        ctx.id_map[matching_record['id']] + '#' + ctx.id_map[record['id']], ctx
    )


def _inc_sequence_number(record, ctx):
    """ Attaches a sequence number to the record and increments the counter for the given probe ID.

    :param dict record: the parsed raw data record
    :param TransformContext ctx: the parsing context object
    """
    seq_map = ctx.per_thread[record['tid']].seq_map
    record['seq'] = seq_map[record['id']]
    seq_map[record['id']] += ctx.step_map[record['id']]


def _build_resource(record_entry, record_exit, uid, ctx):
    """ Creates the profile resource from the entry and exit records.

    :param dict record_entry: the entry raw data record
    :param dict record_exit: the exit raw data record
    :param str uid: the resource UID
    :param TransformContext ctx: the parsing context object

    :return dict: the resulting profile resource
    """
    return {
        'amount': record_exit['timestamp'] - record_entry['timestamp'],
        'timestamp': record_entry['timestamp'],
        'call-order': record_entry['seq'],
        'uid': uid,
        'thread': record_entry['tid'],
        'type': 'mixed',
        'subtype': 'time delta',
        'workload': ctx.workload
    }


def parse_record(line):
    """ Parse the raw data line into a dictionary of components.

    :param str line: a line from the raw data file

    :return dict: the parsed record components
    """
    try:
        # Split the line into 'type' 'tid' 'timestamp' 'probe id'
        components = line.split()
        return {
            'type': int(components[0]),
            'tid': int(components[1]),
            'timestamp': int(components[2]),
            'id': components[3]
        }
    # In case there is any issue with parsing, return corrupted trace record
    # We truly want to catch any error since parsing should be bullet-proof and should not crash
    except Exception:
        WATCH_DOG.info("Corrupted data record: '{}'".format(line.rstrip('\n')))
        return {
            'type': RecordType.Corrupt.value,
            'tid': -1,
            'timestamp': -1,
            'id': -1
        }
