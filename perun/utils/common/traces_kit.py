"""Set of helpers for working with traces"""

from __future__ import annotations

import itertools

# Standard Imports
from collections import defaultdict
from enum import Enum
from typing import Any, Callable, Optional
import functools

# Third-Party Imports

# Perun Imports


class ClassificationStrategy(Enum):
    """The strategy used for final classification of the clusters.

    The traces are first classified wrt to first initial (stratification) classification.
    Then for each sublayer of classifiers, we can employ particular strategies to find
    suitable cluster for given trace.

    1. first-fit: finds first cluster, that matches the threshold of the distance,
    2. best-fit: finds the best cluster, that has the least distance.
    """

    FIRST_FIT = "first-fit"
    BEST_FIT = "best-fit"
    IDENTITY = "identity"


DEFAULT_THRESHOLD: float = 2.0


class TraceCluster:
    """TraceCluster represents a single cluster, that contains list of similar traces.

    Each cluster is represented by its members and its pivot: the first member of the created cluster.

    :ivar pivot: main representant of the cluster, that is used for comparisons with other members
    :ivar members: list of members corresponding to the cluster, whose distance is from pivot smaller than
        threshold of the classifier.
    """

    __slots__ = ["members", "pivot", "id"]
    cluster_dict: dict[str, int] = defaultdict(int)
    id_set: set[str] = set()

    def __init__(self, pivot: TraceClusterMember):
        """Creates empty cluster with single element

        :param pivot: initial pivot of the cluster
        """
        trace_key = (
            f"{pivot.as_list[0]},...,{pivot.as_list[-1]}"
            if len(pivot.as_list) >= 2
            else pivot.as_str
        )
        self.id: str = f"{trace_key}#{TraceCluster.cluster_dict[trace_key]}"
        TraceCluster.id_set.add(self.id)
        self.pivot: TraceClusterMember = pivot
        self.members: list[TraceClusterMember] = [pivot]


class TraceClusterMember:
    """TraceClusterMember represents a single member of the cluster

    :ivar distance: distance of the trace from its parent pivot
    :ivar as_str: member represented as string
    :ivar as_list: member represented as list
    :ivar parent: parent cluster
    """

    __slots__ = ["distance", "as_str", "as_list", "parent"]

    def __init__(self, trace: list[str], trace_as_str: str):
        """Initializes the member based on list of traces and its representation as single string

        :param trace: trace represented as list of strings
        :param trace_as_str: trace represented as string
        """
        self.distance: float = 0
        self.as_str: str = trace_as_str
        self.parent: Optional[TraceCluster] = None
        self.as_list: list[str] = trace


