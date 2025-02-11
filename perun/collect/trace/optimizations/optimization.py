"""The new Perun architecture extension that handles the optimization routine."""

import collections

from perun.utils.common.common_kit import sanitize_filepart
from perun.utils.exceptions import SuppressedExceptions
from perun.collect.trace.optimizations.structs import (
    ParametersManager,
    CGShapingMode,
)
from perun.utils.structs.collect_structs import Optimizations, Pipeline, Parameters, CallGraphTypes
import perun.collect.trace.optimizations.resources.manager as resources
from perun.collect.trace.optimizations.call_graph import CallGraphResource
import perun.collect.trace.optimizations.cg_projection as proj
import perun.collect.trace.optimizations.dynamic_baseline as dbase
import perun.collect.trace.optimizations.static_baseline as sbase
import perun.collect.trace.optimizations.diff_tracing as diff
import perun.collect.trace.optimizations.dynamic_sampling as sampling
from perun.collect.trace.optimizations.dynamic_stats import DynamicStats
import perun.utils.metrics as metrics


SPECIAL_CALL_COUNT = 101


# TODO: classify (metrics) functions as private / public
class CollectOptimization:
    """A class that stores the optimization context and implements the core of the
    optimization architecture.

    :ivar selected_pipeline: the active pipeline selected by the user
    :ivar pipeline: the resulting set of optimization methods created from combining the
                         specified pipeline, enabled and disabled methods
    :ivar params: the collection of optimization parameters
    :ivar resource_cache: specifies whether the optimization should use cache or not
    :ivar reset_cache: specifies whether new resources should be extracted and computed for
                            the current project version
    :ivar call_graph: and CFG structures of the current project version
    :ivar call_graph_old: CG and CFG structures of the previously profiled version
    :ivar dynamic_stats: the Dynamic Stats resource, if available
    """

    # The classification of methods to their respective optimization phases
    __pre = {
        Optimizations.DIFF_TRACING,
        Optimizations.CALL_GRAPH_SHAPING,
        Optimizations.BASELINE_STATIC,
        Optimizations.BASELINE_DYNAMIC,
        Optimizations.DYNAMIC_SAMPLING,
        Optimizations.TIMED_SAMPLING,
    }
    __run = {Optimizations.DYNAMIC_PROBING, Optimizations.TIMED_SAMPLING}
    __post = {Optimizations.BASELINE_DYNAMIC, Optimizations.DYNAMIC_SAMPLING}

    def __init__(self):
        """Construct and initialize the instance"""
        self.selected_pipeline = Pipeline(Pipeline.default())
        self.pipeline = []
        self._optimizations_on = []
        self._optimizations_off = []
        self.params = ParametersManager()
        self.current_workload = None

        self.cg_stats_name = None
        self.dynamic_stats_name = None
        self.resource_cache = True
        self.reset_cache = False
        self.call_graph_type = CallGraphTypes.STATIC
        self.call_graph = None
        self.call_graph_old = None
        self.dynamic_stats = DynamicStats()

    def set_pipeline(self, pipeline_name):
        """Set the used Pipeline.

        :param pipeline_name: name of the user-specified pipeline
        """
        self.selected_pipeline = Pipeline(pipeline_name)

    def enable_optimization(self, optimization_name):
        """Enable certain optimization technique.

        :param optimization_name: name of the optimization method
        """
        self._optimizations_on.append(Optimizations(optimization_name))

    def disable_optimization(self, optimization_name):
        """Disable certain optimization technique.

        :param optimization_name: name of the optimization method
        """
        self._optimizations_off.append(Optimizations(optimization_name))

    def get_pre_optimizations(self):
        """Create the set intersection of created pipeline and pre-optimize methods

        :return: the resulting set of optimization methods to run
        """
        return set(self.pipeline) & self.__pre

    def get_run_optimizations(self):
        """Create the set intersection of created pipeline and run-optimize methods

        :return: the resulting set of optimization methods to run
        """
        return set(self.pipeline) & self.__run

    def get_post_optimizations(self):
        """Create the set intersection of created pipeline and post-optimize methods

        :return: the resulting set of optimization methods to run
        """
        return set(self.pipeline) & self.__post

    def build_pipeline(self, config):
        """Build the pipeline of actually enabled optimization methods from combining the
        selected pipeline, enabled and disabled optimizations.

        :param config: the collection configuration object
        """
        if self.pipeline and config.executable.workload == self.current_workload:
            return

        if self.current_workload is None:
            self.current_workload = config.executable.workload
        # Workloads can change when e.g., workload generators are used
        if config.executable.workload != self.current_workload:
            self.current_workload = config.executable.workload
            # We need to update the dynamic stats file
            self.cg_stats_name, self.dynamic_stats_name = build_stats_names(
                config, self.call_graph_type
            )
            self._load_dynamic_stats()
            return

        self.pipeline = self.selected_pipeline.map_to_optimizations()

        opt_on = set(self._optimizations_on)
        opt_off = set(self._optimizations_off)

        for optimization in opt_on - opt_off:
            self.pipeline.append(optimization)

        for optimization in opt_off - opt_on:
            with SuppressedExceptions(ValueError):
                self.pipeline.remove(optimization)

        # If no optimizations are selected, skip
        if not self.pipeline and not config.cg_extraction:
            return

        # Otherwise prepare the necessary resources
        self.load_resources(config)

        # Infer the optimization parameters
        self.params.infer_params(self.call_graph, self.selected_pipeline, config.get_target())

    def load_resources(self, config):
        """Extract, load and store resources necessary for the given pipeline.

        :param config: the collection configuration object
        """
        # TODO: temporary hack
        old_cg_version = None
        for param_name, param_value in self.params.cli_params:
            if param_name == Parameters.DIFF_VERSION:
                old_cg_version = param_value

        metrics.start_timer("optimization_resources")
        all_funcs = config.get_functions()
        self.cg_stats_name, self.dynamic_stats_name = build_stats_names(
            config, self.call_graph_type
        )
        # cg_stats_name = config.get_stats_name('call_graph')
        if self.get_pre_optimizations() or config.cg_extraction:
            # Extract call graph of the profiled binary
            _cg = resources.extract(
                resources.Resources.CALL_GRAPH_ANGR,
                stats_name=self.cg_stats_name,
                binary=config.get_target(),
                libs=config.libs,
                cache=self.resource_cache and not self.reset_cache,
            )
            # Based on the cache we might have obtained the cached call graph or extracted a new one
            if "minor_version" in _cg:
                self.call_graph = CallGraphResource().from_dict(_cg)
            else:
                self.call_graph = CallGraphResource().from_angr(_cg, all_funcs.keys())

            # Save the extracted call graph before it is modified by the optimization methods
            resources.store(
                resources.Resources.PERUN_CALL_GRAPH,
                stats_name=self.cg_stats_name,
                call_graph=self.call_graph,
                cache=self.resource_cache and not self.reset_cache,
            )
            # TODO: temporary
            if config.cg_extraction:
                raise NotImplementedError("CG extracted OK")

            # Get call graph of the same binary but from the previous project version (if it exists)
            if old_cg_version != self.call_graph.minor:
                call_graph_old = resources.extract(
                    resources.Resources.PERUN_CALL_GRAPH,
                    stats_name=self.cg_stats_name,
                    exclude_self=True,
                    vcs_version=old_cg_version,
                )
                if call_graph_old:
                    self.call_graph_old = CallGraphResource().from_dict(call_graph_old)
        # Get dynamic stats from previous profiling, if there was any
        self._load_dynamic_stats()
        metrics.end_timer("optimization_resources")

    def _load_dynamic_stats(self):
        """Load Dynamic Stats Resource from previous profiling, if there was any."""
        self.dynamic_stats = resources.extract(
            resources.Resources.PERUN_STATS,
            stats_name=self.dynamic_stats_name,
            reset_cache=self.reset_cache,
        )

    def pre_optimize_pipeline(self, config, **_):
        """Run the pre-optimize methods in the defined order.

        :param config: the collection configuration object
        """
        optimizations = self.get_pre_optimizations()
        # No optimizations enabled
        if not optimizations:
            return

        metrics.start_timer("pre-optimize")
        # perform the diff tracing
        if Optimizations.DIFF_TRACING in optimizations:
            diff.diff_tracing(
                self.call_graph,
                self.call_graph_old,
                self.params[Parameters.DIFF_KEEP_LEAF],
                self.params[Parameters.DIFF_INSPECT_ALL],
                self.params[Parameters.DIFF_CG_MODE],
            )

        # Perform the call graph shaping
        if Optimizations.CALL_GRAPH_SHAPING in optimizations:
            mode = self.params[Parameters.CG_SHAPING_MODE]
            if mode == CGShapingMode.MATCH:
                # The match mode simply uses the call graph functions
                pass
            elif mode == CGShapingMode.BOTTOM_UP:
                proj.cg_bottom_up(self.call_graph, self.params[Parameters.CG_PROJ_LEVELS])
            elif mode == CGShapingMode.TOP_DOWN:
                proj.cg_top_down(
                    self.call_graph,
                    self.params[Parameters.CG_PROJ_LEVELS],
                    self.params[Parameters.CG_PROJ_KEEP_LEAF],
                )

        # Perform the static baseline
        if Optimizations.BASELINE_STATIC in optimizations:
            sbase.complexity_filter(
                self.call_graph,
                self.params[Parameters.SOURCE_FILES],
                self.params[Parameters.STATIC_COMPLEXITY],
                self.params[Parameters.STATIC_KEEP_TOP],
            )

        checks = [
            (dbase.call_limit_filter, self.params[Parameters.DYNBASE_HARD_THRESHOLD]),
            (dbase.constant_filter, self.params[Parameters.DYNBASE_SOFT_THRESHOLD]),
            (dbase.wrapper_filter, 0),
        ]
        if Optimizations.BASELINE_DYNAMIC in optimizations:
            dbase.filter_functions(self.call_graph, self.dynamic_stats.global_stats, checks)
        if Optimizations.DYNAMIC_SAMPLING in optimizations:
            sampling.set_sampling(
                self.call_graph,
                self.dynamic_stats.global_stats,
                self.params[Parameters.DYNSAMPLE_STEP],
                self.params[Parameters.DYNSAMPLE_THRESHOLD],
            )

        # Extract the remaining functions from the call graph - these should be probed
        diff_solo = len(optimizations) == 1 and Optimizations.DIFF_TRACING in optimizations
        # If only diff tracing is on, probe only the changed functions
        remaining_func = self.call_graph.get_functions(diff_only=diff_solo)
        config.prune_functions(remaining_func)
        metrics.end_timer("pre-optimize")
        metrics.add_metric("funcs", list(remaining_func.keys()))

    def run_optimize_pipeline(self, config, **_):
        """The "run" pipeline cannot properly run the run-phase optimizations since the
        implementation details are up to each specific engine. Instead, we set the
        requested optimizations and their parameters in the Configuration object.

        :param config: the collection configuration object
        """
        # Create a dictionary of parameters and values, they need to be serializable
        run_optimization_parameters = {
            Parameters.TIMEDSAMPLE_FREQ.value: self.params[Parameters.TIMEDSAMPLE_FREQ],
            Parameters.PROBING_REATTACH.value: self.params[Parameters.PROBING_REATTACH],
            Parameters.PROBING_THRESHOLD.value: self.params[Parameters.PROBING_THRESHOLD],
        }
        # Set the optimization methods and their parameters
        config.set_run_optimization(
            [opt.value for opt in self.get_run_optimizations()],
            run_optimization_parameters,
        )

    def post_optimize_pipeline(self, config, **_):
        """Run the post-optimize methods in the defined order.

        :param config: the collection configuration object
        """
        # Get the set of post-optimize methods
        optimizations = self.get_post_optimizations()
        if optimizations or metrics.is_enabled():
            metrics.start_timer("post-optimize")
            # Create the dynamic stats from the profile, if necessary
            self.dynamic_stats = DynamicStats.from_profile(
                config.stats_data, config.get_functions()
            )
            if metrics.is_enabled():
                self._call_graph_level_assumption()
                self._coverage_metric()
                self._collected_points_metric()
                self._level_time_metric()
                self._level_i_metric()
            # Store the gathered Dynamic Stats
            resources.store(
                resources.Resources.PERUN_STATS,
                stats_name=self.dynamic_stats_name,
                dynamic_stats=self.dynamic_stats,
                no_update=config.no_ds_update,
            )
            metrics.end_timer("post-optimize")

    def _level_i_metric(self):
        """Helper function for computing Level_i metrics, such as callee / caller exclusive times."""
        lvl_coverage = {}
        for tid, funcs in self.dynamic_stats.per_thread.items():
            lvl_coverage[tid] = {}
            for lvl, lvl_funcs in enumerate(self.call_graph.levels):
                # Ignore levels that were filtered
                if all(self.call_graph[func]["filtered"] for func in lvl_funcs):
                    continue
                lvl_coverage[tid][lvl] = {
                    "caller_exc": self._caller_callee_exc(lvl_funcs, funcs, "callers"),
                    "callee_exc": self._caller_callee_exc(lvl_funcs, funcs, "callees"),
                }
        metrics.add_metric("level_coverage", lvl_coverage)

    def _caller_callee_exc(self, level_funcs, funcs, target):
        """Compute exclusive time for immediate callers or callees.

        :param level_funcs: list of functions in the given call graph level
        :param funcs: function statistics
        :param target: identifies the target of the exclusive time computation.

        :return: the total exclusive time of immediate callers or callees
        """
        immediate_targets = {c for func in level_funcs for c in self.call_graph[func][target]}
        return sum(
            funcs.get(c, {"total_exclusive": 0})["total_exclusive"] for c in immediate_targets
        )

    def _level_time_metric(self):
        """Helper function for computing level time metrics, such as Call Graph level exclusive
        time and its breakdown into specific functions within the level.
        """
        level_time = collections.defaultdict(lambda: collections.defaultdict(int))
        exclusive_level_time = collections.defaultdict(lambda: collections.defaultdict(int))
        level_funcs = collections.defaultdict(lambda: collections.defaultdict(list))

        max_calls = (None, 0, 0)
        for tid, funcs in self.dynamic_stats.per_thread.items():
            for func_name, func_stats in funcs.items():
                func_cg_level = self.call_graph[func_name]["level"]
                level_time[tid][func_cg_level] += func_stats["total"]
                exclusive_level_time[tid][func_cg_level] += func_stats["total_exclusive"]
                level_funcs[tid][func_cg_level].append(
                    (
                        func_name,
                        func_stats["total_exclusive"],
                        func_stats["sampled_count"],
                        func_stats["sample"],
                        int(func_stats["total"]),
                    )
                )
                if func_stats["sampled_count"] > max_calls[1]:
                    max_calls = (func_name, func_stats["sampled_count"], func_cg_level)
        max_bu_length = proj.cg_bottom_sets(self.call_graph)[1]
        metrics.add_metric("cg_level_times_exclusive", exclusive_level_time)
        metrics.add_metric("cg_level_funcs", level_funcs)
        metrics.add_metric("max_calls", max_calls)
        metrics.add_metric("max_bu_length", max_bu_length)

    def _coverage_metric(self):
        """Helper function for computing the coverage metrics. Coverage metrics are
        computed for each thread separately - however, for single-threaded applications,
        the threads effectively represent processes.
        """
        if self.call_graph is None:
            return

        threads = self.dynamic_stats.threads
        metrics.add_metric("process_hierarchy", self.dynamic_stats.process_hierarchy)

        # A) Obtain the absolute hotspot coverage as extracted directly from the trace
        coverages_metrics = metrics.read_metric("coverages")

        for tid, coverages in coverages_metrics.items():
            if tid not in threads:
                continue

            tid_stats = self.dynamic_stats.per_thread[tid]
            # The total running time of a thread is a) duration of main, or b) the whole thread
            if "main" in tid_stats:
                main_time = tid_stats["main"]["total"]
            else:
                main_time = threads[tid][1]
            # B) Compute the top-level and min coverages using the CG structure
            # Identify functions that have not been measured by the process / thread
            excluded = set(self.call_graph.cg_map.keys()) - set(tid_stats.keys())
            for func, f_stats in tid_stats.items():
                # Exclude functions that are recursive or exceed the total running time of main
                if func in self.call_graph.recursive or f_stats["total"] > main_time:
                    excluded.add(func)
            # Set them as filtered but remember them, we need to set them back later
            filtered = set()
            for func in excluded:
                if not self.call_graph[func]["filtered"]:
                    filtered.add(func)
                self.call_graph[func]["filtered"] = True
            min_coverage_funcs = self.call_graph.compute_bottom()
            toplevel_funcs = self.call_graph.compute_top()
            # Compute the coverage
            min_coverage = sum(tid_stats[f]["total"] for f in min_coverage_funcs)
            toplevel_coverage = sum(tid_stats[f]["total"] for f in toplevel_funcs)
            # Update the coverage
            coverages.update(
                {
                    "main": main_time,
                    "min_coverage_count": len(min_coverage_funcs),
                    "min_coverage_abs": min_coverage,
                    "min_coverage_relative": 1 - min_coverage / main_time,
                    "toplevel_coverage_count": len(toplevel_funcs),
                    "toplevel_coverage_abs": toplevel_coverage,
                    "toplevel_coverage_relative": toplevel_coverage / main_time,
                    "hotspot_coverage_relative": 1 - coverages["hotspot_coverage_abs"] / main_time,
                }
            )
            # Set the functions as unfiltered again
            for func in filtered:
                self.call_graph[func]["filtered"] = False

    def _collected_points_metric(self):
        """Helper function for calculating the actually reached instrumentation points."""
        if self.call_graph is None:
            return
        collected_func = set(self.call_graph.cg_map.keys()) & set(
            self.dynamic_stats.global_stats.keys()
        )
        diff_funcs = {
            func_name
            for func_name, func_config in self.call_graph.cg_map.items()
            if func_config["diff"]
        }
        metrics.add_metric("diff_funcs", list(diff_funcs))
        metrics.add_metric("collected_func_cg_compare", len(collected_func))

    def _call_graph_level_assumption(self):
        """Check how well the call graph / measured data fulfill the assumption about the
        call count.
        """
        # Detailed statistics about the assumption violations (less than X% difference, etc.)
        violations_stats = {
            "<5%": {"check": lambda count_diff: count_diff < 5, "count": 0},
            "<10%": {"check": lambda count_diff: count_diff < 10, "count": 0},
            "<50%": {"check": lambda count_diff: count_diff < 50, "count": 0},
            ">=50%": {"check": lambda count_diff: count_diff >= 50, "count": 0},
            "1": {
                "check": lambda count_diff: count_diff == SPECIAL_CALL_COUNT,
                "count": 0,
            },
        }
        total_violations, total_confirmations = 0, 0

        # Analyze the functions according to the call graph levels
        for level in self.call_graph.levels:
            # For each function, we check how many callees have larger call count than the
            # function and if not, we measure by how much the call count differs
            for func in level:
                callees = [
                    c
                    for c in self.call_graph[func]["callees"]
                    if c not in self.call_graph.backedges[func]
                ]
                violations, confirmations = self._check_assumption(violations_stats, func, callees)
                total_violations += violations
                total_confirmations += confirmations
        # Transform the violations statistics into percents
        for key, value in violations_stats.items():
            try:
                violations_stats[key] = (value["count"] / total_violations) * 100
            except ZeroDivisionError:
                violations_stats[key] = 0

        # Save the results into metrics
        total = total_violations + total_confirmations
        assumption = {
            "total_violations": total_violations,
            "total_confirmations": total_confirmations,
            "violations_stats": violations_stats,
        }
        try:
            assumption["violations_ratio"] = (total_violations / total) * 100
            assumption["confirmations_ratio"] = (total_confirmations / total) * 100
        except ZeroDivisionError:
            assumption["violations_ratio"] = 0
            assumption["confirmations_ratio"] = 0
        metrics.add_metric("cg_assumption_check", assumption)

    def _check_assumption(self, violations_stats, parent, callees):
        """Check that the assumption holds for specific function and its callees.

        :param violations_stats: the statistics about assumption violations
        :param parent: name of the tested function
        :param callees: the function callees
        :return: the number of assumption violations and confirmations
        """
        dyn_stats = self.dynamic_stats.global_stats
        func_violations, func_confirmations = 0, 0
        func_count = dyn_stats.get(parent, {"count": 0})["count"]
        callee_counts = [dyn_stats.get(c, {"count": 0})["count"] for c in callees]
        for count in callee_counts:
            if 0 < count < func_count:
                func_violations += 1
                self._assumption_violated(violations_stats, func_count, count)
            elif 0 < count >= func_count > 0:
                func_confirmations += 1
        return func_violations, func_confirmations

    @staticmethod
    def _assumption_violated(violations_stats, parent_count, callee_count):
        """Update the violation statistics when assumption violation happens.

        :param violations_stats: the statistics about assumption violations
        :param parent_count: the number of parent function calls
        :param callee_count: the number of callee function calls
        """
        call_count_diff = (1 - (callee_count / parent_count)) * 100
        if callee_count == 1:
            call_count_diff = SPECIAL_CALL_COUNT
        for violations in violations_stats.values():
            if violations["check"](call_count_diff):
                violations["count"] += 1


