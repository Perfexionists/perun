"""
We propose Dynamic Sampling - an iterative method that utilizes both the CGR and Dynamic Stats
to optimize the resulting data volume by automatically estimating the appropriate runtime
sampling value for each function, so that adequate amount of records is collected.
That is, we want to prevent certain functions from over-generating millions of performance
records and to keep sufficient amount of data records for any further post-processing and analysis.

"""

import math
from perun.collect.trace.optimizations.structs import Complexity


_SAMPLE_MAX = 2000000000  # Due to the type limitation of collection programs
_THRESHOLD_EPS_RATIO = 0.1  # The threshold eps tolerance
_CONSTANT_RATIO = 2  # The ratio applied to constant functions in the initial phase
_LINEAR_RATIO = 1.5  # The ratio applied to linear functions in the initial phase


def set_sampling(call_graph, stats, step, threshold):
    """The Dynamic Sampling method.

    :param CallGraphResource call_graph: the CGR optimization resource
    :param dict stats: the Dynamic Stats dictionary
    :param float step: the base for the exponential function that estimates sampling
    :param int threshold: the desired number of records for each profiled function
    """
    stats = {} if stats is None else stats
    # 20% of the threshold is an expected deviation (+- 10%)
    threshold_eps = threshold * _THRESHOLD_EPS_RATIO

    if threshold == 0:
        call_graph.remove_or_filter(set(call_graph.cg_map.keys()) - {"main"})
        return

    for depth, level in enumerate(call_graph.levels):
        for func in level:
            cg_func = call_graph[func]
            # Default sampling according to the level
            func_sample = round(step**depth)
            if func in stats:
                func_calls = stats[func]["sampled_count"]
                func_sample = stats[func]["sample"]
                # The number of function calls is ok, keep the sampling value
                if threshold - threshold_eps <= func_calls <= threshold + threshold_eps:
                    pass
                # Number of function calls is off, attempt to reach the threshold
                else:
                    func_sample = math.floor(func_sample / (threshold / func_calls))
                    # Normalize the value
                    func_sample = 1 if func_sample < 1 else func_sample
            else:
                if cg_func["complexity"] == Complexity.CONSTANT.value:
                    func_sample *= _CONSTANT_RATIO
                elif cg_func["complexity"] == Complexity.LINEAR.value:
                    func_sample *= _LINEAR_RATIO
            # Normalize the sampling
            if func_sample > _SAMPLE_MAX:
                func_sample = _SAMPLE_MAX
            cg_func["sample"] = func_sample
