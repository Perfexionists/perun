"""A comprehensive difference report of baseline-target profiles.

The report includes general overview of the environment (kernel, boot info, machine specs, ...),
a flame graph grid, aggregate table of the most expensive traces, etc.

The report also supports embedding user-defined annotations within the report sections or concrete
values.
"""

from __future__ import annotations

# Standard Imports
import array
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from operator import itemgetter
from pathlib import Path
import sys
from typing import Any, Literal

# Third-Party Imports

# Perun Imports
import perun
from perun import profile as profile
from perun.logic import config
from perun.templates import factory as templates
from perun.utils import log, mapping, streams
from perun.utils.common import diff_kit, common_kit
from perun.utils.structs.common_structs import WebColorPalette
from perun.utils.structs.diff_structs import Config
from perun.view_diff import flamegraph


@dataclass
class TraceStat:
    """Statistics for single trace

    :ivar trace: list of called UID
    :ivar baseline_cost: overall cost of the traces
    :ivar target_cost: overall cost of the traces
    :ivar baseline_partial_costs: list of partial costs of the trace for baseline;
        the partial costs are the particular results for each of the pair of callee
        and caller in the trace.
    :ivar target_partial_costs: list of partial costs of the trace for target
    """

    __slots__ = [
        "trace",
        "trace_id",
        "baseline_cost",
        "target_cost",
        "baseline_partial_costs",
        "target_partial_costs",
    ]
    trace: list[str]
    trace_id: int
    baseline_cost: array.array[float]
    target_cost: array.array[float]
    baseline_partial_costs: list[array.array[float]]
    target_partial_costs: list[array.array[float]]


@dataclass
class SelectionRow:
    """Helper dataclass for displaying selection of data

    :ivar uid: uid of the selected graph
    :ivar index: index in the sorted list of data
    :ivar fresh: the state of the uid - 1) not in baseline (added in target),
        2) not in target (removed in target), or 3) possibly unchanged
    :ivar main_stat: type of the data
    :ivar baseline_abs: the absolute baseline value
    :ivar target_abs: the absolute target value
    :ivar proportional_rel_delta: the relative delta between total target and baseline value
    :ivar abs_delta: absolute change between target and baseline
    :ivar rel_delta: relative change between target and baseline
    :ivar stats: overview of all stat values
    :ivar trace_stats: a collection of stats for traces
    """

    __slots__ = [
        "uid",
        "index",
        "fresh",
        "main_stat",
        "baseline_abs",
        "target_abs",
        "proportional_rel_delta",
        "abs_delta",
        "rel_delta",
        "stats",
        "trace_stats",
    ]

    def __init__(
        self,
        uid: str,
        index: int,
        fresh: Literal["not in baseline", "not in target", "in both"],
        stats: list[tuple[int, float, float, float, float, float]],
        trace_stats: list[tuple[str, str, float, float, float, float, float, str]],
    ) -> None:
        """Initializes the selection row"""
        self.uid: str = uid
        self.index: int = index
        self.fresh: Literal["not in baseline", "not in target", "in both"] = fresh
        self.main_stat: int = stats[0][0]
        self.baseline_abs: float = common_kit.to_compact_num(stats[0][1])
        self.target_abs: float = common_kit.to_compact_num(stats[0][2])
        self.proportional_rel_delta: float = common_kit.to_compact_num(stats[0][3])
        self.abs_delta: float = common_kit.to_compact_num(stats[0][4])
        self.rel_delta: float = common_kit.to_compact_num(stats[0][5])
        # stat_type, baseline_abs, target_abs, prop_rel_delta, abs_delta, rel_delta
        self.stats: list[tuple[int, float, float, float, float, float]] = [
            (
                stat[0],
                common_kit.to_compact_num(stat[1]),
                common_kit.to_compact_num(stat[2]),
                common_kit.to_compact_num(stat[3]),
                common_kit.to_compact_num(stat[4]),
                common_kit.to_compact_num(stat[5]),
            )
            for stat in stats
        ]
        # trace, stat_t, baseline_abs, target_abs, prop_rel_delta, abs_delta, rel_delta, long_trace
        all_stats = Stats.all_stats()
        self.trace_stats: list[tuple[str, int, float, float, float, float, float, str]] = [
            (
                t[0],
                all_stats.index(t[1]),
                common_kit.to_compact_num(t[2]),
                common_kit.to_compact_num(t[3]),
                common_kit.to_compact_num(t[4]),
                common_kit.to_compact_num(t[5]),
                common_kit.to_compact_num(t[6]),
                t[7],
            )
            for t in trace_stats
        ]


