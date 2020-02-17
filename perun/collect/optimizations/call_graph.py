""" A module that implements the Call Graph Resource and all related operations needed for
easy manipulation with its structure.

The Call Graph Structure stores the extracted call graph as well as the control flow graph.
"""


import perun.vcs as vcs
from perun.collect.optimizations.structs import Complexity


class CallGraphResource:
    """ The call graph resource class with all the additional properties.

    :ivar dict cg_map: a dictionary with all the call graph nodes,
                       i.e., structures that represent functions
    :ivar dict reachable: a list of reachable functions computed for each cg_map function
    :ivar list levels: a list containing lists of functions that have the same 'level' estimation,
                       the list index is also the level value
    :ivar list leaves: a list of leaf function names
    :ivar int depth: the depth of the call graph, i.e., tha maximum reached level by any function
    :ivar dict cfg: the control flow graph structure containing list of basic blocks and edges for
                    each cg_map function
    :ivar str minor: the minor version associated with the call graph resource
    :ivar set recursive: the set of self-recursive functions, used in metrics computation

    """
    def __init__(self):
        """ Creates a default empty Call Graph Resource object. To properly compute / set all
        values, use the appropriate from_angr / from_dict methods.
        """
        self.cg_map = {}
        self.reachable = {}
        self.levels = []
        self.leaves = []
        self.depth = 0
        self.cfg = {}
        self.minor = vcs.get_minor_head()
        # TODO: metrics
        self.recursive = set()

    def __getitem__(self, item):
        """ Quick dictionary-like access to cg_map values.

        :param str item: name of the function that should be retrieved

        :return dict: the dictionary object representing the function node
        """
        return self.cg_map[item]

    def __setitem__(self, key, value):
        """ Quick dictionary-like assignment to cg_map values.

        :param str key: name of the cg_map function
        :param dict value: the function dictionary object
        """
        self.cg_map[key] = value

    def from_angr(self, angr_cg, functions):
        """ Computes the call graph resource properties based on the extracted call graph object

        :param dict angr_cg: the call graph dictionary extracted using angr
        :param set functions: a set of function names obtained from the collection strategies

        :return CallGraphResource: the properly initialized CGR object
        """
        self._build_cg_map(angr_cg['call_graph'], functions)
        self._build_levels()
        self._compute_reachability()
        self._build_cfg(angr_cg['control_flow'], functions)
        return self

    def from_dict(self, dict_cg):
        """ Initializes the resource properties according to the CGR loaded from 'stats'.

        :param dict dict_cg: the call graph resource in a Perun storage format

        :return CallGraphResource: the properly initialized CGR object
        """
        call_graph, cfg = dict_cg['call_graph'], dict_cg['control_flow']
        self.cg_map = call_graph['cg_map']
        self.levels = call_graph['levels']
        self.leaves = call_graph['leaves']
        self.recursive = set(call_graph.get('recursive', []))
        self.depth = call_graph['depth']
        self.cfg = cfg
        self.minor = dict_cg['minor_version']
        # Compute the reachability since it can get too big to store
        self._compute_reachability()
        return self

    def _build_cg_map(self, angr_cg, functions):
        """ Creates the cg_map property using the angr_cg dictionary.

        :param dict angr_cg: the call graph dictionary extracted using angr
        :param set functions: a set of function names obtained from the collection strategies
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
        edges = 0
        for func_name, callees in angr_cg.items():
            # Ignore excluded functions
            if func_name in self.cg_map:
                func = self[func_name]
                # Add edges to all callees, except for self loops and excluded nodes
                for callee in callees:
                    edges += 1
                    if callee == func_name:
                        self.recursive.add(func_name)
                    if callee != func_name and callee in self.cg_map:
                        self._add_connection(func, self[callee])

    def _build_levels(self):
        """ Computes the levels property of CGR using a longest path estimator.
        """
        # Estimate the levels of the nodes
        self._estimate_level()
        # Build the level lists
        self.depth = max(self.cg_map.values(), key=lambda item: item['level'])['level']
        self.levels = [[] for _ in range(self.depth + 1)]
        # Assign the functions to the level lists
        for func_name, func_config in self.cg_map.items():
            # Register the call graph function as a leaf if it has no callees
            self._set_leaf(func_config)
            # Keep a reference to the function in the appropriate level
            self.levels[func_config['level']].append(func_name)

    def _estimate_level(self):
        """ The longest path length estimator. Since LP is a NP-complete problem, we leverage a
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
        tested = {'nodes': {}, 'levels': {}}

        self['main']['level'] = 0
        # Inspect list keeps track of caller -> callee pairs to inspect in a BFS fashion
        inspect_list = [('main', callee, 0) for callee in self['main']['callees']]
        while inspect_list:
            # Get the next candidate to expand
            parent, callee, level = inspect_list.pop(0)
            parent_visited = visited_pairs.setdefault(parent, [])
            # Avoid duplicate checks (caused e.g. by loops)
            if callee not in parent_visited and callee not in finished:
                # Add new level candidate based on the caller level
                parent_visited.append(callee)
                callee_node = self[callee]
                callee_node['level'].append(level)
                # Update the tested records
                _update_tested(tested, callee_node, parent)

                # If all the callers have been already inspected, set the level to its maximum
                if len(callee_node['level']) == len(callee_node['callers']):
                    # callee_node['level'] = max(callee_node['level'])
                    self._set_level(callee_node)
                    finished.add(callee)
                    # Expand the callees to be inspected as well, if any
                    if callee_node['callees']:
                        inspect_list.extend(
                            (callee, callee_callee, callee_node['level'])
                            for callee_callee in callee_node['callees']
                        )
            # There can still be some functions that were not assigned a level since not all of the
            # callers were inspected - this means that there is a cycle in the call graph and
            # we break it by finding an unfinished function with the lowest level estimate (i.e.
            # not all of the callers were inspected yet and thus the level is not accurate)
            # and setting the function as finished (thus setting the level estimate as the final
            # level value), which generates new records for the inspect list - if the function has
            # any callees.
            while not inspect_list:
                if not self._expand_candidate(tested, finished, inspect_list):
                    break

    def _expand_candidate(self, tested, finished, inspect_list):
        """ Find unresolved function that is the best candidate for breaking the loop in CG. We
        select functions that have the currently lowest level estimate, since they might cause a
        domino effect by subsequently breaking other cycles.

        :param dict tested: an internal structure that keeps track of the fully unresolved functions
        :param set finished: a set of already fully resolved functions
        :param list inspect_list: the set of functions that are queued for further expansion

        :return bool: True if we managed to find and process a candidate, False otherwise
        """
        # No more candidates, every function should have a valid level estimate
        if not tested['levels']:
            return False
        # Get the next candidate
        candidate_level = min(tested['levels'].keys())
        candidate = sorted(list(tested['levels'][candidate_level]))[0]
        # Delete it from the tested dictionary
        _delete_from_levels(tested['levels'], candidate_level, candidate)
        del tested['nodes'][candidate]
        # Set the node as finished and expand the candidate into the inspect list
        node = self[candidate]
        self._set_level(node)
        # node['level'] = candidate_level
        finished.add(candidate)
        inspect_list.extend([(candidate, callee, node['level']) for callee in node['callees']])
        return True

    def _set_level(self, node):
        """ Assigns a level value to the supplied node, i.e., function.

        We set the level according to the maximum caller and callee level (to avoid e.g., two
        functions that call one another on the same level).

        :param dict node: the object representing a CG function
        """
        callers_max = max(node['level'])
        # Inspect the callees, however, they might or might not be already resolved
        callee_max = []
        for callee in node['callees']:
            callee_level = self[callee]['level']
            if isinstance(callee_level, int):
                callee_max.append(callee_level)
            else:
                if callee_level:
                    callee_max.append(max(callee_level))
        # Set the level as the maximum of callers and callees + 1
        callee_max = max(callee_max) if callee_max else callers_max
        node['level'] = max(callers_max, callee_max) + 1

    def _compute_reachability(self):
        """ Compute the reachability property for all cg_map functions. We speed the computation
        thanks to the usage of levels, since we can traverse the CG in reverse order (bottom -> top)
        and build on the previously computed results
        """
        self.reachable = {func_name: set() for func_name in self.cg_map.keys()}
        # Start from the bottom levels
        for level in reversed(self.levels):
            for func in level:
                self._reachable_callees(self[func])

    def _reachable_callees(self, vertex):
        """ Compute or obtain the reachability set of the 'vertex' function.

        :param dict vertex: the CG function dictionary with all the properties
        """
        reachable = set()
        candidates = [callee for callee in vertex['callees']]
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
                callees = [callee for callee in self[func]['callees'] if callee not in reachable]
                candidates.extend(callees)
        self.reachable[vertex['name']] = reachable

    def _build_cfg(self, cfgs, functions):
        """ Transforms the extracted CFG into the CGR format.

        :param dict cfgs: the CFG dictionaries with blocks and edges
        :param set functions: a set of function obtained from a collection strategy
        """
        for func, cfg in cfgs.items():
            if func in functions:
                self.cfg[func] = cfg

    def get_functions(self, diff_only=False):
        """ Obtain functions from the cg_map in format suitable for further processing outside the
        optimization module.

        :param bool diff_only: specifies whether only functions detected as changed should be listed

        :return dict: a dictionary of 'name': 'sample value' format
        """
        def filter_func(func):
            """ The filtering function.

            :param dict func: the function in dictionary format
            :return bool: whether we should include the given function in output or not
            """
            return func['diff'] or func['name'] == 'main' if diff_only else not func['filtered']

        return {
            func['name']: func['sample'] for func in self.cg_map.values() if filter_func(func)
        }

    def set_diff(self, funcs):
        """ Set the diff flag to a given functions

        :param list funcs: the collection of functions to set as changed
        """
        for func in funcs:
            if func in self.cg_map:
                # If the functions was already filtered, remove the flag
                self[func]['filtered'] = False
                self[func]['diff'] = True

    def get_diff(self):
        """ Get list of functions with diff flag.

        :return list: a collection of changed functions
        """
        return [func['name'] for func in self.cg_map.values() if func['diff']]

    def sort_by_level(self, functions, reverse=True):
        """ Sort the provided functions according to their level.

        :param list functions: a collection of function names
        :param bool reverse: if set to True, the functions are sorted in descending order

        :return list: a list of functions sorted by the level property
        """
        return sorted(
            map(lambda name: (name, self[name]['level']), functions),
            key=lambda item: item[1], reverse=reverse
        )

    def remove_or_filter(self, functions, set_filtered=True):
        """ Remove functions from the CG structure if all references to the functions are gone
        (e.g., no more callers or callees). Otherwise, set the function as filtered to not break
        the CG structure (optional).

        :param list functions: list of functions to remove or filter
        :param bool set_filtered: if set to True, functions are at least given the 'filtered' flag
        """
        funcs = self.sort_by_level(functions)
        for func_name, _ in funcs:
            # Do not remove diff functions (i.e. those that changed and should be profiled)
            if self[func_name]['diff']:
                continue
            if not self._remove_function(func_name) and set_filtered:
                self[func_name]['filtered'] = True

    def subsumption(self, func_1, func_2):
        """ Perform a subsumption check on two functions. Subsumption is defined as follows:
        f1 sub f2 <=> f1.level < f2.level AND f2 in f1.reachable

        :param str func_1: name of the first function
        :param str func_2: name of the second function

        :return bool: True if the subsumption property holds, False otherwise
        """
        if func_1 == func_2:
            return False
        res = self[func_1]['level'] < self[func_2]['level'] and func_2 in self.reachable[func_1]
        return res

    def coverage_max_cut(self):
        """ Helper function for the Top Level Coverage Metric. Find call graph cut required to
        identify the TLC probes.

        :return set, int: the set of functions that are not suitable for TLC and the level of
                          the CG cut
        """
        visited = {'main'}
        callees = self['main']['callees']
        while callees:
            # Ignore backedges in the possible initial call chain
            filtered_callees = [callee for callee in callees if callee not in visited]
            if len(filtered_callees) > 1:
                # We found the first call graph branch
                cut_level = max(self[func]['level'] for func in visited)
                return visited, cut_level
            elif len(filtered_callees) == 0:
                # We ran out of functions, the call graph is thus possibly one linear call chain
                return {'main'}, 0
            else:
                # We continue through the linear call chain
                visited.add(filtered_callees[0])
                callees = self[filtered_callees[0]]['callees']
        cut_level = max(self[func]['level'] for func in visited)
        return visited, cut_level

    def _remove_function(self, name):
        """ Attempt to remove a function from call graph.

        :param str name: name of the function to remove

        :return bool: True if the function has been successfully removed, False otherwise
        """
        # Remove only existing leaf functions
        if name not in self.cg_map or not self[name]['leaf']:
            return False
        func = self[name]
        # Remove the reference to the removed function from all the callers
        for caller_name in func['callers']:
            caller = self[caller_name]
            caller['callees'].remove(name)
            # Set the caller to a leaf node if this was the last callee
            self._set_leaf(caller)
        # Remove the reference to the function from the levels structure
        self.levels[func['level']].remove(func['name'])
        del self.cg_map[func['name']]
        return True

    def _set_leaf(self, func):
        """ Safely set the given function as leaf, i.e., only when the function is actually leaf.

        :param dict func: the function dictionary
        """
        if not func['callees']:
            func['leaf'] = True
            self.leaves.append(func['name'])

    @staticmethod
    def _create_cg_node(name, filtered=False):
        """ Creates new dictionary that represents a single call graph function.

        :param str name: name of the function
        :param bool filtered: set if the node should be immediately set as filtered

        :return dict: the function object
        """
        return {
            'name': name,
            'level': [],
            'filtered': filtered,
            'callers': [],
            'callees': [],
            'leaf': False,
            'diff': False,
            'sample': 0,
            'complexity': Complexity.Generic.value
        }

    @staticmethod
    def _add_connection(parent, callee):
        """ Add 'edge' to the cg_map structure, i.e., set tha caller and callee relation

        :param dict parent: the dictionary of the parent function
        :param dict callee: the dictionary of the callee function
        """
        if callee['name'] not in parent['callees']:
            parent['callees'].append(callee['name'])
        if parent['name'] not in callee['callers']:
            callee['callers'].append(parent['name'])


