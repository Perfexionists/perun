"""
Static Baseline optimization is based on the formal static analysis of the project sourcecode.
Specifically, we leverage the resource bounds analysis(with the focus on amortized complexity
analysis), which is implemented in the Perun Bounds collector: a wrapper over the
well-established Loopus tool

"""

import perun.logic.runner as runner
import perun.utils.log as log
from perun.utils.common.common_kit import get_module
from perun.collect.trace.optimizations.structs import Complexity


def complexity_filter(call_graph, sources, complexity, keep_top):
    """The Static Baseline method.

    :param CallGraphResource call_graph: the CGR optimization resource
    :param list sources: the source files of the project
    :param Complexity complexity: complexity threshold for functions to be excluded from profiling
    :param int keep_top: protected top CG levels
    """
    bounds_map = _get_complexity_classes(sources)
    if bounds_map:
        _call_graph_filter(call_graph, bounds_map, complexity, keep_top)


def _get_complexity_classes(sources):
    """Run the Perun bounds collector to gather information about inferred bounds and complexity.

    :param list sources: the collection of source files that should be compiled by the LLVM

    :return dict: a dictionary containing the parsed results of bounds collector
    """
    # Simulate the runner context by manually configured parameters and run the bounds collector
    collection_report, prof = runner.run_all_phases_for(
        get_module("perun.collect.bounds.run"), "collector", {"sources": sources}
    )
    if not collection_report.is_ok():
        log.error(f"static bounds analysis failed: {collection_report.message}", recoverable=True)
        return {}

    # parse the collector output and store the local and total bounds
    bounds_map = {}
    for resource in prof["global"]["resources"]:
        func = bounds_map.setdefault(
            resource["uid"]["function"], {"total bound": [], "local bound": []}
        )
        func[resource["type"]].append(Complexity.from_poly(resource["class"]))

    for bounds in bounds_map.values():
        if bounds["total bound"]:
            bounds["complexity"] = Complexity.max(bounds["total bound"])
        elif bounds["local bound"]:
            bounds["complexity"] = Complexity.max(bounds["local bound"])
        else:
            bounds["complexity"] = Complexity.GENERIC

    return bounds_map


def _call_graph_filter(call_graph, bounds_map, complexity, keep_top):
    """Compare the inferred complexities with the threshold and remove functions that match the
    specified complexity degree.

    :param CallGraphResource call_graph: the CGR optimization resource
    :param dict bounds_map: a dictionary containing the parsed results of bounds collector
    :param Complexity complexity: complexity threshold for functions to be excluded from profiling
    :param int keep_top: protected top CG levels
    """
    filter_list = []
    # Assign complexity to all CG functions, if we failed to infer one, use the default
    for level in reversed(call_graph.levels[keep_top:]):
        for func in level:
            func_complexity = bounds_map.get(func, {"complexity": Complexity.GENERIC})["complexity"]
            call_graph[func]["complexity"] = Complexity(func_complexity)
            # Filter functions that are below the threshold
            if func_complexity <= complexity:
                filter_list.append(func)
    call_graph.remove_or_filter(filter_list)