class Graph:
    """Represents single sankey graph

    :ivar nodes: mapping of uids#pos to concrete sankey nodes
    :ivar uid_to_nodes: mapping of uid to list of its uid#pos, i.e. uid in different contexts
    :ivar uid_to_id: mapping of uid to unique identifiers
    :ivar stats_to_id: mapping of stats to unique identifiers
    """

    __slots__ = ["nodes", "uid_to_nodes", "uid_to_id", "stats_to_id", "uid_to_traces"]

    nodes: dict[str, Node]
    uid_to_traces: dict[str, list[list[str]]]
    uid_to_nodes: dict[str, list[Node]]
    uid_to_id: dict[str, int]
    stats_to_id: dict[str, int]

    def __init__(self):
        """Initializes empty graph"""
        self.nodes = {}
        self.uid_to_nodes = defaultdict(list)
        self.uid_to_traces = defaultdict(list)
        self.stats_to_id = {}
        self.uid_to_id = {}

    def get_node(self, node: str) -> Node:
        """For give uid#pos returns its corresponding node

        If the uid is not yet assigned unique id, we assign it.
        If the node has corresponding node created we return it.

        :param node: node in form of uid#pos
        :return: corresponding node in sankey graph
        """
        uid = node.split("#")[0]
        if uid not in self.uid_to_id:
            self.uid_to_id[uid] = len(self.uid_to_id)
        if node not in self.nodes:
            self.nodes[node] = Node(node)
            self.uid_to_nodes[uid].append(self.nodes[node])
        return self.nodes[node]

    def translate_stats(self, stats: str) -> int:
        """Translates string representation of stats to unique id

        :param stats: stats represented as string
        :return: unique id for the string
        """
        if stats not in self.stats_to_id:
            self.stats_to_id[stats] = len(self.stats_to_id)
        return self.stats_to_id[stats]

    def translate_node(self, node: str) -> str:
        """Translates the node to its unique id

        :param node: node which we are translating to id
        :return: unique identifier for the node uid
        """
        if "#" in node:
            return f"{self.uid_to_id[node.split('#')[0]]}"
        return str(self.uid_to_id[node])

    def get_caller_stats(self, src: str, tgt: str) -> Stats:
        """Returns stats for callers of the src

        :param src: source node
        :param tgt: target caller node
        :return: stats
        """
        # Create node if it does not already exist
        src_node = self.get_node(src)

        # Get link if it does not already exist
        if tgt not in src_node.callers:
            tgt_node = self.get_node(tgt)
            src_node.callers[tgt] = Link(tgt_node, Stats())

        return src_node.callers[tgt].stats

    def get_callee_stats(self, src: str, tgt: str) -> Stats:
        """Returns stats for callees of the src

        :param src: source node
        :param tgt: target callee node
        :return: stats
        """
        # Create node if it does not already exist
        src_node = self.get_node(src)

        # Get link if it does not already exist
        if tgt not in src_node.callees:
            tgt_node = self.get_node(tgt)
            src_node.callees[tgt] = Link(tgt_node, Stats())

        return src_node.callees[tgt].stats

    def to_jinja_string(self, link_type: Literal["callees", "callers"] = "callees") -> str:
        """Since jinja seems to be awfully slow with this, we render the result ourselves

        1. Target nodes of "uid#pos" are simplified to "uid",
            since you can infer pos to be pos+1 of source
        2. Stats are merged together: first half is for baseline, second half is for target

        TODO: switch callers to callees and callees to callers

        :param link_type: either callees for callees or caller for callers
        :return: string representation of the callee or caller relation
        """

        def comma_control(commas_list: list[bool], pos: int) -> str:
            """Helper function for comma control

            :param pos: position in the nesting
            :param commas_list: list of boolean flags for comma control (true = we should output)
            """
            if commas_list[pos]:
                return ","
            commas_list[pos] = True
            return ""

        output = ["{"]
        commas = [False, False, False]
        for uid, nodes in log.progress(
            self.uid_to_nodes.items(), description="Converting Nodes To Jinja"
        ):
            output.extend([comma_control(commas, 0), f"{self.translate_node(uid)}:", "{"])
            commas[1] = False
            for node in nodes:
                output.extend([comma_control(commas, 1), f"{node.get_order()}:", "{"])
                commas[2] = False
                for link in node.get_links(link_type).values():
                    assert link_type == "callers" or int(node.get_order()) + 1 == int(
                        link.target.get_order()
                    )
                    assert (
                        link_type == "callees"
                        or int(node.get_order()) == int(link.target.get_order()) + 1
                    )
                    output.extend(
                        [comma_control(commas, 2), f"{self.translate_node(link.target.uid)}:"]
                    )
                    base_and_tgt = link.stats.to_array("baseline") + link.stats.to_array("target")
                    stats = f"[{','.join(base_and_tgt)}]"
                    output.append(str(self.translate_stats(stats)))
                output.append("}")
            output.append("}")
        output.append("}")
        return "".join(output)