def _is_in_funcs(func_name, functions):
    """ Safely checks whether the given function is in the functions obtained from strategies

    :param str func_name: name of the function
    :param set functions: the set of function obtained from strategies

    :return bool: True if 'func_name' is in the strategy functions
    """
    if not functions:
        return True
    return func_name in functions


def _update_tested(tested, node, caller):
    """ Update the internal structure that keeps track of candidates and their levels in a
    fast-access structure.

    :param dict tested: the helper structure used during computing the CG levels property
    :param dict node: the updated function, supplied as dictionary
    :param str caller: the caller context, i.e., name of the caller function
    """
    # Get the node and levels structures
    levels = tested['levels']
    tested_node = tested['nodes'].setdefault(
        node['name'], {'level': -1, 'callers': list(node['callers'])}
    )
    # Remove the caller from the node record
    if caller in tested_node['callers']:
        tested_node['callers'].remove(caller)
        # Remove the tested record if no more callers are remaining
        if not tested_node['callers']:
            _delete_from_levels(levels, tested_node['level'], node['name'])
            del tested['nodes'][node['name']]
            return

    # Reassign the node to a new minimum level
    old_level = tested_node['level']
    new_level = max(node['level'])
    if new_level > old_level:
        tested_node['level'] = new_level
        # Remove the old level association
        _delete_from_levels(levels, old_level, node['name'])
        # Add the node to the new corresponding level
        levels.setdefault(new_level, set()).add(node['name'])


def _delete_from_levels(levels, level, name):
    """ Delete the specified function from the helper levels structure for candidates.

    :param list levels: a list structure that bundles and keeps track of candidate levels
    :param int level: the level containing the function to remove
    :param str name: name of the function to remove
    """
    if level != -1:
        levels[level].discard(name)
        # Remove the entire level category if no more records are there
        if not levels[level]:
            del levels[level]
