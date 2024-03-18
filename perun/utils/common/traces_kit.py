"""Set of helpers for working with traces """
from __future__ import annotations

# Standard Imports
from enum import Enum
from typing import Any, Callable, Optional
import functools

# Third-Party Imports

# Perun Imports


class ClassificationStrategy(Enum):
    """ """

    FIRST_FIT = "first-fit"
    BEST_FIT = "best-fit"


DEFAULT_THRESHOLD: float = 2.0


class TraceCluster:
    __slots__ = ["members", "pivot"]

    def __init__(self, pivot: TraceClusterMember):
        self.pivot: TraceClusterMember = pivot
        self.members: list[TraceClusterMember] = [pivot]


class TraceClusterMember:
    __slots__ = ["distance", "as_str", "as_list", "parent"]

    def __init__(self, trace: list[str], trace_as_str: str):
        self.distance: int = 0
        self.as_str: str = trace_as_str
        self.parent: Optional[TraceCluster] = None
        self.as_list: list[str] = trace


class TraceClassifierLayer:
    __slots__ = [
        "trace_to_cluster",
        "distance_cache",
        "cost_cache",
        "clusters",
        "find_cluster",
        "threshold",
    ]

    def __init__(
        self,
        strategy: ClassificationStrategy = ClassificationStrategy.FIRST_FIT,
        threshold: float = DEFAULT_THRESHOLD,
    ):
        self.trace_to_cluster: dict[str, TraceClusterMember] = {}
        self.distance_cache: dict[str, float] = {}
        self.cost_cache: dict[str, float] = {}
        self.clusters: list[TraceCluster] = []
        if strategy == ClassificationStrategy.FIRST_FIT:
            self.find_cluster: Callable[
                [TraceClusterMember], TraceClusterMember
            ] = self.find_first_fit_cluster_for
        else:
            assert strategy == ClassificationStrategy.BEST_FIT
            self.find_cluster: Callable[
                [TraceClusterMember], TraceClusterMember
            ] = self.find_best_fit_cluster_for
        self.threshold: float = threshold

    def classify_trace(self, trace: list[str]) -> TraceClusterMember:
        trace_as_str = ",".join(trace)
        if trace_as_str not in self.trace_to_cluster:
            cluster = self.find_cluster_for(TraceClusterMember(trace, trace_as_str))
            self.trace_to_cluster[trace_as_str] = cluster
            return cluster
        return self.trace_to_cluster[trace_as_str]

    def find_cluster_for(self, trace_member: TraceClusterMember) -> TraceClusterMember:
        return self.find_cluster(trace_member)

    def find_first_fit_cluster_for(self, trace_member: TraceClusterMember) -> TraceClusterMember:
        trace_len = len(trace_member.as_list)
        for cluster in self.clusters:
            if abs(len(cluster.pivot.as_list) - trace_len) > self.threshold:
                continue
            fitness = fast_compute_distance(
                trace_member.as_list, cluster.pivot.as_list, self.threshold, self.distance_cache
            )
            if fitness <= self.threshold:
                cluster.members.append(trace_member)
                trace_member.parent = cluster
                trace_member.distance = fitness
                return cluster.pivot

        # We did not find any suitable cluster, hence we crate new one
        new_cluster = TraceCluster(trace_member)
        self.clusters.append(new_cluster)
        trace_member.parent = new_cluster
        return trace_member

    def find_best_fit_cluster_for(self, trace_member: TraceClusterMember) -> TraceClusterMember:
        best_fit: Optional[TraceCluster] = None
        best_fit_distance = self.threshold + 1
        trace_len = len(trace_member.as_list)
        for cluster in self.clusters:
            if abs(len(cluster.pivot.as_list) - trace_len) > self.threshold:
                continue
            fitness = fast_compute_distance(
                trace_member.as_list, cluster.pivot.as_list, self.threshold, self.distance_cache
            )
            if fitness < best_fit_distance:
                best_fit = cluster
        if not best_fit:
            # We did not find any suitable cluster, hence we crate new one
            new_cluster = TraceCluster(trace_member)
            self.clusters.append(new_cluster)
            trace_member.parent = new_cluster
            return trace_member
        else:
            trace_member.parent = best_fit
            trace_member.distance = best_fit_distance
            best_fit.members.append(trace_member)
            return best_fit.pivot


class TraceClassifier:
    __slots__ = ["layers", "strategy", "threshold"]

    def __init__(
        self,
        strategy: ClassificationStrategy = ClassificationStrategy.FIRST_FIT,
        threshold: float = DEFAULT_THRESHOLD,
    ):
        self.layers: dict[str, TraceClassifierLayer] = {}
        self.strategy: ClassificationStrategy = strategy
        self.threshold: float = threshold

    @staticmethod
    def stratify_trace(trace: list[str]) -> str:
        return ",".join(trace[:2])

    def get_classification_layer(self, trace: list[str]) -> TraceClassifierLayer:
        stratification = TraceClassifier.stratify_trace(trace)
        if layer := self.layers.get(stratification):
            return layer
        new_layer = TraceClassifierLayer(self.strategy, self.threshold)
        self.layers[stratification] = new_layer
        return new_layer

    def classify_trace(self, trace: list[str]) -> TraceClusterMember:
        layer = self.get_classification_layer(trace)
        return layer.classify_trace(trace)


@functools.cache
def split_to_words(identifier: str) -> set[str]:
    """Splits identifier of function into list of words

    For simplicity, we assume, that identifier is in snake case, so camel case will not be split

    :param identifier: identifier of function or other primitive, that consists of words
    :return: list of words in identifier
    """
    return set(identifier.split("_"))