@dataclass
class Node:
    """Single node in sankey graph

    :ivar uid: unique identifier of the node (the label)
    :ivar callees: map of positions to edge relation for callees
    :ivar callers: map of positions to edge relation for callers
    :ivar stats: statistics for the given node
    """

    __slots__ = ["uid", "callees", "callers", "stats"]

    uid: str
    callees: dict[str, Link]
    callers: dict[str, Link]
    stats: Stats

    def __init__(self, uid: str):
        """Initializes the node"""
        self.uid = uid
        self.callees = {}
        self.callers = {}
        self.stats = Stats()

    def get_links(self, link_type: Literal["callees", "callers"]) -> dict[str, Link]:
        """Returns linkage based on given type

        :param link_type: either callees or callers
        :return: linkage of the given ty pe
        """
        if link_type == "callees":
            return self.callees
        assert link_type == "callers"
        return self.callers

    def get_order(self) -> int:
        """Gets position/order in the call traces

        :return: order/position in the call traces
        """
        return int(self.uid.split("#")[1])


@dataclass
class Link:
    """Helper dataclass for linking two nodes

    :ivar target: target of the edge
    :ivar stats: stats of the edge
    """

    __slots__ = ["stats", "target"]
    target: Node
    stats: Stats


class Stats:
    """Statistics for a given edge or node

    :ivar baseline: baseline stats
    :ivar target: target stats
    """

    __slots__ = ["baseline", "target"]
    KnownStatsSet: set[str] = set()
    SortedStats: list[str] = []

    def __init__(self) -> None:
        """Initializes the stat"""
        self.baseline: dict[str, float] = defaultdict(float)
        self.target: dict[str, float] = defaultdict(float)

    def add_stat(
        self, stat_type: Literal["baseline", "target"], stat_key: str, stat_val: int | float
    ) -> None:
        """Adds stat of given type

        :ivar stat_type: type of the stat (either baseline or target)
        :ivar stat_key: type of the metric
        :ivar stat_val: value of the metric
        """
        Stats.KnownStatsSet.add(stat_key)
        if stat_type == "baseline":
            self.baseline[stat_key] += stat_val
        else:
            self.target[stat_key] += stat_val

    @staticmethod
    def all_stats() -> list[str]:
        """Returns sorted list of stats"""
        if not Stats.SortedStats:
            Stats.SortedStats = sorted(list(Stats.KnownStatsSet))
        return Stats.SortedStats

    def to_array(self, stat_type: Literal["baseline", "target"]) -> list[str]:
        """Converts stats to single compact array"""
        stats = self.baseline if stat_type == "baseline" else self.target
        return [
            common_kit.compact_convert_num_to_str(stats.get(stat, 0), 2)
            for stat in Stats.all_stats()
        ]


