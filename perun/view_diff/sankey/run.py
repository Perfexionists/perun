"""Sankey difference of the profiles

The difference is in form of:

cmd       | cmd
workload  | workload
collector | kernel

| ---|          |======|
     |-----|====
|---|          |------|

"""

from __future__ import annotations

# Standard Imports
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

# Third-Party Imports
import click

# Perun Imports
import perun
from perun.templates import factory as templates
from perun.profile import convert
from perun.profile.factory import Profile
from perun.utils import log
from perun.utils.common import diff_kit, common_kit
from perun.utils.structs.common_structs import WebColorPalette


@dataclass
class Config:
    __slots__ = ["minimize", "source_key", "inclusive_traces", "edge_threshold"]
    minimize: bool
    source_key: str
    inclusive_traces: bool
    edge_threshold: float


@dataclass
class SuccessorStats:
    """Represents statistic about successors between sankey nodes

    :ivar baseline: stats for baseline profile
    :ivar target: stats for target profile
    """

    __slots__ = ["baseline", "target"]

    baseline: float
    target: float


@dataclass
class SankeyNode:
    """Single node in the sankey graph

    :ivar uid: string representation of the uid/node
    :ivar tag: uid joined with order in the traces
    :ivar trace: trace to the node
    :ivar id: integer representation of the node in the graph
    :ivar succs: list of successor sankey nodes together with the stats
    :ivar preds: list of predecessor sankey nodes together with the stats
    """

    __slots__ = ["uid", "id", "succs", "preds", "tag", "trace"]

    uid: str
    tag: str
    id: int
    trace: list[str]
    succs: dict[int, SuccessorStats]
    preds: dict[int, SuccessorStats]


@dataclass
class SelectionRow:
    """Helper dataclass for displaying selection of data

    :ivar uid: uid of the selected graph
    :ivar index: index in the sorted list of data
    :ivar abs_amount: absolute change in the units
    :ivar rel_amount: relative change in the units
    """

    __slots__ = ["uid", "index", "abs_amount", "rel_amount"]
    uid: str
    index: int
    abs_amount: float
    rel_amount: float


@dataclass
class Linkage:
    """Representation of linkage in the sankey graph

    :ivar source: sources of the edges
    :ivar target: targets of the edges
    :ivar value: values of edges
    :ivar color: colours of edges
    """

    __slots__ = ["source", "target", "value", "color"]
    source: list[int]
    target: list[int]
    value: list[float]
    color: list[str]

    def __init__(self):
        self.source = []
        self.target = []
        self.value = []
        self.color = []


@dataclass
class SankeyGraph:
    """Representation of sankey graph data consisting of links between nodes

    :ivar uid: function for which they sankey graph is corresponding
    :ivar label: list of labels for each node in the graph
    :ivar customdata: list of uids for unique identification of the node (different from label) and traces
    :ivar width: the size of the longest trace
    :ivar height: the maximal number of paralel traces
    :ivar min: minimal number of amount on edges
    :ivar max: maximal amount on edges
    """

    __slots__ = [
        "diff",
        "height",
        "label",
        "linkage",
        "max",
        "min",
        "node_colors",
        "customdata",
        "sum",
        "uid",
        "width",
    ]
    uid: str
    label: list[str]
    customdata: list[list[str]]
    node_colors: list[str]
    linkage: dict[Literal["split", "merged"], Linkage]
    width: int
    height: int
    min: float
    max: float
    diff: float
    sum: float

    def __init__(self, uid: str):
        """Initializes the graph"""
        self.uid = uid
        self.label = []
        self.customdata = []
        self.node_colors = []
        self.linkage = {"split": Linkage(), "merged": Linkage()}
        self.width = 0
        self.height = 0
        self.min = -1
        self.max = 0
        self.diff = 0
        self.sum = 0


def get_sankey_point(sankey_points: dict[str, SankeyNode], key: str) -> SankeyNode:
    """Retrieves the sankey node from the list of points.

    If the point does not exist, then it is created

    :param sankey_points: map of keys to sankey nodes
    :param key: key identifying sankey node
    :return: sankey node corresponding to given key
    """
    if key not in sankey_points:
        uid = key.split("#")[0]
        sankey_points[key] = SankeyNode(uid, key, len(sankey_points), [uid], {}, {})
    return sankey_points[key]