class TraceClassifierLayer:
    """Single layer that classifies traces into clusters

    When given a trace, the layer either returns previously classified cluster, or it iterates
    through the clusters, tries to find a suitable cluster, and if not found, a new one is created.
    The trace is then merged into the classified cluster.

    The layer utilizes its own cache for computing the distances. For computing costs of switching
    uids in the traces, we use the shared general cache.

    :ivar trace_to_cluster: mapping of traces (as strings) to their classified TraceClusters
    :ivar distance_cache: cache of the distances between two traces represented as floating point
    :ivar clusters: list of clusters in the layer
    :ivar find_cluster: function used to find appropriate cluster; this is set wrt strategy either
        as 'best-fit' or as 'first-fit'.
    :ivar threshold: threshold of the distances between vectors.
    """

    __slots__ = [
        "trace_to_cluster",
        "distance_cache",
        "clusters",
        "find_cluster",
        "threshold",
    ]

    def __init__(
        self,
        strategy: ClassificationStrategy = ClassificationStrategy.FIRST_FIT,
        threshold: float = DEFAULT_THRESHOLD,
    ):
        """Initializes the cluster layer

        :param strategy: strategy used to find the appropriate cluster
        :param threshold: threshold for checking the distances between traces; traces of different
            lengths are automatically pruned.
        """
        self.trace_to_cluster: dict[str, TraceCluster] = {}
        self.distance_cache: dict[str, float] = {}
        self.clusters: list[TraceCluster] = []
        if strategy == ClassificationStrategy.FIRST_FIT:
            self.find_cluster: Callable[[TraceClusterMember], TraceCluster] = (
                self.find_first_fit_cluster_for
            )
        elif strategy == ClassificationStrategy.IDENTITY:
            self.find_cluster: Callable[[TraceClusterMember], TraceCluster] = (  # type: ignore
                self.find_identity_for
            )
        else:
            assert strategy == ClassificationStrategy.BEST_FIT
            self.find_cluster: Callable[[TraceClusterMember], TraceCluster] = (  # type: ignore
                self.find_best_fit_cluster_for
            )
        self.threshold: float = threshold

    def classify_trace(self, trace: list[str]) -> TraceCluster:
        """For given trace return corresponding cluster

        First, we check, if we already get the cluster classified.
        Otherwise, we iterate through the clusters and try to find either best-fit
        or first-fit.

        :param trace: trace represent as (ordered) list of uids
        """
        trace_as_str = ",".join(trace)
        if trace_as_str not in self.trace_to_cluster:
            cluster = self.find_cluster_for(TraceClusterMember(trace, trace_as_str))
            self.trace_to_cluster[trace_as_str] = cluster
            return cluster
        return self.trace_to_cluster[trace_as_str]

    def find_cluster_for(self, trace_member: TraceClusterMember) -> TraceCluster:
        """Dynamically invokes strategy used for finding cluster for given trace

        :param trace_member: trace which we are classifying
        :return: classification of the traces
        """
        return self.find_cluster(trace_member)

    def find_identity_for(self, trace_member: TraceClusterMember) -> TraceCluster:
        """Always creates new cluster for trace

        :param trace_member: trace which we are classifying
        :return: classification of the traces
        """
        new_cluster = TraceCluster(trace_member)
        self.clusters.append(new_cluster)
        trace_member.parent = new_cluster
        return new_cluster

    def find_first_fit_cluster_for(self, trace_member: TraceClusterMember) -> TraceCluster:
        """Finds first suitable cluster for the given trace

        We iterate through all the clusters; we skip clusters, that are bigger than
        the analysed traces wrt given threshold (no need to classify them, since
        they will always have cost higher than the threshold). If we find some
        cluster that is suitable, we return it.

        If no cluster is found, we create a new one.

        Note: this might return worst cluster than there actually is, especially
        if the threshold is low: generally we want to find such clusters that have
        mostly the switching of uids.

        :param trace_member: trace which we are classifying
        :return: classification of the traces
        """
        trace_len = len(trace_member.as_list)
        for cluster in self.clusters:
            if abs(len(cluster.pivot.as_list) - trace_len) <= self.threshold:
                fitness = fast_compute_distance(
                    trace_member.as_list, cluster.pivot.as_list, self.threshold, self.distance_cache
                )
                if fitness <= self.threshold:
                    cluster.members.append(trace_member)
                    trace_member.parent = cluster
                    trace_member.distance = fitness
                    return cluster

        # We did not find any suitable cluster, hence we crate new one
        new_cluster = TraceCluster(trace_member)
        self.clusters.append(new_cluster)
        trace_member.parent = new_cluster
        return new_cluster

    def find_best_fit_cluster_for(self, trace_member: TraceClusterMember) -> TraceCluster:
        """Finds best fit cluster for the given trace

        We iterate through all the clusters; we skip clusters, that are bigger than
        the analysed traces wrt given threshold (no need to classify them, since
        they will always have cost higher than the threshold). We then remember which
        cluster had the best fit. This is finally returned.

        If no cluster is found, we create a new one.

        Note: this finds the best cluster, however, if there is too much clusters, it might lead
        to an excesive number of comparisons leading to high computational cost.

        :param trace_member: trace which we are classifying
        :return: classification of the traces
        """
        best_fit: Optional[TraceCluster] = None
        best_fit_distance = self.threshold
        trace_len = len(trace_member.as_list)
        for cluster in self.clusters:
            if abs(len(cluster.pivot.as_list) - trace_len) <= self.threshold:
                fitness = fast_compute_distance(
                    trace_member.as_list, cluster.pivot.as_list, self.threshold, self.distance_cache
                )
                if fitness < best_fit_distance or (
                    fitness == best_fit_distance and best_fit is None
                ):
                    best_fit = cluster
        if not best_fit:
            # We did not find any suitable cluster, hence we crate new one
            new_cluster = TraceCluster(trace_member)
            self.clusters.append(new_cluster)
            trace_member.parent = new_cluster
            return new_cluster
        else:
            trace_member.parent = best_fit
            trace_member.distance = best_fit_distance
            best_fit.members.append(trace_member)
            return best_fit


