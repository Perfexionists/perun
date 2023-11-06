"""
Dynamic baseline optimization is an iterative method that leverages metrics gathered from
previous collection runs (stored in the Dynamic Stats) of the same command configuration,
i.e. the collection command (profiled executable), its arguments and workload - however,
not necessarily the same optimization settings. In particular, the method attempts to
identify functions that can be omitted from subsequent profiling.
"""


_CONSTANT_MEDIAN_RATIO = 0.05
_MEDIAN_RESOLUTION = 10
_WRAPPER_THRESHOLD_RATIO = 0.8


def filter_functions(call_graph, stats_map, checks):
    """The Dynamic Baseline method.

    :param CallGraphResource call_graph: the CGR optimization resource
    :param dict stats_map: the Dynamic Stats resource
    :param list checks: the list of checks to run
    """
    filtered_funcs = []
    changes = call_graph.get_diff()
    for func_name in stats_map.keys():
        # Do not filter functions that have been changed since the last baseline
        # Their change in (performance) behaviour is not easily predictable
        if func_name in changes or func_name not in call_graph.cg_map:
            continue

        # Run all the check functions
        for check_f, check_threshold in checks:
            if check_f(
                call_graph=call_graph,
                stats=stats_map,
                func=func_name,
                threshold=check_threshold,
            ):
                filtered_funcs.append(func_name)
                break

    # Finally remove the filtered functions
    call_graph.remove_or_filter(filtered_funcs)


def call_limit_filter(stats, func, threshold, **_):
    """Checks whether the call limit has exceeded the hard threshold.

    :param dict stats: the Dynamic Stats resource
    :param str func: name of the checked function
    :param int threshold: the threshold to compare to

    :return bool: True if the function should be filtered, False otherwise
    """
    return stats[func]["count"] > threshold


def constant_filter(stats, func, threshold, **_):
    """Checks whether the call limit has exceeded the soft threshold and moreover, if the
    function shows a constant-like behaviour.

    :param dict stats: the Dynamic Stats resource
    :param str func: name of the checked function
    :param int threshold: the threshold to compare to

    :return bool: True if the function should be filtered, False otherwise
    """
    calls, iqr, median = stats[func]["count"], stats[func]["IQR"], stats[func]["median"]
    return (calls > threshold) and (
        iqr < median * _CONSTANT_MEDIAN_RATIO or median <= _MEDIAN_RESOLUTION
    )


def wrapper_filter(call_graph, func, stats, **_):
    """Inspects all callers of the given function and checks if the wrapper-wrapped conditions
    are met - if as much as a single caller does not meet the requirements, we do not filter the
    function.

    :param CallGraphResource call_graph: the CGR optimization resource
    :param dict stats: the Dynamic Stats resource
    :param str func: name of the checked function

    :return bool: True if the function should be filtered, False otherwise
    """
    # Inspect all func callers
    calls, median = stats[func]["count"], stats[func]["median"]
    callers = call_graph[func]["callers"]
    if len(callers) < 1:
        return False
    for parent in callers:
        # The parent might not have any records
        if parent not in stats:
            return False
        # Check if all callers satisfy the wrapper constraints
        p_callees, parent_median = (
            call_graph[parent]["callees"],
            stats[parent]["median"],
        )
        if (
            stats[parent]["count"] != calls
            or len(p_callees) != 1
            or func != p_callees[0]
            or median < parent_median * _WRAPPER_THRESHOLD_RATIO
        ):
            return False
    # All of the callers satisfy the constraints, func is wrapped
    return True