def process_single_edge(
    sankey_map: dict[str, dict[str, SankeyNode]],
    key: str,
    profile_type: Literal["baseline", "target"],
    src: str,
    tgt: str,
    amount: float,
) -> None:
    """Creates and edge in each of the sankey graph along the trace

    Increases the valuation of appropriate statistic

    :param sankey_map: list of sankey points corresponding to each uid
    :param key: key where sankey points are
    :param profile_type: identification of either baseline or target
    :param src: source id of the edge
    :param tgt: target id of the edge
    :param amount: valuation of the edge
    """
    sankey_points = sankey_map[key]
    src_point = get_sankey_point(sankey_points, src)
    tgt_point = get_sankey_point(sankey_points, tgt)
    if tgt_point.id not in src_point.succs:
        src_point.succs[tgt_point.id] = SuccessorStats(0.0, 0.0)
    if src_point.id not in tgt_point.preds:
        tgt_point.preds[src_point.id] = SuccessorStats(0.0, 0.0)
    if profile_type == "baseline":
        src_point.succs[tgt_point.id].baseline += amount
        tgt_point.preds[src_point.id].baseline += amount
    else:
        assert profile_type == "target"
        src_point.succs[tgt_point.id].target += amount
        tgt_point.preds[src_point.id].target += amount


def process_edge(
    sankey_map: dict[str, dict[str, SankeyNode]],
    reachability_map: dict[str, set[str]],
    trace: list[str],
    profile_type: Literal["baseline", "target"],
    src: str,
    tgt: str,
    amount: float,
    cfg: Config,
) -> None:
    """Creates and edge in each of the sankey graph along the trace

    Increases the valuation of appropriate statistic

    :param sankey_map: list of sankey points corresponding to each uid
    :param reachability_map: map of reachable nodes
    :param trace: list of uid representing the trace
    :param profile_type: identification of either baseline or target
    :param src: source id of the edge
    :param tgt: target id of the edge
    :param amount: valuation of the edge
    :param cfg: configuration of the generation
    """
    if cfg.inclusive_traces:
        for t in trace:
            process_single_edge(sankey_map, t, profile_type, src, tgt, amount)
    else:
        for reachable in reachability_map["->".join(trace)].union(set(trace)):
            process_single_edge(sankey_map, reachable, profile_type, src, tgt, amount)


def process_traces(
    profile: Profile,
    sankey_map: dict[str, dict[str, SankeyNode]],
    reachability_map: dict[str, set[str]],
    profile_type: Literal["baseline", "target"],
    cfg: Config,
) -> None:
    """Processes all traces in the profile

    Iterates through all traces and creates edges for each pair
    of source and target.

    :param profile: input profile
    :param sankey_map: output sankey map with sankey nodes
    :param reachability_map: set of nodes reachable for each node
    :param profile_type: type of the profile
    :param cfg: configuration of the generation
    """
    for _, resource in log.progress(profile.all_resources(), description="Processing Traces"):
        trace_len = len(resource["trace"])
        full_trace = [convert.to_uid(t) for t in resource["trace"]] + [
            convert.to_uid(resource["uid"])
        ]
        amount = float(resource[cfg.source_key])
        if trace_len > 0 and amount > cfg.edge_threshold:
            if cfg.inclusive_traces:
                for i in range(0, trace_len - 1):
                    src = f"{full_trace[i]}#{i}"
                    tgt = f"{full_trace[i + 1]}#{i + 1}"
                    process_edge(
                        sankey_map,
                        reachability_map,
                        full_trace,
                        profile_type,
                        src,
                        tgt,
                        amount,
                        cfg,
                    )
                src = f"{full_trace[-2]}#{trace_len - 1}"
                tgt = f"{full_trace[-1]}"
                process_edge(
                    sankey_map,
                    reachability_map,
                    full_trace,
                    profile_type,
                    src,
                    tgt,
                    amount,
                    cfg,
                )
            else:
                src = f"{full_trace[-2]}#{trace_len-1}"
                tgt = f"{full_trace[-1]}#{trace_len}"
                process_edge(
                    sankey_map,
                    reachability_map,
                    full_trace,
                    profile_type,
                    src,
                    tgt,
                    amount,
                    cfg,
                )


def create_edge(
    graph: SankeyGraph,
    edge_type: Literal["split", "merged"],
    src: int,
    tgt: int,
    value: float,
    color: str,
) -> None:
    """Creates single edge in the sankey graph

    :param edge_type: type of the edge
    :param graph: output sankey graph
    :param src: source of the edge
    :param tgt: target of the edge
    :param value: valuation of the edge
    :param color: color of the edge
    """
    if value > 0:
        graph.linkage[edge_type].source.append(src)
        graph.linkage[edge_type].target.append(tgt)
        graph.linkage[edge_type].value.append(value)
        graph.linkage[edge_type].color.append(color)
        graph.min = min(value, graph.min) if graph.min != -1 else value
        graph.max = max(value, graph.max)


