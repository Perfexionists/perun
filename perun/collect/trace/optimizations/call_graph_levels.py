"""This Mixin class is used to inject specific "Call Graph Level Estimation" functionality
into the Call Graph class.

The call graph level estimation is implemented using various techniques and heuristics that
can be rather complicated, confusing and not very straightforward - thus cluttering the
definition of the Call Graph class and making it more difficult to understand the bigger
picture. Combined with the fact that the user of the Call Graph class does not necessarily
need to know all the nitty-gritty details about the level estimation (but rather being aware
of its existence) makes this functionality an ideal candidate for separation.

Since the estimation heavily leverages the Call Graph class data, it is designed as a Mixin
to seamlessly integrate into the Call Graph class.

"""

from enum import Enum

import networkx as nx


class LevelEstimator(Enum):
    """The collection of supported Call Graph Level estimators.

    The DFS estimator obtains a set of backedges identified during a DFS call graph traversal
    and then builds levels as follows:
     - initially, the 'main' function has level 0
     - in each iteration, we add function to the new level if all of their non-backedge callers
       already have a level value assigned

    The DOM estimator works similarly to the DFS estimator, the only difference being different
    approach to backedges identification - instead of DFS traversal, we leverage the dominance
    relation.

    The LongestPath estimates the longest simple path from root to all other nodes and assigns
    each node its level based on the obtained path length.
    """

    DFS = "DFS"
    DOM = "DOM"
    LONGEST_PATH = "LP"