class TraceClassifier:
    """Hierarchical classifier of traces

    The first layer is done wrt stratification: by default we look at the prefix of the
    trace and use its first two callers in the traces. This can be changed by different
    function (e.g. wrt existence of some function).

    The classifier then uses the appropriate layer, that does the actual classification.

    :ivar layers: map of layers of classifiers wrt stratification
    :ivar strategy: strategy used in each classifier for finding the suitable cluster for trace
    :ivar threshold: threshold used in each classifier for limiting the computed distance
    :ivar stratification_strategy: strategy used to distribute the state space into a smaller
        number of layers.
    """

    __slots__ = ["layers", "strategy", "threshold", "stratification_strategy"]

    def __init__(
        self,
        strategy: ClassificationStrategy = ClassificationStrategy.FIRST_FIT,
        threshold: float = DEFAULT_THRESHOLD,
        stratification_strategy: Optional[Callable[[list[str]], str]] = None,
    ):
        """Initializes the classifier

        :param strategy: strategy for classification in each sublayer
        :param threshold: threshold for computed distance
        :param stratification_strategy: strategy for distributing the state space into smaller layers
        """
        self.layers: dict[str, TraceClassifierLayer] = {}
        self.strategy: ClassificationStrategy = strategy
        if stratification_strategy is not None:
            self.stratification_strategy: Callable[[list[str]], str] = stratification_strategy
        else:
            self.stratification_strategy = TraceClassifier.stratify_trace
        self.threshold: float = threshold

    @staticmethod
    def stratify_trace(trace: list[str]) -> str:
        """Basic stratification of the traces

        We use the first two callers as the prefix to distribute traces into smaller state space.

        :param trace: classified trace
        :return: representation of the master class of the trace
        """
        return ",".join(trace[:2])

    def get_classification_layer(self, trace: list[str]) -> TraceClassifierLayer:
        """Finds the layer, where we will classify the trace

        :param trace: classified trace for which we are looking up sub state space
        :return: layer, where the trace will be classified
        """
        stratification = self.stratification_strategy(trace)
        if layer := self.layers.get(stratification):
            return layer
        new_layer = TraceClassifierLayer(self.strategy, self.threshold)
        self.layers[stratification] = new_layer
        return new_layer

    def classify_trace(self, trace: list[str]) -> TraceCluster:
        """Classifies the trace

        :param trace: trace
        :return: classification of the trace
        """
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


def fast_compute_distance(
    lhs: list[str], rhs: list[str], threshold: float, cache: dict[str, float]
) -> float:
    """Optimized version of the computed distance

    See the `compute_distance` for more info about the algorithm.

    In particular this optimizes the following:

      1. The heuristics wrt length of the traces are extracted and not cached.
      2. We assume, that if the traces are of same length, then the switch is always preferred.
      3. We always insert/delete to bigger side (hence, omitting one case)

    :param lhs: left trace
    :param rhs: right trace
    :param threshold: threshold for pruning less interesting traces from start
    :param cache: cache for the results
    :return: distance between rhs and lhs
    """
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


def fold_recursive_calls_in_trace(trace: list[str], generalize: bool = False) -> list[str]:
    """Folds consecutive recursive calls to single uid

    If generalize is set to True, then each consecutive calls to certain UID will be
    folded to ^*, otherwise to ^{number_of_consecutive_calls}.

    So, e.g., for trace [a, b, c, c, c], we get [a, b, c^3] for generalize=False, and [a, b, c^*] otherwise.

    :param trace: list of strings in order of calls
    :param generalize: if set to true, then the folded calls will be generalized to *
    :return: trace with folded recursive calls
    """
    folded_trace = []
    for uid, group in itertools.groupby(trace):
        count = sum(1 for _ in group)
        if count > 1:
            folded_trace.append(f"{uid}^*" if generalize else f"{uid}^{count}")
        else:
            folded_trace.append(uid)
    return folded_trace