def process_max(
    counts: dict[str, float],
    resource: dict[str, Any],
) -> None:
    """Accumulates resources

    :param counts: counts of resources
    :param resource: consumed resources
    """
    for key in resource:
        amount = common_kit.try_convert(resource[key], [float])
        if amount is None or key in ("time", "command", "uid"):
            continue
        readable_key = mapping.get_readable_key(key)
        counts[readable_key] += amount


def process_node(
    graph: Graph,
    profile_type: Literal["baseline", "target"],
    resource: dict[str, Any],
    uid: str,
) -> None:
    """Processes single edge with given resources

    :param graph: sankey graph
    :param profile_type: type of the profile
    :param resource: consumed resources
    :param uid: the node uid
    """
    node = graph.get_node(uid)
    for key in resource:
        amount = common_kit.try_convert(resource[key], [float])
        if amount is None or key in ("time", "command", "uid"):
            continue
        readable_key = mapping.get_readable_key(key)
        node.stats.add_stat(profile_type, readable_key, amount)


def process_edge(
    graph: Graph,
    profile_type: Literal["baseline", "target"],
    resource: dict[str, Any],
    src: str,
    tgt: str,
) -> None:
    """Processes single edge with given resources

    :param graph: sankey graph
    :param profile_type: type of the profile
    :param resource: consumed resources
    :param src: callee
    :param tgt: caller
    """
    src_stats = graph.get_callee_stats(src, tgt)
    tgt_stats = graph.get_caller_stats(tgt, src)
    for key in resource:
        amount = common_kit.try_convert(resource[key], [float])
        if amount is None or key in ("time", "command", "uid"):
            continue
        readable_key = mapping.get_readable_key(key)
        src_stats.add_stat(profile_type, readable_key, amount)
        tgt_stats.add_stat(profile_type, readable_key, amount)


def process_traces(
    prof: profile.Profile, profile_type: Literal["baseline", "target"], graph: Graph
) -> None:
    """Processes all traces in the profile

    Iterates through all traces and creates edges for each pair of source and target.

    :param prof: input profile
    :param profile_type: type of the profile
    :param graph: sankey graph
    """
    max_trace = 0
    max_samples: dict[str, float] = defaultdict(float)
    for _, resource in log.progress(prof.all_resources(), description="Processing Traces"):
        full_trace = [profile.to_uid(t, Config().minimize) for t in resource.get("trace", {})]
        full_trace.append(profile.to_uid(resource["uid"], Config().minimize))
        trace_len = len(full_trace)
        max_trace = max(max_trace, trace_len)
        # Process edge stats
        if trace_len > 1:
            if Config().trace_is_inclusive:
                for i in range(0, trace_len - 1):
                    src = f"{full_trace[i]}#{i}"
                    tgt = f"{full_trace[i + 1]}#{i + 1}"
                    process_edge(graph, profile_type, resource, src, tgt)
            else:
                src = f"{full_trace[-2]}#{trace_len - 2}"
                tgt = f"{full_trace[-1]}#{trace_len - 1}"
                process_edge(graph, profile_type, resource, src, tgt)
            for uid in full_trace:
                graph.uid_to_traces[uid].append(full_trace)
        # Process node stats TODO: Return to this, as this was fixed very quickly
        if Config().trace_is_inclusive:
            process_max(max_samples, resource)
            for i in range(0, trace_len):
                src = f"{full_trace[i]}#{i}"
                process_node(graph, profile_type, resource, src)
        else:
            tgt = f"{full_trace[-1]}#{trace_len - 1}"
            process_node(graph, profile_type, resource, tgt)

    saved_maxima = Config().max_per_resource
    for key in max_samples.keys():
        saved_maxima[key] = max(saved_maxima[key], max_samples[key])
        # TODO: This is a bit of a hack since the key already contains the unit
        name, unit = key.split("[", maxsplit=1)
        name.rstrip()
        unit = unit.rsplit("]", maxsplit=1)[0]
        Config().profile_stats[profile_type].append(
            profile.ProfileStat(
                f"Overall {name}",
                profile.ProfileStatComparison.LOWER,
                unit,
                description=f"The overall value of the {name} for the root value",
                value=[int(max_samples[key])],
            )
        )
    Config().profile_stats[profile_type].append(
        profile.ProfileStat(
            "Maximum Trace Length",
            profile.ProfileStatComparison.LOWER,
            "#",
            description="Maximum length of the trace in the profile",
            value=[max_trace],
        )
    )
    Config().max_seen_trace = max(max_trace, Config().max_seen_trace)


