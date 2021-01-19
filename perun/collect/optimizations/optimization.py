""" The new Perun architecture extension that handles the optimization routine.
"""

import collections

from perun.profile.helpers import sanitize_filepart
from perun.utils.helpers import SuppressedExceptions
from perun.collect.optimizations.structs import Optimizations, Pipeline, Parameters, \
    CallGraphTypes, ParametersManager, CGShapingMode
import perun.collect.optimizations.resources.manager as resources
from perun.collect.optimizations.call_graph import CallGraphResource
import perun.collect.optimizations.cg_shaping as shaping
import perun.collect.optimizations.cg_projection as proj
import perun.collect.optimizations.dynamic_baseline as dbase
import perun.collect.optimizations.static_baseline as sbase
import perun.collect.optimizations.diff_tracing as diff
import perun.collect.optimizations.dynamic_sampling as sampling
from perun.collect.optimizations.dynamic_stats import DynamicStats
import perun.utils.metrics as metrics


SPECIAL_CALL_COUNT = 101


# TODO: classify (metrics) functions as private / public
class CollectOptimization:
    """ A class that stores the optimization context and implements the core of the
    optimization architecture.

    :ivar Pipeline selected_pipeline: the active pipeline selected by the user
    :ivar list pipeline: the resulting set of optimization methods created from combining the
                         specified pipeline, enabled and disabled methods
    :ivar ParametersManager params: the collection of optimization parameters
    :ivar bool resource_cache: specifies whether the optimization should use cache or not
    :ivar bool reset_cache: specifies whether new resources should be extracted and computed for
                            the current project version
    :ivar CallGraphResource call_graph: and CFG structures of the current project version
    :ivar CallGraphResource call_graph_old: CG and CFG structures of the previously profiled version
    :ivar DynamicStats dynamic_stats: the Dynamic Stats resource, if available
    """
    # The classification of methods to their respective optimization phases
    __pre = {
        Optimizations.DiffTracing, Optimizations.CallGraphShaping, Optimizations.BaselineStatic,
        Optimizations.BaselineDynamic, Optimizations.DynamicSampling, Optimizations.TimedSampling
    }
    __run = {
        Optimizations.DynamicProbing, Optimizations.TimedSampling
    }
    __post = {
        Optimizations.BaselineDynamic, Optimizations.DynamicSampling
    }

    def __init__(self):
        """ Construct and initialize the instance
        """
        self.selected_pipeline = Pipeline(Pipeline.default())
        self.pipeline = []
        self._optimizations_on = []
        self._optimizations_off = []
        self.params = ParametersManager()

        self.cg_stats_name = None
        self.dynamic_stats_name = None
        self.resource_cache = True
        self.reset_cache = False
        self.call_graph_type = CallGraphTypes.Static
        self.call_graph = None
        self.call_graph_old = None
        self.dynamic_stats = DynamicStats()

    def set_pipeline(self, pipeline_name):
        """ Set the used Pipeline.

        :param str pipeline_name: name of the user-specified pipeline
        """
        self.selected_pipeline = Pipeline(pipeline_name)

    def enable_optimization(self, optimization_name):
        """ Enable certain optimization technique.

        :param str optimization_name: name of the optimization method
        """
        self._optimizations_on.append(Optimizations(optimization_name))

    def disable_optimization(self, optimization_name):
        """ Disable certain optimization technique.

        :param str optimization_name: name of the optimization method
        """
        self._optimizations_off.append(Optimizations(optimization_name))

    def get_pre_optimizations(self):
        """ Create the set intersection of created pipeline and pre-optimize methods

        :return set: the resulting set of optimization methods to run
        """
        return set(self.pipeline) & self.__pre

    def get_run_optimizations(self):
        """ Create the set intersection of created pipeline and run-optimize methods

        :return set: the resulting set of optimization methods to run
        """
        return set(self.pipeline) & self.__run

    def get_post_optimizations(self):
        """ Create the set intersection of created pipeline and post-optimize methods

        :return set: the resulting set of optimization methods to run
        """
        return set(self.pipeline) & self.__post

    def build_pipeline(self, config):
        """ Build the pipeline of actually enabled optimization methods from combining the
        selected pipeline, enabled and disabled optimizations.

        :param Configuration config: the collection configuration object
        """
        if self.pipeline:
            return
        self.pipeline = self.selected_pipeline.map_to_optimizations()

        on = set(self._optimizations_on)
        off = set(self._optimizations_off)

        for optimization in on - off:
            self.pipeline.append(optimization)

        for optimization in off - on:
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
        """ Extract, load and store resources necessary for the given pipeline.

        :param Configuration config: the collection configuration object
        """
        # TODO: temporary hack
        old_cg_version = None
        for param_name, param_value in self.params.cli_params:
            if param_name == Parameters.DiffVersion:
                old_cg_version = param_value

        metrics.start_timer('optimization_resources')
        all_funcs = config.get_functions()
        self.cg_stats_name, self.dynamic_stats_name = build_stats_names(config)
        # cg_stats_name = config.get_stats_name('call_graph')
        if self.get_pre_optimizations() or config.cg_extraction:
            # Extract call graph of the profiled binary
            if self.call_graph_type == CallGraphTypes.Dynamic:
                self.cg_stats_name = 'd' + self.cg_stats_name
            elif self.call_graph_type == CallGraphTypes.Mixed:
                self.cg_stats_name = 'm' + self.cg_stats_name
            _cg = resources.extract(
                resources.Resources.CallGraphAngr, stats_name=self.cg_stats_name,
                binary=config.get_target(), libs=config.libs,
                cache=self.resource_cache and not self.reset_cache,
            )
            # Based on the cache we might have obtained the cached call graph or extracted a new one
            if 'minor_version' in _cg:
                self.call_graph = CallGraphResource().from_dict(_cg)
            else:
                self.call_graph = CallGraphResource().from_angr(_cg, all_funcs.keys())

            # Save the extracted call graph before it is modified by the optimization methods
            resources.store(
                resources.Resources.PerunCallGraph, stats_name=self.cg_stats_name,
                call_graph=self.call_graph, cache=self.resource_cache and not self.reset_cache
            )
            # TODO: temporary
            if config.cg_extraction:
                raise NotImplementedError('CG extracted OK')

            # Get call graph of the same binary but from the previous project version (if it exists)
            call_graph_old = resources.extract(
                resources.Resources.PerunCallGraph,
                stats_name=self.cg_stats_name, exclude_self=True,
                vcs_version=old_cg_version
            )
            if call_graph_old:
                self.call_graph_old = CallGraphResource().from_dict(call_graph_old)
        # Get dynamic stats from previous profiling, if there was any
        self.dynamic_stats = resources.extract(
            resources.Resources.PerunStats, stats_name=self.dynamic_stats_name,
            reset_cache=self.reset_cache
        )
        metrics.end_timer('optimization_resources')

    def pre_optimize_pipeline(self, config, **_):
        """ Run the pre-optimize methods in the defined order.

        :param Configuration config: the collection configuration object
        """
        optimizations = self.get_pre_optimizations()
        # No optimizations enabled
        if not optimizations:
            return

        metrics.start_timer('pre-optimize')
        # perform the diff tracing
        if Optimizations.DiffTracing in optimizations:
            diff.diff_tracing(
                self.call_graph, self.call_graph_old,
                self.params[Parameters.DiffKeepLeaf],
                self.params[Parameters.DiffInspectAll],
                self.params[Parameters.DiffCfgMode]
            )

        # Perform the call graph shaping
        if Optimizations.CallGraphShaping in optimizations:
            mode = self.params[Parameters.CGShapingMode]
            if mode == CGShapingMode.Match:
                # The match mode simply uses the call graph functions
                pass
            elif mode in [CGShapingMode.Strict, CGShapingMode.Soft]:
                shaping.call_graph_trimming(
                    self.call_graph,
                    self.params[Parameters.CGTrimLevels],
                    self.params[Parameters.CGTrimMinFunctions],
                    self.params[Parameters.CGTrimKeepLeaf]
                )
            elif mode == CGShapingMode.Prune:
                shaping.call_graph_pruning(
                    self.call_graph,
                    self.params[Parameters.CGPruneChainLength],
                    self.params[Parameters.CGPruneKeepTop]
                )
            elif mode == CGShapingMode.Bottom_up:
                proj.cg_bottom_up(
                    self.call_graph,
                    self.params[Parameters.CGProjLevels]
                )
            elif mode == CGShapingMode.Top_down:
                proj.cg_top_down(
                    self.call_graph,
                    self.params[Parameters.CGProjLevels],
                    self.params[Parameters.CGProjKeepLeaf]
                )

        # Perform the static baseline
        if Optimizations.BaselineStatic in optimizations:
            sbase.complexity_filter(
                self.call_graph,
                self.params[Parameters.SourceFiles],
                self.params[Parameters.StaticComplexity],
                self.params[Parameters.StaticKeepTop]
            )

        checks = [
            (dbase.call_limit_filter, self.params[Parameters.DynBaseHardThreshold]),
            (dbase.constant_filter, self.params[Parameters.DynBaseSoftThreshold]),
            (dbase.wrapper_filter, 0),
        ]
        if Optimizations.BaselineDynamic in optimizations:
            dbase.filter_functions(self.call_graph, self.dynamic_stats.global_stats, checks)
        if Optimizations.DynamicSampling in optimizations:
            sampling.set_sampling(
                self.call_graph, self.dynamic_stats.global_stats,
                self.params[Parameters.DynSampleStep],
                self.params[Parameters.DynSampleThreshold]
            )

        # Extract the remaining functions from the call graph - these should be probed
        diff_solo = len(optimizations) == 1 and Optimizations.DiffTracing in optimizations
        # If only diff tracing is on, probe only the changed functions
        remaining_func = self.call_graph.get_functions(diff_only=diff_solo)
        config.prune_functions(remaining_func)
        metrics.end_timer('pre-optimize')
        metrics.add_metric('funcs', list(remaining_func.keys()))

    def run_optimize_pipeline(self, config, **_):
        """ The "run" pipeline cannot properly run the run-phase optimizations since the
        implementation details are up to each specific engine. Instead, we set the
        requested optimizations and their parameters in the Configuration object.

        :param Configuration config: the collection configuration object
        """
        # Create a dictionary of parameters and values, they need to be serializable
        run_optimization_parameters = {
            Parameters.TimedSampleFreq.value:
                self.params[Parameters.TimedSampleFreq],
            Parameters.ProbingReattach.value:
                self.params[Parameters.ProbingReattach],
            Parameters.ProbingThreshold.value:
                self.params[Parameters.ProbingThreshold]
        }
        # Set the optimization methods and their parameters
        config.set_run_optimization(
            [opt.value for opt in self.get_run_optimizations()], run_optimization_parameters
        )

    def post_optimize_pipeline(self, config, **_):
        """ Run the post-optimize methods in the defined order.

        :param Configuration config: the collection configuration object
        """
        # Get the set of post-optimize methods
        optimizations = self.get_post_optimizations()
        if optimizations or metrics.is_enabled():
            metrics.start_timer('post-optimize')
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
                resources.Resources.PerunStats,
                stats_name=self.dynamic_stats_name,
                dynamic_stats=self.dynamic_stats
            )
            metrics.end_timer('post-optimize')

    def _level_i_metric(self):
        """ Helper function for computing Level_i metrics, such as callee / caller exclusive times.
        """
        lvl_coverage = {}
        for tid, funcs in self.dynamic_stats.per_thread.items():
            lvl_coverage[tid] = {}
            for lvl, lvl_funcs in enumerate(self.call_graph.levels):
                # Ignore levels that were filtered
                if all(self.call_graph[func]['filtered'] for func in lvl_funcs):
                    continue
                immediate_callers = {
                    c for func in lvl_funcs for c in self.call_graph[func]['callers']
                }
                immediate_callees = {
                    c for func in lvl_funcs for c in self.call_graph[func]['callees']
                }
                lvl_coverage[tid][lvl] = {
                    'caller_exc': sum(funcs.get(c, {'total_exclusive': 0})['total_exclusive']
                                      for c in immediate_callers),
                    'callee_exc': sum(funcs.get(c, {'total_exclusive': 0})['total_exclusive']
                                      for c in immediate_callees)
                }
        metrics.add_metric('level_coverage', lvl_coverage)

    def _level_time_metric(self):
        """ Helper function for computing level time metrics, such as Call Graph level exclusive
        time and its breakdown into specific functions within the level.
        """
        level_time = collections.defaultdict(lambda: collections.defaultdict(int))
        exclusive_level_time = collections.defaultdict(lambda: collections.defaultdict(int))
        level_funcs = collections.defaultdict(lambda: collections.defaultdict(list))

        max_calls = (None, 0, 0)
        for tid, funcs in self.dynamic_stats.per_thread.items():
            for func_name, func_stats in funcs.items():
                func_cg_level = self.call_graph[func_name]['level']
                level_time[tid][func_cg_level] += func_stats['total']
                exclusive_level_time[tid][func_cg_level] += func_stats['total_exclusive']
                level_funcs[tid][func_cg_level].append(
                    (func_name, func_stats['total_exclusive'], func_stats['sampled_count'],
                     func_stats['sample'])
                )
                if func_stats['sampled_count'] > max_calls[1]:
                    max_calls = (func_name, func_stats['sampled_count'], func_cg_level)
        max_bu_length = proj._cg_bottom_sets(self.call_graph)[1]
        metrics.add_metric('cg_level_times_exclusive', exclusive_level_time)
        metrics.add_metric('cg_level_funcs', level_funcs)
        metrics.add_metric('max_calls', max_calls)
        metrics.add_metric('max_bu_length', max_bu_length)

    def _coverage_metric(self):
        """ Helper function for computing the coverage metrics. Coverage metrics are
        computed for each thread separately - however, for single-threaded applications,
        the threads effectively represent processes.
        """
        if self.call_graph is None:
            return

        threads = self.dynamic_stats.threads
        metrics.add_metric("process_hierarchy", self.dynamic_stats.process_hierarchy)

        # A) Obtain the absolute hotspot coverage as extracted directly from the trace
        coverages_metrics = metrics.read_metric('coverages')

        for tid, coverages in coverages_metrics.items():
            if tid not in threads:
                continue

            tid_stats = self.dynamic_stats.per_thread[tid]
            # The total running time of a thread is a) duration of main, or b) the whole thread
            if 'main' in tid_stats:
                main_time = tid_stats['main']['total']
            else:
                main_time = threads[tid].duration
            # B) Compute the top-level and min coverages using the CG structure
            # Identify functions that have not been measured by the process / thread
            excluded = set(self.call_graph.cg_map.keys()) - set(tid_stats.keys())
            for func, f_stats in tid_stats.items():
                # Exclude functions that are recursive or exceed the total running time of main
                if func in self.call_graph.recursive or f_stats['total'] > main_time:
                    excluded.add(func)
            # Set them as filtered but remember them, we need to set them back later
            filtered = set()
            for func in excluded:
                if not self.call_graph[func]['filtered']:
                    filtered.add(func)
                self.call_graph[func]['filtered'] = True
            min_coverage_funcs = self.call_graph.compute_bottom()
            toplevel_funcs = self.call_graph.compute_top()
            # Compute the coverage
            min_coverage = sum(tid_stats[f]['total'] for f in min_coverage_funcs)
            toplevel_coverage = sum(tid_stats[f]['total'] for f in toplevel_funcs)
            # Update the coverage
            coverages.update({
                'main': main_time,
                'min_coverage_count': len(min_coverage_funcs),
                'min_coverage_abs': min_coverage,
                'min_coverage_relative': 1 - min_coverage / main_time,
                'toplevel_coverage_count': len(toplevel_funcs),
                'toplevel_coverage_abs': toplevel_coverage,
                'toplevel_coverage_relative': toplevel_coverage / main_time,
                'hotspot_coverage_relative': 1 - coverages['hotspot_coverage_abs'] / main_time
            })
            # Set the functions as unfiltered again
            for func in filtered:
                self.call_graph[func]['filtered'] = False

    def _collected_points_metric(self):
        """ Helper function for calculating the actually reached instrumentation points.
        """
        if self.call_graph is None:
            return
        collected_func = (set(self.call_graph.cg_map.keys()) &
                          set(self.dynamic_stats.global_stats.keys()))
        metrics.add_metric('collected_func_cg_compare', len(collected_func))

    def _call_graph_level_assumption(self):
        """ Check how well the call graph / measured data fulfill the assumption about the
        call count.
        """
        # Detailed statistics about the assumption violations (less than X% difference, etc.)
        violations_stats = {
            '<5%': {'check': lambda count_diff: count_diff < 5, 'count': 0},
            '<10%': {'check': lambda count_diff: count_diff < 10, 'count': 0},
            '<50%': {'check': lambda count_diff: count_diff < 50, 'count': 0},
            '>=50%': {'check': lambda count_diff: count_diff >= 50, 'count': 0},
            '1': {'check': lambda count_diff: count_diff == SPECIAL_CALL_COUNT, 'count': 0},
        }
        total_violations, total_confirmations = 0, 0

        # Analyze the functions according to the call graph levels
        for depth, level in enumerate(self.call_graph.levels):
            # For each function, we check how many callees have larger call count than the
            # function and if not, we measure by how much the call count differs
            for func in level:
                callees = [
                    c for c in self.call_graph[func]['callees']
                    if c not in self.call_graph.backedges[func]
                ]
                v, c = self._check_assumption(violations_stats, func, callees)
                total_violations += v
                total_confirmations += c
        # Transform the violations statistics into percents
        for key, value in violations_stats.items():
            try:
                violations_stats[key] = (value['count'] / total_violations) * 100
            except ZeroDivisionError:
                violations_stats[key] = 0

        # Save the results into metrics
        total = total_violations + total_confirmations
        assumption = {
            'total_violations': total_violations,
            'total_confirmations': total_confirmations,
            'violations_stats': violations_stats
        }
        try:
            assumption['violations_ratio'] = (total_violations / total) * 100
            assumption['confirmations_ratio'] = (total_confirmations / total) * 100
        except ZeroDivisionError:
            assumption['violations_ratio'] = 0
            assumption['confirmations_ratio'] = 0
        metrics.add_metric('cg_assumption_check', assumption)

    def _check_assumption(self, violations_stats, parent, callees):
        """ Check that the assumption holds for specific function and its callees.

        :param dict violations_stats: the statistics about assumption violations
        :param str parent: name of the tested function
        :param list callees: the function callees
        :return tuple (int, int): the number of assumption violations and confirmations
        """
        dyn_stats = self.dynamic_stats.global_stats
        func_violations, func_confirmations = 0, 0
        func_count = dyn_stats.get(parent, {'count': 0})['count']
        callee_counts = [(c, dyn_stats.get(c, {'count': 0})['count']) for c in callees]
        for callee, count in callee_counts:
            if 0 < count < func_count:
                func_violations += 1
                self._assumption_violated(violations_stats, func_count, count)
            elif 0 < count >= func_count > 0:
                func_confirmations += 1
        return func_violations, func_confirmations

    @staticmethod
    def _assumption_violated(violations_stats, parent_count, callee_count):
        """ Update the violation statistics when assumption violation happens.

        :param dict violations_stats: the statistics about assumption violations
        :param int parent_count: the number of parent function calls
        :param int callee_count: the number of callee function calls
        """
        call_count_diff = (1 - (callee_count / parent_count)) * 100
        if callee_count == 1:
            call_count_diff = SPECIAL_CALL_COUNT
        for violations in violations_stats.values():
            if violations['check'](call_count_diff):
                violations['count'] += 1


