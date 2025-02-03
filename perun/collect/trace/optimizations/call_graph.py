"""A module that implements the Call Graph Resource and all related operations needed for
easy manipulation with its structure.

The Call Graph Structure stores the extracted call graph as well as the control flow graph.
"""

from perun.logic import pcs
from perun.collect.trace.optimizations.call_graph_levels import (
    CGLevelMixin,
    LevelEstimator,
)
from perun.collect.trace.optimizations.structs import Complexity


# TODO: think about converting the proprietary graph structure into the networkx graph
class CallGraphResource(CGLevelMixin):
    """The call graph resource class with all the additional properties.

    :ivar cg_map: a dictionary with all the call graph nodes,
                       i.e., structures that represent functions
    :ivar reachable: a list of reachable functions computed for each cg_map function
    :ivar levels: a list containing lists of functions that have the same 'level' estimation,
                       the list index is also the level value
    :ivar leaves: a list of leaf function names
    :ivar depth: the depth of the call graph, i.e., tha maximum reached level by any function
    :ivar cfg: the control flow graph structure containing list of basic blocks and edges for
                    each cg_map function
    :ivar minor: the minor version associated with the call graph resource
    :ivar recursive: the set of self-recursive functions, used in metrics computation

    """

    def __init__(self):
        """Creates a default empty Call Graph Resource object. To properly compute / set all
        values, use the appropriate from_angr / from_dict methods.
        """
        self.cg_map = {}
        self.reachable = {}
        self.backedges = {}
        self.bottom = set()
        self.top = set()
        self.levels = []
        self.leaves = []
        self.depth = 0
        self.cfg = {}
        self.minor = pcs.vcs().get_minor_head()
        # TODO: metrics
        self.recursive = set()

    def __getitem__(self, item):
        """Quick dictionary-like access to cg_map values.

        :param item: name of the function that should be retrieved

        :return: the dictionary object representing the function node
        """
        return self.cg_map[item]

    def __setitem__(self, key, value):
        """Quick dictionary-like assignment to cg_map values.

        :param key: name of the cg_map function
        :param value: the function dictionary object
        """
        self.cg_map[key] = value

    def from_angr(self, angr_cg, functions):
        """Computes the call graph resource properties based on the extracted call graph object

        :param angr_cg: the call graph dictionary extracted using angr
        :param functions: a set of function names obtained from the collection strategies

        :return: a properly initialized CGR object
        """
        self._build_cg_map(angr_cg["call_graph"], functions)
        # The DFS backedges and level estimator is currently fixed
        self._build_levels(LevelEstimator.DFS)
        self._compute_reachability()
        self._build_cfg(angr_cg["control_flow"], functions)
        return self

    def add_dyn(self, dyn_cg, old_cg, cfg):
        """Merges the dynamic call graph resource which is reconstructed from the profiling
        trace and an old call graph resource (dynamic, static, ...).
        We also use the statically obtained call graph for constructing a control flow graph.

        :param dyn_cg: the 'func': callees dictionary from the profiling run
        :param old_cg: call graph structure to update
        :param cfg: the angr CFG dictionary

        :return: a properly initialized CGR object
        """
        call_graph = {func: conf["callees"] for func, conf in old_cg.items()}
        for name, callees in dyn_cg.items():
            call_graph.setdefault(name, []).extend(callees)
            call_graph[name] = sorted(list(set(call_graph[name])))

        new_call_graph = {
            "call_graph": _remove_unreachable(call_graph),
            "control_flow": cfg,
        }
        functions = set(new_call_graph["call_graph"].keys())
        return self.from_angr(new_call_graph, functions)

    def from_dict(self, dict_cg):
        """Initializes the resource properties according to the CGR loaded from 'stats'.

        :param dict_cg: the call graph resource in a Perun storage format

        :return: the properly initialized CGR object
        """
        call_graph, cfg = dict_cg["call_graph"], dict_cg["control_flow"]
        self.cg_map = call_graph["cg_map"]
        self.recursive = set(call_graph.get("recursive", []))
        self.cfg = cfg
        # The DFS backedges and level estimator is currently fixed
        self._build_levels(LevelEstimator.DFS)
        # # Compute the reachability since it can get too big to store
        self._compute_reachability()
        self.minor = dict_cg["minor_version"]
        return self

    def get_functions(self, diff_only=False):
        """Obtain functions from the cg_map in format suitable for further processing outside the
        optimization module.

        :param diff_only: specifies whether only functions detected as changed should be listed

        :return: a dictionary of 'name': 'sample value' format
        """

        def filter_func(func):
            """The filtering function.

            :param func: the function in dictionary format
            :return: whether we should include the given function in output or not
            """
            return func["diff"] if diff_only else not func["filtered"]

        base = {"main": self.cg_map["main"]["sample"]}
        base.update(
            {func["name"]: func["sample"] for func in self.cg_map.values() if filter_func(func)}
        )
        return base

    def set_diff(self, funcs):
        """Set the diff flag to a given functions

        :param funcs: the collection of functions to set as changed
        """
        for func in funcs:
            if func in self.cg_map:
                # If the functions was already filtered, remove the flag
                self[func]["filtered"] = False
                self[func]["diff"] = True

    def get_diff(self):
        """Get list of functions with diff flag.

        :return: a collection of changed functions
        """
        return [func["name"] for func in self.cg_map.values() if func["diff"]]

    def sort_by_level(self, functions, reverse=True):
        """Sort the provided functions according to their level.

        :param functions: a collection of function names
        :param reverse: if set to True, the functions are sorted in descending order

        :return: a list of functions sorted by the level property
        """
        return sorted(
            map(lambda name: (name, self[name]["level"]), functions),
            key=lambda item: item[1],
            reverse=reverse,
        )

    def remove_or_filter(self, functions, set_filtered=True):
        """Remove functions from the CG structure if all references to the functions are gone
        (e.g., no more callers or callees). Otherwise, set the function as filtered to not break
        the CG structure (optional).

        :param functions: list of functions to remove or filter
        :param set_filtered: if set to True, functions are at least given the 'filtered' flag
        """
        funcs = self.sort_by_level(functions)
        for func_name, _ in funcs:
            # Do not remove diff functions (i.e. those that changed and should be profiled)
            if self[func_name]["diff"]:
                continue
            if not self._remove_function(func_name) and set_filtered:
                self[func_name]["filtered"] = True

    def subsumption(self, func_1, func_2):
        """Perform a subsumption check on two functions. Subsumption is defined as follows:
        f1 sub f2 <=> f1.level < f2.level AND f2 in f1.reachable

        :param func_1: name of the first function
        :param func_2: name of the second function

        :return: True if the subsumption property holds, False otherwise
        """
        if func_1 == func_2:
            return False
        res = self[func_1]["level"] < self[func_2]["level"] and func_2 in self.reachable[func_1]
        return res

    def compute_bottom(self):
        """Compute the Bottom set of the call graph. If back edges are available, leverage them
        to compute the set easily. Otherwise, leverage the subsumption operation.

        :return: the resulting Bottom set of the call graph
        """
        unfiltered_funcs = [func for func in self.cg_map.keys() if not self[func]["filtered"]]
        if self.backedges:
            self.bottom = set()
            for func in unfiltered_funcs:
                # Find callees and back edges except those that are filtered
                unfiltered_callees = [
                    callee for callee in self[func]["callees"] if not self[callee]["filtered"]
                ]
                unfiltered_backedges = [
                    be for be in self.backedges[func] if not self[be]["filtered"]
                ]
                # The node has no unfiltered callees or only back edges -> it is a bottom node
                if len(unfiltered_backedges) == len(unfiltered_callees):
                    self.bottom.add(func)
        else:
            self.bottom = set(
                func
                for func in unfiltered_funcs
                if not any(self.subsumption(func, cmp_func) for cmp_func in unfiltered_funcs)
            )
        return self.bottom

    def compute_top(self):
        """Compute the Top set of the call graph.

        First find the max cut that filters main function and functions that are the only
        callee of main and its successors. Then filter the cut functions and leverage
        subsumption to find the Top set.

        :return: the resulting Top set of the call graph
        """
        # Find the maximum cut and the corresponding excluded functions
        excluded, _ = self.coverage_max_cut()
        tested_funcs = [
            func
            for func in self.cg_map.keys()
            if func not in excluded and not self[func]["filtered"]
        ]
        # Find the maximum coverage functions
        self.top = set(
            func
            for func in tested_funcs
            if not any(self.subsumption(cmp_func, func) for cmp_func in tested_funcs)
        )
        if not self.top:
            self.top = {"main"}
        return self.top

    def coverage_max_cut(self):
        """Helper function for the Top Level Coverage Metric. Find call graph cut required to
        identify the TLC probes.

        :return: the set of functions that are not suitable for TLC and the level of
                          the CG cut
        """
        visited = {"main"}
        callees = self["main"]["callees"]
        while callees:
            # Ignore backedges and filtered functions in the possible initial call chain
            unfiltered_callees = [
                callee
                for callee in callees
                if callee not in visited and not self[callee]["filtered"]
            ]
            if len(unfiltered_callees) > 1:
                # We found the first call graph branch
                break
            if len(unfiltered_callees) == 0:
                # We ran out of functions, the call graph is thus possibly one linear call chain
                return {"main"}, 0

            # We continue through the linear call chain
            visited.add(unfiltered_callees[0])
            callees = self[unfiltered_callees[0]]["callees"]
        cut_level = max(self[func]["level"] for func in visited)
        return visited, cut_level

    def _build_cg_map(self, angr_cg, functions):
        """Creates the cg_map property using the angr_cg dictionary.

        :param angr_cg: the call graph dictionary extracted using angr
        :param functions: a set of function names obtained from the collection strategies
        """
        # Add the nodes of the call graph
        excluded = set()
        nodes = 0
        for func_name in angr_cg.keys():
            # Ignore the functions that are not present in extracted functions for now
            if not _is_in_funcs(func_name, functions):
                excluded.add(func_name)
            # Create a cg_map record
            else:
                nodes += 1
                self[func_name] = self._create_cg_node(func_name)
        # Add those excluded functions that have at least one callee that is not excluded
        # Such functions may be needed to not break the call graph structure
        for func_name in excluded:
            included_callees = [name for name in angr_cg[func_name] if name not in excluded]
            if included_callees:
                self[func_name] = self._create_cg_node(func_name, filtered=True)

        # Add the edges of the call graph
        for func_name, callees in angr_cg.items():
            # Ignore excluded functions
            if func_name in self.cg_map:
                func = self[func_name]
                # Add edges to all callees, except for self loops and excluded nodes
                for callee in callees:
                    if callee == func_name:
                        self.recursive.add(func_name)
                    if callee != func_name and callee in self.cg_map:
                        self._add_connection(func, self[callee])

    def _compute_reachability(self):
        """Compute the reachability property for all cg_map functions. We speed the computation
        thanks to the usage of levels, since we can traverse the CG in reverse order (bottom -> top)
        and build on the previously computed results
        """
        self.reachable = {func_name: set() for func_name in self.cg_map.keys()}
        # Start from the bottom levels
        for level in reversed(self.levels):
            for func in level:
                self._reachable_callees(self[func])

    def _reachable_callees(self, vertex):
        """Compute or obtain the reachability set of the 'vertex' function.

        :param vertex: the CG function dictionary with all the properties
        """
        reachable = set()
        candidates = list(vertex["callees"])
        while candidates:
            func = candidates.pop()
            # The function has already been inspected
            if func in reachable:
                continue
            # The reachability has already been computed for the function, use it
            reachable.add(func)
            if self.reachable[func]:
                reachable |= self.reachable[func]
            # Expand the function
            else:
                callees = [callee for callee in self[func]["callees"] if callee not in reachable]
                candidates.extend(callees)
        self.reachable[vertex["name"]] = reachable

    def _build_cfg(self, cfgs, functions):
        """Transforms the extracted CFG into the CGR format.

        :param cfgs: the CFG dictionaries with blocks and edges
        :param functions: a set of function obtained from a collection strategy
        """
        for func, cfg in cfgs.items():
            if func in functions:
                self.cfg[func] = cfg

    def _remove_function(self, name):
        """Attempt to remove a function from call graph.

        :param name: name of the function to remove

        :return: True if the function has been successfully removed, False otherwise
        """
        # Remove only existing leaf functions
        if name not in self.cg_map or not self[name]["leaf"]:
            return False
        func = self[name]
        # Remove the reference to the removed function from all the callers
        for caller_name in func["callers"]:
            caller = self[caller_name]
            caller["callees"].remove(name)
            # Set the caller to a leaf node if this was the last callee
            self._set_leaf(caller)
        # Remove the reference to the function from the levels structure
        self.levels[func["level"]].remove(func["name"])
        del self.cg_map[func["name"]]
        return True

    def _set_leaf(self, func):
        """Safely set the given function as leaf, i.e., only when the function is actually leaf.

        :param func: the function dictionary
        """
        if not func["callees"]:
            func["leaf"] = True
            self.leaves.append(func["name"])

    @staticmethod
    def _create_cg_node(name, filtered=False):
        """Creates new dictionary that represents a single call graph function.

        :param name: name of the function
        :param filtered: set if the node should be immediately set as filtered

        :return: the function object
        """
        return {
            "name": name,
            "level": [],
            "filtered": filtered,
            "callers": [],
            "callees": [],
            "leaf": False,
            "diff": False,
            "sample": 0,
            "complexity": Complexity.GENERIC.value,
        }

    @staticmethod
    def _add_connection(parent, callee):
        """Add 'edge' to the cg_map structure, i.e., set the caller and callee relation

        :param parent: the dictionary of the parent function
        :param callee: the dictionary of the callee function
        """
        if callee["name"] not in parent["callees"]:
            parent["callees"].append(callee["name"])
        if parent["name"] not in callee["callers"]:
            callee["callers"].append(parent["name"])


def _remove_unreachable(call_graph):
    """Removes functions from the call graph that are not reachable from the 'main' function.

    :param call_graph: a call graph dictionary

    :return: pruned call graph dictionary
    """
    iters = [{"main"}]
    visited = {"main"}

    while iters[-1]:
        current_iter = iters[-1]
        new_iter = set()
        for func in current_iter:
            func_callees = [c for c in call_graph.get(func, []) if c not in visited]
            new_iter |= set(func_callees)
            visited |= set(func_callees)
        iters.append(new_iter)

    new_angr_cg = {}
    for func, callees in call_graph.items():
        if func in visited:
            new_angr_cg[func] = list(set(callees) & visited)
    return new_angr_cg


def _is_in_funcs(func_name, functions):
    """Safely checks whether the given function is in the functions obtained from strategies

    :param func_name: name of the function
    :param functions: the set of function obtained from strategies

    :return: True if 'func_name' is in the strategy functions
    """
    if not functions:
        return True
    return func_name in functions