def generate_trace_stats(graph: Graph) -> dict[str, list[TraceStat]]:
    """Generates trace stats

    :param graph: sankey graph
    :return: trace stats
    """
    trace_stats = defaultdict(list)
    log.minor_info("Generating stats for traces")
    trace_cache: dict[str, TraceStat] = {}
    trace_counter: int = 0
    for uid, traces in log.progress(
        graph.uid_to_traces.items(), description="Generating Trace Stats"
    ):
        processed = set()
        for trace in [trace for trace in traces if len(trace) > 1]:
            key = ",".join(trace)
            if key not in processed:
                # High memory consumption
                processed.add(key)
                if key in trace_cache:
                    trace_stats[uid].append(trace_cache[key])
                    continue
                trace_len = len(trace)
                stat_len = len(Stats.all_stats())
                base_sum: array.array[float] = array.array(
                    "d", [sys.float_info.max if Config().trace_is_inclusive else 0.0] * stat_len
                )
                base_partial: list[array.array[float]] = [
                    array.array("d", [0.0] * (trace_len - 1)) for _ in range(0, stat_len)
                ]
                tgt_sum: array.array[float] = array.array(
                    "d", [sys.float_info.max if Config().trace_is_inclusive else 0.0] * stat_len
                )
                tgt_partial: list[array.array[float]] = [
                    array.array("d", [0.0] * (trace_len - 1)) for _ in range(0, stat_len)
                ]
                for i in range(0, trace_len - 1):
                    src, tgt = f"{trace[i]}#{i}", f"{trace[i + 1]}#{i + 1}"
                    node = graph.get_node(src)
                    if tgt in node.callees:
                        stats = node.callees[tgt].stats
                        for j, stat in enumerate(Stats.all_stats()):
                            base_stat, tgt_stat = stats.baseline[stat], stats.target[stat]
                            base_partial[j][i] += base_stat
                            tgt_partial[j][i] += tgt_stat
                            if Config().trace_is_inclusive:
                                base_sum[j] = common_kit.try_min(base_sum[j], base_stat)
                                tgt_sum[j] = common_kit.try_min(tgt_sum[j], tgt_stat)
                            else:
                                base_sum[j] += base_stat
                                tgt_sum[j] += tgt_stat

                trace_stat = TraceStat(
                    trace, trace_counter, base_sum, tgt_sum, base_partial, tgt_partial
                )
                trace_counter += 1
                trace_cache[key] = trace_stat
                trace_stats[uid].append(trace_stat)
    return trace_stats


