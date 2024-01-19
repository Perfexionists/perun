"""
The Call Graph Projection is a family of static analysis methods that exploits the structure
of CG to identify and filter functions that are, e.g. more likely to be invoked more times
than the remaining functions. The CG Projection family originates in the CG Shaping and slightly
modifies some of the approaches.
"""

from perun.utils.common.common_kit import partition_list


def cg_top_down(call_graph, chain_length, keep_leaf):
    """The Call Graph Projection Top Down method.
    The method keeps only the 'chain_length' top-most levels of the call graph.

    :param CallGraphResource call_graph: the CGR optimization resource
    :param int chain_length: the number of top CG levels to keep
    :param bool keep_leaf: if set to True, leaf functions will be kept during the trimming
    """

    def _check_for_leaf(candidate_func):
        """Function that checks whether a function should be filtered or not based on the
        leaf criterion.

        :param str candidate_func: name of the candidate function

        :return bool: True if the function should not be removed
        """
        # Either we accept leaves OR we don't AND the function is not a leaf
        return keep_leaf or (not keep_leaf and not call_graph[candidate_func]["leaf"])

    keep_funcs = set()
    trim_funcs = set()
    for idx, level in enumerate(call_graph.levels):
        # The maximum specified level reached
        if idx + 1 > chain_length:
            trim_funcs |= set(level)
        else:
            # Partition the functions in this level into those that should be kept or removed
            keep, trim = partition_list(level, _check_for_leaf)
            trim_funcs |= set(trim)
            keep_funcs |= set(keep)

    call_graph.remove_or_filter(trim_funcs - {"main"}, set_filtered=True)


def cg_bottom_up(call_graph, chain_length):
    """The Call Graph Projection Bottom Up method.
    The method starts at with the set of bottom-level functions and in each iteration,
    functions that are direct callers of some function in the set are added to the set.
    Functions in the resulting set are kept and the rest of the functions is removed

    :param CallGraphResource call_graph: the CGR optimization resource
    :param int chain_length: the path length to traverse
    """
    # Check that the parameter is valid
    if chain_length == 0:
        call_graph.remove_or_filter(set(call_graph.cg_map.keys() - {"main"}), set_filtered=True)
        return
    # Compute the set of the bottom functions
    call_graph.compute_bottom()
    visited = cg_bottom_sets(call_graph, chain_length)[0]
    # Remove functions that were not added into the set
    call_graph.remove_or_filter(set(call_graph.cg_map.keys()) - visited, set_filtered=True)


def cg_bottom_sets(call_graph, chain_length=None):
    """Helper function that computes the iterative sets for each bottom function.

    :param CallGraphResource call_graph: the CGR optimization resource
    :param int chain_length: the path length to traverse

    :return tuple (set, int): set of all visited functions and maximum number of steps taken
    """
    if chain_length is None:
        chain_length = call_graph.depth

    call_graph.compute_bottom()

    max_length = 0
    visited = set()
    # We implement the method by inspecting every bottom-level function and the according callers
    # (also transitively)
    for bot in call_graph.bottom:
        bot = call_graph[bot]
        # Set the appropriate limits for the probe
        level_max = round(bot["level"] + chain_length / 2)
        level_min = round(bot["level"] - chain_length / 2)
        visited.add(bot["name"])
        # Functions that should be further inspected in the next step
        inspect = {bot["name"]}
        # Functions that can reach the bottom-level function in the specified number of steps
        bot_set = {bot["name"]}
        # Each step adds functions that call at least one of the bot_set functions
        for step in range(chain_length - 1):
            step_callers = set()
            for func in inspect:
                # Add new functions that fulfill the limits
                step_callers |= {
                    caller
                    for caller in call_graph[func]["callers"]
                    if caller not in bot_set
                    and level_min <= call_graph[caller]["level"] <= level_max
                }
            # Check if we got new callers in this step
            if not step_callers:
                # If not, compute the maximum number of steps needed for closure
                max_length = max(max_length, step)
                break
            inspect = step_callers
            bot_set |= step_callers
            visited |= step_callers

    return visited, max_length