# Create the Optimization object so that all the affected modules can use it
# TODO: do we really need to have this as a global? Think about making it local in runner
Optimization = CollectOptimization()


def optimize(runner_type, runner_phase, **collect_params):
    """ Define new runner step that is being run in between the typical collector steps:
    before, collect, after, teardown.

    :param str runner_type: string name of the runner (the run function is derived from this)
    :param str runner_phase: name of the phase/function that is run
    :param collect_params: the data collection parameters that should contain the Configuration
    """
    if runner_type == 'postprocessor' or 'config' not in collect_params:
        return

    Optimization.build_pipeline(collect_params['config'])
    if not Optimization.pipeline:
        return

    if runner_phase == 'before':
        Optimization.pre_optimize_pipeline(**collect_params)
        Optimization.run_optimize_pipeline(**collect_params)
    elif runner_phase == 'after':
        Optimization.post_optimize_pipeline(**collect_params)


def build_stats_names(config):
    """ Build names of call graph and dynamic stats files.

    The CG stats name is built using the main binary and possible libraries with no emphasis on
    arguments or workloads - the CG structure stays the same regardless of runtime arguments.

    Dynamic Stats name is built using both binaries and arguments, since stats can differ based
    on the supplied parameters.

    :param Configuration config: the Configuration object

    :return tuple (str, str): CG stats name, Dynamic Stats name
    """
    binaries = sanitize_filepart('--'.join([config.binary] + sorted(config.libs))).replace('.', '_')
    binaries_param = sanitize_filepart(
        '--'.join([arg for arg in [config.executable.args, config.executable.workload] if arg])
    ).replace('.', '_')
    return 'cg--{}'.format(binaries), 'ds--' + '--'.join([binaries, binaries_param])