def _get_baseline_target_total() -> tuple[list[float], list[float]]:
    """A helper function to obtain baseline target total values for all stats.

    :return: collections of baseline and target total values
    """
    # TODO: Nasty, but currently the only reasonable way to access the maxima.
    return [
        float(stat.value[0])
        for stat in Config().profile_stats["baseline"]
        if stat.name.startswith("Overall")
    ], [
        float(stat.value[0])
        for stat in Config().profile_stats["target"]
        if stat.name.startswith("Overall")
    ]


def _to_percentage(value: float) -> float:
    """Transforms a value to a percentage and round it to 2 decimal places.

    :param value: the value to transform and round

    :return: the transformed value
    """
    return round(100 * value, 2)


def generate_selection(graph: Graph, trace_stats: dict[str, list[TraceStat]]) -> list[SelectionRow]:
    """Generates selection table

    :param graph: sankey graph
    :param trace_stats: stats for traces for each uid
    :return: list of selection rows for table
    """
    selection = []
    log.minor_info("Generating selection table")
    trace_stat_cache: dict[str, tuple[str, str, float, float, float, float, float, str]] = {}
    stat_len = len(Stats.all_stats())
    baseline_max, target_max = _get_baseline_target_total()
    for uid, nodes in log.progress(
        graph.uid_to_nodes.items(), description="Generating Selection Rows"
    ):
        baseline_overall: array.array[float] = array.array("d", [0.0] * stat_len)
        target_overall: array.array[float] = array.array("d", [0.0] * stat_len)
        # StatID, baseline abs, target abs, proportional delta, abs delta, rel delta
        stats: list[tuple[int, float, float, float, float, float]] = []
        for node in nodes:
            for i, known_stat in enumerate(Stats.all_stats()):
                baseline_overall[i] += node.stats.baseline[known_stat]
                target_overall[i] += node.stats.target[known_stat]
        for i in range(0, stat_len):
            baseline, target = baseline_overall[i], target_overall[i]
            prop_diff = _to_percentage(target / target_max[i] - baseline / baseline_max[i])
            abs_diff = target - baseline
            try:
                rel_diff = _to_percentage(abs_diff / max(baseline, target))
            except ZeroDivisionError:
                # Skip this record, both baseline and target are 0
                continue
            stats.append((i, baseline, target, prop_diff, abs_diff, rel_diff))
        stats = sorted(stats, key=itemgetter(3))

        if stats:
            state: Literal["not in baseline", "not in target", "in both"] = "in both"
            if all(val == 0 or val == 0.0 for val in baseline_overall):
                state = "not in baseline"
            elif all(val == 0 or val == 0.0 for val in target_overall):
                state = "not in target"

            # Prepare trace stats
            long_trace_stats = extract_stats_from_trace(graph, trace_stats[uid], trace_stat_cache)
            selection.append(
                SelectionRow(uid, graph.uid_to_id[uid], state, stats, long_trace_stats)
            )
    return selection