# TODO: unify leaves / bottom across multiple estimators!!!
class CGLevelMixin:
    """Avoid intellisense warnings (since Mixin classes are not properly supported by PyCharm's
    code inspection): @DynamicAttrs
    """

    def _estimator_dispatcher(self, estimator):
        """Fetches the appropriate handler function according to the selected estimator.

        :param estimator: the selected estimator

        :return: appropriate estimator function
        """
        _dispatcher = {
            LevelEstimator.DFS: self._dfs_estimator,
            LevelEstimator.DOM: self._dom_estimator,
            LevelEstimator.LONGEST_PATH: self._lp_estimator,
        }
        return _dispatcher[estimator]

    def _build_levels(self, estimator):
        """Computes the levels property of CGR using the selected estimator."""
        # Estimate the levels of the nodes using the selected estimator
        self._estimator_dispatcher(estimator)()
        # Build the level lists
        self.depth = max(self.cg_map.values(), key=lambda item: item["level"])["level"]
        self.levels = [[] for _ in range(self.depth + 1)]
        # Assign the functions to the level lists
        for func_name, func_config in self.cg_map.items():
            # Register the call graph function as a leaf if it has no callees
            self._set_leaf(func_config)
            # Keep a reference to the function in the appropriate level
            self.levels[func_config["level"]].append(func_name)

    def _dfs_estimator(self):
        """Computes the levels property of CGR using the DFS estimator."""
        # Compute the back edges using a DFS traversal
        self._dfs_backedges()
        # Obtain the bottom nodes based on the back edges and callees
        self.compute_bottom()
        # Compute the call graph levels
        self._iterative_level()

    def _dfs_backedges(self):
        """Performs the DFS graph traversal and identifies backedges based on the traversal."""
        # Backedges are represented as 'func': set(f1, f2, ..) where f1 and f2 are callees of 'func'
        self.backedges = {node: set() for node in self.cg_map.keys()}
        # List of unvisited callees for each visited node
        edge_list = {"main": list(self["main"]["callees"])}
        # Stack trace of the current traversed path
        stack_trace = ["main"]
        while stack_trace:
            current_node = stack_trace[-1]
            # Obtain next edge, if any
            if not edge_list[current_node]:
                stack_trace.pop()
                continue
            next_node = edge_list[current_node].pop()
            # If the node is already in the stack, it is a backedge
            if next_node in stack_trace:
                self.backedges[current_node].add(next_node)
                continue
            stack_trace.append(next_node)
            # In case the node was not yet encountered, register it
            edge_list.setdefault(next_node, list(self[next_node]["callees"]))

    def _dom_estimator(self):
        """Computes the dominance relation using the immediate dominators."""
        # Create networkx graph
        edges = [
            (parent, callee) for parent in self.cg_map.keys() for callee in self[parent]["callees"]
        ]
        graph = nx.DiGraph(edges)

        # Use it to compute dominance and identify back edges
        idom = nx.immediate_dominators(graph, "main")
        self.backedges = {
            vertex: _find_backedges_for(vertex, graph.successors(vertex), idom)
            for vertex in graph.nodes()
        }
        # Using the back edges, compute bottom
        self.calculate_bottom()
        # Finally, iteratively compute the call graph levels
        self._iterative_level()

    def _iterative_level(self):
        """Iteratively build the CG levels, where new level is defined as a set of functions which
        already have all of their callers resolved - i.e., the callers either have assigned level
        or are classified as backedges.
        """
        # Visited functions that still have some unresolved callers
        candidates = set()
        # The 'main' function is at the top of the CG and thus the first level
        self["main"]["level"] = 0
        # Iterative sets that define the levels
        iter_sets = [
            {"main"},
        ]
        # Functions that are resolved, i.e., have been assigned a level
        processed = iter_sets[-1]
        while iter_sets[-1]:
            # The new level
            new_iter = set()
            # New visited functions reachable from the last level
            for func in iter_sets[-1]:
                candidates |= set(self[func]["callees"]) - self.backedges[func] - processed
            # Check if there is a caller that has not been resolved yet
            for func in candidates:
                unsolved_callers = {
                    caller for caller in self[func]["callers"] if func not in self.backedges[caller]
                } - processed
                if not unsolved_callers:
                    new_iter.add(func)
            # Update the visited, resolved and level structures
            candidates -= new_iter
            processed |= new_iter
            iter_sets.append(new_iter)
            iter_idx = len(iter_sets) - 1
            # Assign the level to the CG nodes
            for func in new_iter:
                self[func]["level"] = iter_idx

    def _lp_estimator(self):
        """The longest path length estimator. Since LP is a NP-complete problem, we leverage a
        heuristic to estimate the length - basically, we try to resolve all callers and based on
        the highest length (level) of the callers, we assign the resulting level estimate. When we
        cannot resolve all callers, it indicates a cycle which we break by estimating a level based
        only on the resolved callers and callees.
        """
        finished = set()
        visited_pairs = {}
        # nodes: {<function name>: {
        #     'level': <current maximum level estimate>,
        #     'callers': <remaining callers that were not yet inspected>}
        # }
        # levels: {<level>: {'fun1', 'fun2', 'fun3', ...}}
        tested = {"nodes": {}, "levels": {}}

        self["main"]["level"] = 0
        # Inspect list keeps track of caller -> callee pairs to inspect in a BFS fashion
        inspect_list = [("main", callee, 0) for callee in self["main"]["callees"]]
        while inspect_list:
            # Get the next candidate to expand
            parent, callee, level = inspect_list.pop(0)
            parent_visited = visited_pairs.setdefault(parent, [])
            # Avoid duplicate checks (caused e.g. by loops)
            if callee not in parent_visited and callee not in finished:
                # Add new level candidate based on the caller level
                parent_visited.append(callee)
                callee_node = self[callee]
                callee_node["level"].append(level)
                # Update the tested records
                _update_tested(tested, callee_node, parent)

                # If all the callers have been already inspected, set the level to its maximum
                if len(callee_node["level"]) == len(callee_node["callers"]):
                    # callee_node['level'] = max(callee_node['level'])
                    self._lp_set_level(callee_node)
                    finished.add(callee)
                    # Expand the callees to be inspected as well, if any
                    if callee_node["callees"]:
                        inspect_list.extend(
                            (callee, callee_callee, callee_node["level"])
                            for callee_callee in callee_node["callees"]
                        )
            # There can still be some functions that were not assigned a level since not all of the
            # callers were inspected - this means that there is a cycle in the call graph and
            # we break it by finding an unfinished function with the lowest level estimate (i.e.
            # not all of the callers were inspected yet and thus the level is not accurate)
            # and setting the function as finished (thus setting the level estimate as the final
            # level value), which generates new records for the inspect list - if the function has
            # any callees.
            while not inspect_list:
                if not self._lp_expand_candidate(tested, finished, inspect_list):
                    break

    def _lp_expand_candidate(self, tested, finished, inspect_list):
        """Find unresolved function that is the best candidate for breaking the loop in CG. We
        select functions that have the currently lowest level estimate, since they might cause a
        domino effect by subsequently breaking other cycles.

        :param tested: an internal structure that keeps track of the fully unresolved functions
        :param finished: a set of already fully resolved functions
        :param inspect_list: the set of functions that are queued for further expansion

        :return: True if we managed to find and process a candidate, False otherwise
        """
        # No more candidates, every function should have a valid level estimate
        if not tested["levels"]:
            return False
        # Get the next candidate
        candidate_level = min(tested["levels"].keys())
        candidate = sorted(list(tested["levels"][candidate_level]))[0]
        # Delete it from the tested dictionary
        _delete_from_levels(tested["levels"], candidate_level, candidate)
        del tested["nodes"][candidate]
        # Set the node as finished and expand the candidate into the inspect list
        node = self[candidate]
        self._lp_set_level(node)
        # node['level'] = candidate_level
        finished.add(candidate)
        inspect_list.extend([(candidate, callee, node["level"]) for callee in node["callees"]])
        return True

    def _lp_set_level(self, node):
        """Assigns a level value to the supplied node, i.e., function.

        We set the level according to the maximum caller and callee level (to avoid e.g., two
        functions that call one another on the same level).

        :param node: the object representing a CG function
        """
        callers_max = max(node["level"])
        # Inspect the callees, however, they might or might not be already resolved
        callee_max = []
        for callee in node["callees"]:
            callee_level = self[callee]["level"]
            if isinstance(callee_level, int):
                callee_max.append(callee_level)
            else:
                if callee_level:
                    callee_max.append(max(callee_level))
        # Set the level as the maximum of callers and callees + 1
        callee_max = max(callee_max) if callee_max else callers_max
        node["level"] = max(callers_max, callee_max) + 1