# Create the Optimization object so that all the affected modules can use it
# TODO: do we really need to have this as a global? Think about making it local in runner
Optimization = CollectOptimization()


def optimize(runner_type, runner_phase, **collect_params):
    """Define new runner step that is being run in between the typical collector steps:
    before, collect, after, teardown.

    :param runner_type: string name of the runner (the run function is derived from this)
    :param runner_phase: name of the phase/function that is run
    :param collect_params: the data collection parameters that should contain the Configuration
    """
    if runner_type == "postprocessor" or "config" not in collect_params:
        return

    Optimization.build_pipeline(collect_params["config"])
    if not Optimization.pipeline:
        return

    if runner_phase == "before":
        Optimization.pre_optimize_pipeline(**collect_params)
        Optimization.run_optimize_pipeline(**collect_params)
    elif runner_phase == "after":
        Optimization.post_optimize_pipeline(**collect_params)


def build_stats_names(config, cg_type=CallGraphTypes.STATIC):
    """Build names of call graph and dynamic stats files.

    The CG stats name is built using the main binary and possible libraries with no emphasis on
    arguments or workloads - the CG structure stays the same regardless of runtime arguments.

    Dynamic Stats name is built using both binaries and arguments, since stats can differ based
    on the supplied parameters.

    :param config: the Configuration object
    :param cg_type: Call Graph type

    :return: CG stats name, Dynamic Stats name
    """
    binaries = sanitize_filepart("--".join([config.binary] + sorted(config.libs))).replace(".", "_")
    binaries_param = sanitize_filepart(
        "--".join([arg for arg in [config.executable.workload] if arg])
    ).replace(".", "_")
    cg_prefix = "cg"
    if cg_type == CallGraphTypes.DYNAMIC:
        cg_prefix = "dcg"
    elif cg_type == CallGraphTypes.MIXED:
        cg_prefix = "mcg"
    return f"{cg_prefix}--{binaries}", "ds--" + "--".join([binaries, binaries_param])