def extract_stats_from_trace(
    graph: Graph,
    uid_stats: list[TraceStat],
    cache: dict[str, tuple[str, str, float, float, float, float, float, str]],
) -> list[tuple[str, str, float, float, float, float, float, str]]:
    """Extracts stats from trace

    :param graph: sankey graph
    :param uid_stats: stats for each uid in the graph
    :param cache: helper cache for reducing the statistics
    """
    uid_trace_stats: list[tuple[str, str, float, float, float, float, float, str]] = []
    top_n_limit, sort_by_key, relative_thresh, threshold_idx = (
        Config().top_n_traces,
        4,
        Config().relative_threshold,
        6,
    )
    baseline_max, target_max = _get_baseline_target_total()
    for trace in uid_stats:
        # Trace is in form of [short_trace, stat_type, baseline abs, target abs, proportional delta,
        # abs delta, rel delta, long_trace]
        for i, stat in enumerate(Stats.all_stats()):
            key = f"{trace.trace_id}#{stat}"
            if key not in cache:
                target_cost, baseline_cost = trace.target_cost[i], trace.baseline_cost[i]
                abs_amount = target_cost - baseline_cost
                try:
                    rel_amount = _to_percentage(abs_amount / max(baseline_cost, target_cost))
                except ZeroDivisionError:
                    continue
                prop_diff = _to_percentage(
                    target_cost / target_max[i] - baseline_cost / baseline_max[i]
                )

                short_id = f"{graph.uid_to_id[trace.trace[0]]};{graph.uid_to_id[trace.trace[-1]]}"
                long_trace = ";".join([f"{graph.uid_to_id[t]}" for t in trace.trace])
                long_baseline_stats = ";".join(
                    common_kit.compact_convert_list_to_str(trace.baseline_partial_costs[i])
                )
                long_target_stats = ";".join(
                    common_kit.compact_convert_list_to_str(trace.target_partial_costs[i])
                )
                long_data = f"{long_trace}#{long_baseline_stats}#{long_target_stats}"
                cache[key] = (
                    short_id,
                    stat,
                    baseline_cost,
                    target_cost,
                    prop_diff,
                    abs_amount,
                    rel_amount,
                    long_data,
                )
            if float(cache[key][threshold_idx]) >= relative_thresh:
                common_kit.add_to_sorted(
                    uid_trace_stats, cache[key], itemgetter(sort_by_key), top_n_limit
                )
    return uid_trace_stats


def compose_chatbot_contexts(sources: tuple[str, ...]) -> str:
    """Compose the additional chatbot prompt context from possibly multiple sources.

    :param sources: sources of the prompt context; may be either strings or a file paths.
    :return: the resulting prompt context string.
    """
    context_str: str = ""
    for source in sources:
        if source.endswith(".prompt"):
            # The context is stored in a file, attempt to open and read it.
            with streams.safely_open_and_log(Path(source), "r", fatal_fail=False) as handle:
                if handle is not None:
                    context_str += f"\n{handle.read()}"
        else:
            context_str += f"\n{source}"
    return context_str + "\n"