def _find_backedges_for(vertex, successors, idom):
    """Identifies backedges by computing the dominance relation that uses the transitive property
    of the immediate dominators.

    :param vertex: the CG vertex
    :param successors: iterator of the vertex successors
    :param idom: the immediate dominators dictionary

    :return: a set of backedges originating from the vertex
    """
    # Get the trivial dominator (the vertex itself) and its immediate dominator
    dom = [vertex, idom[vertex]]
    # Build the rest of the dominator set (by traversing the dominator tree)
    while dom[-1] != dom[-2]:
        dom.append(idom[dom[-1]])
    dom = set(dom)

    vertex_backedges = set()
    for succ in successors:
        if succ in dom:
            vertex_backedges.add(succ)
    return vertex_backedges


def _update_tested(tested, node, caller):
    """Update the internal structure that keeps track of candidates and their levels in a
    fast-access structure.

    :param tested: the helper structure used during computing the CG levels property
    :param node: the updated function, supplied as dictionary
    :param caller: the caller context, i.e., name of the caller function
    """
    # Get the node and levels structures
    levels = tested["levels"]
    tested_node = tested["nodes"].setdefault(
        node["name"], {"level": -1, "callers": list(node["callers"])}
    )
    # Remove the caller from the node record
    if caller in tested_node["callers"]:
        tested_node["callers"].remove(caller)
        # Remove the tested record if no more callers are remaining
        if not tested_node["callers"]:
            _delete_from_levels(levels, tested_node["level"], node["name"])
            del tested["nodes"][node["name"]]
            return

    # Reassign the node to a new minimum level
    old_level = tested_node["level"]
    new_level = max(node["level"])
    if new_level > old_level:
        tested_node["level"] = new_level
        # Remove the old level association
        _delete_from_levels(levels, old_level, node["name"])
        # Add the node to the new corresponding level
        levels.setdefault(new_level, set()).add(node["name"])


def _delete_from_levels(levels, level, name):
    """Delete the specified function from the helper levels structure for candidates.

    :param levels: a list structure that bundles and keeps track of candidate levels
    :param level: the level containing the function to remove
    :param name: name of the function to remove
    """
    if level != -1:
        levels[level].discard(name)
        # Remove the entire level category if no more records are there
        if not levels[level]:
            del levels[level]