def switch_cost(lhs_identifier: str, rhs_identifier: str) -> float:
    """Computes cost of switching lhs_identifier with rhs_identifier

    The cost is computed as 1 - 2 * number of common words / (number of words in LHS + number of words in RHS)

    :param lhs_identifier: left hand side identifier (function)
    :param rhs_identifier: right hand side identifier (function)
    :return: float cost of switching lhs with rhs
    """
    key = (
        f"{lhs_identifier};{rhs_identifier}"
        if lhs_identifier < rhs_identifier
        else f"{rhs_identifier};{lhs_identifier}"
    )
    if key not in SWITCH_CACHE.keys():
        lhs_words = split_to_words(lhs_identifier)
        rhs_words = split_to_words(rhs_identifier)
        cost = 1 - (2 * len(lhs_words.intersection(rhs_words)) / (len(lhs_words) + len(rhs_words)))
        SWITCH_CACHE[key] = cost
    return SWITCH_CACHE[key]


DISTANCE_CACHE: dict[str, float] = {}
SWITCH_CACHE: dict[str, float] = {}


def compute_distance(
    lhs_trace: list[dict[str, Any]],
    rhs_trace: list[dict[str, Any]],
    trace_key: str = "func",
) -> float:
    """Computes the distance between two traces

    The distance is computed as least number of applications of following operations:

      1. Match (cost = 0): matching parts of the traces, i.e. the same functions;
      2. Insert/Delete (cost = 1): adding or deleting part of the trace, so the traces match
      3. Substituion (cost = variable): switching part of the trace with another

    This is based on [ISCSME'21] paper called:
    Performance debugging in the large via mining millions of stack traces

    We assume, that the inputs are in form of list which contains the dictionaries
    with key "func" that corresponds to the name of the ids. One can change it using
    the parameter "trace_key".

    :param lhs_trace: lhs trace of function names
    :param rhs_trace: rhs trace of function names
    :param trace_key: key that is used for retrieving the trace names
    :return: distance between two traces
    """
    key = f"{','.join(l[trace_key] for l in lhs_trace)};{','.join(r[trace_key] for r in rhs_trace)}"

    if key not in DISTANCE_CACHE.keys():
        # We need to insert everything from RHS, hence full cost of what is in RHS
        if len(lhs_trace) == 0:
            cost = float(len(rhs_trace))
        # We need to insert everything from LHS, hence full cost of what is in LHS
        elif len(rhs_trace) == 0:
            cost = float(len(lhs_trace))
        # 1. First parts are matched in the trace, so the cost is the cost of matching the rest of the trace
        elif lhs_trace[0][trace_key] == rhs_trace[0][trace_key]:
            cost = compute_distance(lhs_trace[1:], rhs_trace[1:], trace_key)
        # Else, we have to either try to insert/delete or switch functions
        else:
            # 2. We try Insertion/Deletion of the current functions, and add the cost of inserting/deleting
            cost_delete_lhs = compute_distance(lhs_trace[1:], rhs_trace, trace_key) + 1
            cost_delete_rhs = compute_distance(lhs_trace, rhs_trace[1:], trace_key) + 1
            # 3. We try Switch of the current two functions add the switch cost and compute the rest of the distance
            cost_switch = compute_distance(lhs_trace[1:], rhs_trace[1:], trace_key) + switch_cost(
                lhs_trace[0][trace_key], rhs_trace[0][trace_key]
            )
            # We take the minimum of the computed costs
            cost = min(cost_delete_lhs, cost_delete_rhs, cost_switch)
        DISTANCE_CACHE[key] = cost
    return DISTANCE_CACHE[key]


def fast_switch_cost(lhs: str, rhs: str, switch_cache: dict[str, float]) -> float:
    key = f"{lhs};{rhs}" if lhs < rhs else f"{rhs};{lhs}"
    if key not in switch_cache.keys():
        lhs_words = set(lhs.split("_"))
        rhs_words = set(rhs.split("_"))
        cost = 1 - (2 * len(lhs_words.intersection(rhs_words)) / (len(lhs_words) + len(rhs_words)))
        switch_cache[key] = cost
    return switch_cache[key]


def fast_compute_distance(
    lhs: list[str], rhs: list[str], threshold: float, cache: dict[str, float]
) -> float:
    keys = [",".join(lhs), ",".join(rhs)]
    key = f"{keys[0]};{keys[1]}" if keys[0] < keys[1] else f"{keys[1]};{keys[0]}"
    lhs_len = len(lhs)
    rhs_len = len(rhs)

    if lhs_len == 0:
        return rhs_len
    if rhs_len == 0:
        return lhs_len
    if abs(lhs_len - rhs_len) > threshold:
        return threshold + 1

    if key not in cache.keys():
        # Extremes we need to insert or delete
        # 1. First match
        if lhs[0] == rhs[0]:
            cost = fast_compute_distance(lhs[1:], rhs[1:], threshold, cache)
        elif lhs_len == rhs_len:
            # We will always do switch if the lens are same
            cost = fast_compute_distance(lhs[1:], rhs[1:], threshold, cache) + switch_cost(
                lhs[0], rhs[0]
            )
        else:
            costs = []
            # 2. Try Insertion/Deletion
            if lhs_len > rhs_len:
                costs.append(fast_compute_distance(lhs[1:], rhs, threshold, cache) + 1)
            else:
                costs.append(fast_compute_distance(lhs, rhs[1:], threshold, cache) + 1)
            # 3. Try Switch
            costs.append(
                fast_compute_distance(lhs[1:], rhs[1:], threshold, cache)
                + switch_cost(lhs[0], rhs[0])
            )
            cost = min(costs)
        cache[key] = cost
    return cache[key]