def generate_report_from_native(
    lhs_profile: profile.Profile, rhs_profile: profile.Profile, **kwargs: Any
) -> None:
    """Generates differences of two profiles as sankey diagram

    :param lhs_profile: baseline profile
    :param rhs_profile: target profile
    :param kwargs: additional arguments
    """
    fg_forward_kwargs = {
        arg.replace("flamegraph_", ""): val
        for arg, val in kwargs.items()
        if arg.startswith("flamegraph_")
    }
    # FIXME: temporary solution before refactoring to FlameGraphSettings.
    del fg_forward_kwargs["parallelize"]

    # We automatically set the value of True for kperf, which samples
    Config().minimize = kwargs.get("minimize", False)
    Config().top_n_traces = kwargs.get("top_n", Config().DefaultTopN)
    Config().relative_threshold = kwargs.get(
        "filter_by_relative", Config().DefaultRelativeThreshold
    )
    if lhs_profile.get("collector_info", {}).get("name") == "kperf":
        Config().trace_is_inclusive = True
    else:
        Config().trace_is_inclusive = kwargs.get("trace_is_inclusive", False)

    graph = Graph()

    process_traces(lhs_profile, "baseline", graph)
    process_traces(rhs_profile, "target", graph)
    lhs_stats = list(lhs_profile.all_stats())
    rhs_stats = list(rhs_profile.all_stats())

    trace_stats = generate_trace_stats(graph)
    selection_table = generate_selection(graph, trace_stats)
    flamegraphs, lhs_fg_stats, rhs_fg_stats = flamegraph.generate_flamegraphs(
        lhs_profile,
        rhs_profile,
        Stats.all_stats(),
        skip_diff=False,
        minimize=Config().minimize,
        squash_unknown=not kwargs.get("no_squash_unknown", False),
        **fg_forward_kwargs,
    )
    lhs_fg_diff_stats, rhs_fg_diff_stats = diff_kit.generate_diff_of_stats(
        flamegraph.process_flamegraph_stats(lhs_fg_stats),
        flamegraph.process_flamegraph_stats(rhs_fg_stats),
    )

    lhs_header, rhs_header = diff_kit.generate_diff_of_headers(
        diff_kit.generate_specification(lhs_profile), diff_kit.generate_specification(rhs_profile)
    )
    lhs_vulnerabilities, rhs_vulnerabilities = diff_kit.generate_diff_of_headers(
        diff_kit.generate_vulnerabilities(lhs_profile),
        diff_kit.generate_vulnerabilities(rhs_profile),
    )
    lhs_diff_stats, rhs_diff_stats = diff_kit.generate_diff_of_stats(lhs_stats, rhs_stats)
    lhs_meta, rhs_meta = diff_kit.generate_diff_of_headers(
        lhs_profile.all_metadata(), rhs_profile.all_metadata()
    )

    # Process user-defined chatbot prompt context, if provided.
    prompt_ctx = ""
    if kwargs["chatbot_url"] is not None:
        prompt_ctx_sources: tuple[str, ...] | None = kwargs.get("chatbot_prompt_context", None)
        if prompt_ctx_sources is not None:
            log.minor_info("Processing chatbot prompt context")
            prompt_ctx = compose_chatbot_contexts(prompt_ctx_sources)

    template = templates.get_template("diff_views/report.html.jinja2")
    content = template.render(
        title="Perun Report - Profiles Comparison",
        perun_version=perun.__version__,
        timestamp=datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M:%S") + " UTC",
        chatbot=kwargs["chatbot_url"],
        chatbot_prompt_context=prompt_ctx,
        lhs_tag="Baseline (base)",
        lhs_header=lhs_header,
        lhs_vulnerabilities=lhs_vulnerabilities,
        lhs_user_stats=lhs_diff_stats,
        lhs_fg_stats=lhs_fg_diff_stats,
        lhs_metadata=lhs_meta,
        rhs_tag="Target (tgt)",
        rhs_header=rhs_header,
        rhs_vulnerabilities=rhs_vulnerabilities,
        rhs_user_stats=rhs_diff_stats,
        rhs_fg_stats=rhs_fg_diff_stats,
        rhs_metadata=rhs_meta,
        palette=WebColorPalette,
        callee_graph=graph.to_jinja_string("callees"),
        caller_graph=graph.to_jinja_string("callers"),
        stat_list=Stats.all_stats(),
        units=[mapping.get_unit(s) for s in Stats.all_stats()],
        stats="["
        + ",".join(
            list(map(itemgetter(0), sorted(list(graph.stats_to_id.items()), key=itemgetter(1))))
        )
        + "]",
        nodes=map(itemgetter(0), sorted(list(graph.uid_to_id.items()), key=itemgetter(1))),
        node_map=[
            sorted([node.get_order() for node in nodes])
            for nodes in map(
                itemgetter(1),
                sorted(list(graph.uid_to_nodes.items()), key=lambda x: graph.uid_to_id[x[0]]),
            )
        ],
        flamegraphs=flamegraphs,
        selection_table=selection_table,
        offline=config.lookup_key_recursively("showdiff.offline", False),
        height=Config().max_seen_trace * Config().DefaultHeightCoefficient + 200,
        container_height=Config().max_seen_trace * Config().DefaultHeightCoefficient + 200,
        notes_enabled=True,
        links=list(kwargs.get("link", [])),
        default_theme=kwargs.get("default_theme", "light"),
    )
    log.minor_success("HTML template", "rendered")
    output_file = diff_kit.save_diff_view(
        kwargs.get("output_path"), content, "report", lhs_profile, rhs_profile
    )
    log.minor_status("Output saved", log.path_style(output_file))