def relabel_sankey_points(sankey_points: dict[str, SankeyNode]) -> dict[str, SankeyNode]:
    """Relabels sankey points after the minimization

    :param sankey_points: sankey points
    :return: relabeled sankey points
    """
    ids = [sp.id for sp in sankey_points.values()]
    for sp in sankey_points.values():
        sp.id = ids.index(sp.id)
        new_succs = {ids.index(key): val for (key, val) in sp.succs.items()}
        sp.succs = new_succs
        new_preds = {ids.index(key): val for (key, val) in sp.preds.items()}
        sp.preds = new_preds
    return sankey_points


def delete_node(point, pred, succ):
    """Delets point and merges it into its preds an succs

    merges pred -> point -> succ into pred -> succ

    :param point: point we are deleting
    :param pred: predecessor of the point
    :param succ: succ of point
    """
    pred.succs[succ.id] = pred.succs[point.id]
    pred.succs.pop(point.id)
    pred.trace.append(point.uid)
    succ.preds[pred.id] = succ.preds[point.id]
    succ.preds.pop(point.id)


def minimize_sankey_maps(
    sankey_map: dict[str, dict[str, SankeyNode]],
) -> dict[str, dict[str, SankeyNode]]:
    """Merges chains of unbranched code

    :param sankey_map: map of sankey graphs;
    """
    minimal_sankey_map = {}
    for uid, sankey_points in log.progress(sankey_map.items(), description="Minimizing Sankey Map"):
        id_to_point = {val.id: val for val in sankey_points.values()}
        minimal_sankey_points = {}
        for key in sankey_points.keys():
            point = sankey_points[key]
            if point.uid != uid:
                preds, succs = list(point.preds.keys()), list(point.succs.keys())
                # TODO: Fix that you should compare the stats
                if len(preds) == 1 and len(succs) == 1:
                    pred, succ = id_to_point[preds[0]], id_to_point[succs[0]]
                    if len(pred.succs) == 1 and len(succ.preds) == 1:
                        # Merging a -> b -> c into ab -> c
                        delete_node(point, pred, succ)
                        continue
            minimal_sankey_points[key] = point
        minimal_sankey_map[uid] = relabel_sankey_points(minimal_sankey_points)
    return minimal_sankey_map


def extract_graphs_from_sankey_map(
    sankey_map: dict[str, dict[str, SankeyNode]],
) -> list[SankeyGraph]:
    """For computed maps of sankey edges computes the list of actual sankey graphs


    :return: list of sankey graphs
    """
    sankey_graphs = []

    for uid, sankey_points in log.progress(sankey_map.items(), description="Extracting Graphs"):
        graph = SankeyGraph(uid)
        positions = []

        for point in sankey_points.values():
            if "#" in point.tag:
                positions.append(int(point.tag.split("#")[-1]))
            graph.label.append(
                point.uid if len(point.trace) == 1 else f"{point.uid}⇢{point.trace[-1]}"
            )
            graph.customdata.append([point.tag, "<br>↧<br>".join(point.trace)])
            graph.node_colors.append(
                WebColorPalette.Highlight if point.uid == uid else WebColorPalette.NoHighlight
            )
            for succ, value in point.succs.items():
                value_diff = abs(value.baseline - value.target)
                create_edge(
                    graph, "merged", point.id, succ, value.baseline, WebColorPalette.Baseline
                )
                create_edge(graph, "merged", point.id, succ, value.target, WebColorPalette.Target)
                if value.baseline == value.target:
                    create_edge(
                        graph, "split", point.id, succ, value.baseline, WebColorPalette.Equal
                    )
                elif value.baseline > value.target:
                    create_edge(graph, "split", point.id, succ, value.target, WebColorPalette.Equal)
                    create_edge(
                        graph, "split", point.id, succ, value_diff, WebColorPalette.Decrease
                    )
                    if point.uid == uid:
                        graph.sum += max(value.baseline, value.target)
                        graph.diff -= value_diff
                else:
                    create_edge(
                        graph, "split", point.id, succ, value.baseline, WebColorPalette.Equal
                    )
                    create_edge(
                        graph, "split", point.id, succ, value_diff, WebColorPalette.Increase
                    )
                    if point.uid == uid:
                        graph.sum += max(value.baseline, value.target)
                        graph.diff += value_diff

        graph.width = max(positions) if positions else 10
        graph.height = max(positions.count(pos) for pos in set(positions)) if positions else 10
        sankey_graphs.append(graph)

    return sankey_graphs


