"""
The Call Graph Shaping is a family of static analysis methods that exploits the structure
of CG to identify and filter functions that are, e.g. more likely to be invoked more times
than the remaining functions. Namely, we introduce three distinct Call Graph Shaping
approaches: top-down (Trimming), bottom-up (Pruning) and Matching.
"""


from perun.utils import partition_list


def call_graph_trimming(call_graph, level_thr, min_functions, keep_leaf):
    """ The Call Graph Trimming method.

    :param CallGraphResource call_graph: the CGR optimization resource
    :param int level_thr: the number of top CG levels to keep
    :param int min_functions: the minimum amount of functions that should be left after the trimming
    :param bool keep_leaf: if set to True, leaf functions will be kept during the trimming
    """

    def _check_for_leaf(candidate_func):
        """ Function that checks whether a function should be filtered or not based on the
        leaf criterion.

        :param str candidate_func: name of the candidate function

        :return bool: True if the function should not be removed
        """
        # Either we accept leaves OR we don't AND the function is not a leaf
        return keep_leaf or (not keep_leaf and not call_graph[candidate_func]['leaf'])

    keep_funcs = []
    trim_funcs = []
    coverage_mode = False
    for idx, level in enumerate(call_graph.levels):
        # The maximum specified level reached
        if idx + 1 > level_thr:
            if len(keep_funcs) >= min_functions:
                # The minimum number of functions has also been reached
                # Trim the rest of the functions
                trim_funcs.extend(level)
                continue
            # We haven't reached the required number of functions
            coverage_mode = True

        # Partition the functions in this level into those that should be kept or removed
        keep, trim = partition_list(level, _check_for_leaf)
        trim_funcs.extend(trim)

        if not coverage_mode:
            # All the remaining functions from this level should be kept
            keep_funcs.extend(keep)
        else:
            # Obtain the coverage for each function and sort the candidates according to it
            candidates = sorted(
                map(lambda func: (func, len(call_graph.reachable[func])), keep),
                key=lambda func: func[1], reverse=True
            )
            # Select the required number of functions to keep (based on their coverage value)
            # Trim the rest of them
            candidates_count = min(len(candidates), min_functions - len(keep_funcs))
            keep_funcs.extend([name for name, _ in candidates[:candidates_count]])
            trim_funcs.extend([name for name, _ in candidates[candidates_count:]])

    call_graph.remove_or_filter(trim_funcs, set_filtered=True)


def call_graph_pruning(call_graph, chain_length, keep_top):
    """ The Call Graph Pruning method.

    :param CallGraphResource call_graph: the CGR optimization resource
    :param int chain_length: the maximum length of the pruning paths
    :param int keep_top: the number of top call graph levels that will not be pruned
    """
    if chain_length == 0:
        return
    call_graph.compute_bottom()

    all_candidates = set()
    for leaf in call_graph.bottom:
        # Get the leaf and the level range in which to prune
        leaf = call_graph[leaf]
        level_max = round(leaf['level'] + chain_length / 2)
        level_min = round(leaf['level'] - chain_length / 2)

        # Skip leaves that are in the protected levels
        if leaf['level'] < keep_top:
            continue
        inspect_list = [leaf['name']]
        all_candidates.add(leaf['name'])
        leaf_candidates = {leaf['name']}
        # Iterate the callers up the call chain according to the specified chain length
        for _ in range(chain_length - 1):
            step_callers = set()
            # Get all the candidate callers, filter the protected levels and already present callers
            for candidate in inspect_list:
                callers = [
                    caller for caller in call_graph[candidate]['callers']
                    if caller not in leaf_candidates and call_graph[caller]['level'] >= keep_top
                    and level_min <= call_graph[caller]['level'] <= level_max
                ]
                step_callers |= set(callers)
            all_candidates |= step_callers
            leaf_candidates |= step_callers
            inspect_list = list(step_callers)
            # No more candidates, break the chain traversal
            if not inspect_list:
                break
    call_graph.remove_or_filter(list(all_candidates), set_filtered=True)