def compute_reachable(profile: Profile, reachability_map: dict[str, set[str]]) -> None:
    """Computes map for each node a map of forward reachable functions.

    :param profile: profile with data
    :param reachability_map: map of nodes to their backward or forward reachable nodes
    """
    for _, resource in log.progress(
        profile.all_resources(), description="Computing Reachable Nodes"
    ):
        full_trace = [convert.to_uid(t) for t in resource["trace"]] + [
            convert.to_uid(resource["uid"])
        ]
        for i in range(0, len(full_trace) - 1):
            reachability_map["->".join(full_trace[: i + 1])].update(full_trace[i + 1 :])


def to_sankey_graphs(lhs_profile: Profile, rhs_profile: Profile, cfg: Config) -> list[SankeyGraph]:
    """Converts difference of two profiles to sankey format

    :param lhs_profile: baseline profile
    :param rhs_profile: target profile
    :param cfg: configuration of the generation
    """
    sankey_map: dict[str, dict[str, SankeyNode]] = defaultdict(dict)
    reachability_map: dict[str, set[str]] = defaultdict(set)

    if not cfg.inclusive_traces:
        compute_reachable(lhs_profile, reachability_map)
        compute_reachable(rhs_profile, reachability_map)

    process_traces(lhs_profile, sankey_map, reachability_map, "baseline", cfg)
    process_traces(rhs_profile, sankey_map, reachability_map, "target", cfg)

    if cfg.minimize:
        sankey_map = minimize_sankey_maps(sankey_map)
    return extract_graphs_from_sankey_map(sankey_map)


def generate_sankey_difference(lhs_profile: Profile, rhs_profile: Profile, **kwargs: Any) -> None:
    """Generates differences of two profiles as sankey diagram

    :param lhs_profile: baseline profile
    :param rhs_profile: target profile
    :param kwargs: additional arguments
    """
    # We automatically set the value of True for kperf, which samples
    if lhs_profile.get("collector_info", {}).get("name") == "kperf":
        kwargs["trace_is_inclusive"] = True

    log.major_info("Generating Sankey Graph Difference")

    cfg = Config(
        kwargs.get("minimize", False),
        kwargs.get("source_column", "amount"),
        kwargs.get("trace_is_inclusive", False),
        kwargs.get("filter_edges", 0.0),
    )

    sankey_graphs = sorted(
        to_sankey_graphs(lhs_profile, rhs_profile, cfg),
        key=lambda x: x.uid,
    )
    selection_table = [
        SelectionRow(g.uid, i, g.diff, common_kit.safe_division(g.diff, g.sum) * 100)
        for (i, g) in enumerate(sankey_graphs)
    ]
    lhs_header, rhs_header = diff_kit.generate_diff_of_headers(
        diff_kit.generate_specification(lhs_profile), diff_kit.generate_specification(rhs_profile)
    )

    template = templates.get_template("diff_view_sankey.html.jinja2")
    content = template.render(
        title="Differences of profiles (with sankey)",
        perun_version=perun.__version__,
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + " UTC",
        lhs_tag="Baseline (base)",
        lhs_header=lhs_header,
        rhs_tag="Target (tgt)",
        rhs_header=rhs_header,
        sankey_graphs=sankey_graphs,
        selection_table=selection_table,
        palette=WebColorPalette,
    )
    log.minor_success("Difference sankey", "generated")
    output_file = diff_kit.save_diff_view(
        kwargs.get("output_file"), content, "sankey", lhs_profile, rhs_profile
    )
    log.minor_status("Output saved", log.path_style(output_file))


@click.command()
@click.option("-o", "--output-file", help="Sets the output file (default=automatically generated).")
@click.option(
    "-m",
    "--minimize",
    help="Minimizes the sankey grafs by merging non-branching points (default=False).",
    is_flag=True,
    default=False,
)
@click.option(
    "-c",
    "--source-column",
    nargs=1,
    help="Selects column for output of the sankey graph (default=amount).",
    default="amount",
)
@click.option(
    "-i",
    "--trace-is-inclusive",
    is_flag=True,
    default=False,
    help="Marks that the amount should be distributed through all of the traces (default=False). "
    "Note, that for kperf profiles we set this automatically to true.",
)
@click.option(
    "-f",
    "--filter-edges",
    default=-1.0,
    type=click.FLOAT,
    help="Filters edges smaller than [INT] valuation for both target and baseline (default=0).",
)
@click.pass_context
def sankey(ctx: click.Context, *_: Any, **kwargs: Any) -> None:
    """Creates sankey graphs representing the differences between two profiles"""
    assert ctx.parent is not None and f"impossible happened: {ctx} has no parent"
    profile_list = ctx.parent.params["profile_list"]
    generate_sankey_difference(profile_list[0], profile_list[1], **kwargs)
