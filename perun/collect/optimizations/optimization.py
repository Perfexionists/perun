""" The new Perun architecture extension that handles the optimization routine.
"""


from perun.utils.helpers import SuppressedExceptions
from perun.collect.optimizations.structs import Optimizations, Pipeline, Parameters, \
    ParametersManager, CGShapingMode
import perun.collect.optimizations.resources.manager as resources
from perun.collect.optimizations.call_graph import CallGraphResource
import perun.collect.optimizations.cg_shaping as shaping
import perun.collect.optimizations.dynamic_baseline as dbase
import perun.collect.optimizations.static_baseline as sbase
import perun.collect.optimizations.diff_tracing as diff
import perun.collect.optimizations.dynamic_sampling as sampling
import perun.collect.optimizations.gather as gather
import perun.utils.metrics as metrics


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
    :ivar CallGraphResource call_graph: the CG and CFG structures of the current project version
    :ivar CallGraphResource call_graph_old: CG and CFG structures of the previously profiled version
    :ivar dict dynamic_stats: the Dynamic Stats resource, if available
    """
    # The classification of methods to their respective optimization phases
    __pre = {
        Optimizations.DiffTracing, Optimizations.CallGraphShaping, Optimizations.BaselineStatic,
        Optimizations.BaselineDynamic, Optimizations.DynamicSampling
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

        self.resource_cache = True
        self.reset_cache = False
        self.call_graph = None
        self.call_graph_old = None
        self.dynamic_stats = {}

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
        if not self.pipeline:
            return

        # Otherwise prepare the necessary resources
        self.load_resources(config)

        # Infer the optimization parameters
        self.params.infer_params(self.call_graph, self.selected_pipeline, config.get_target())

    def load_resources(self, config):
        """ Extract, load and store resources necessary for the given pipeline.

        :param Configuration config: the collection configuration object
        """
        metrics.start_timer('optimization_resources')
        all_funcs = config.get_functions()
        cg_stats_name = config.get_stats_name('call_graph')
        if self.get_pre_optimizations():
            # Extract call graph of the profiled binary
            _cg = resources.extract(
                resources.Resources.CallGraphAngr, stats_name=cg_stats_name,
                binary=config.get_target(), cache=self.resource_cache and not self.reset_cache
            )
            # Based on the cache we might have obtained the cached call graph or extracted a new one
            if 'minor_version' in _cg:
                self.call_graph = CallGraphResource().from_dict(_cg)
            else:
                self.call_graph = CallGraphResource().from_angr(_cg, all_funcs.keys())

            # Save the extracted call graph before it is modified by the optimization methods
            resources.store(
                resources.Resources.PerunCallGraph, stats_name=cg_stats_name,
                call_graph=self.call_graph, cache=self.resource_cache and not self.reset_cache
            )

            # Get call graph of the same binary but from the previous project version (if it exists)
            call_graph_old = resources.extract(
                resources.Resources.PerunCallGraph, stats_name=cg_stats_name
            )
            if call_graph_old:
                self.call_graph_old = CallGraphResource().from_dict(call_graph_old)
        # Get dynamic stats from previous profiling, if there was any
        self.dynamic_stats = resources.extract(
            resources.Resources.PerunStats, stats_name=config.get_stats_name('dynbase'),
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
            else:
                shaping.call_graph_pruning(
                    self.call_graph,
                    self.params[Parameters.CGPruneChainLength],
                    self.params[Parameters.CGPruneKeepTop]
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
            dbase.filter_functions(self.call_graph, self.dynamic_stats, checks)
        if Optimizations.DynamicSampling in optimizations:
            sampling.set_sampling(
                self.call_graph, self.dynamic_stats,
                self.params[Parameters.DynSampleStep],
                self.params[Parameters.DynSampleThreshold]
            )

        # Extract the remaining functions from the call graph - these should be probed
        diff_solo = len(optimizations) == 1 and Optimizations.DiffTracing in optimizations
        # If only diff tracing is on, probe only the changed functions
        remaining_func = self.call_graph.get_functions(diff_only=diff_solo)
        config.prune_functions(remaining_func)
        metrics.end_timer('pre-optimize')

    def post_optimize_pipeline(self, profile, config, **_):
        """ Run the post-optimize methods in the defined order.

        :param Profile profile: the Perun profile generated during the profiling
        :param Configuration config: the collection configuration object
        """
        # Get the set of post-optimize methods
        optimizations = self.get_post_optimizations()
        if optimizations or metrics.is_enabled():
            metrics.start_timer('post-optimize')
            # Create the dynamic stats from the profile, if necessary
            dyn_stats = gather.gather_stats(profile, config)
            # TODO: metric only
            self.coverage_metric(dyn_stats)
            self.collected_points_metric(dyn_stats)
            if optimizations:
                # Store the gathered Dynamic Stats
                self.dynamic_stats.update(dyn_stats)
                resources.store(
                    resources.Resources.PerunStats, stats_name=config.get_stats_name('dynbase'),
                    stats_map=self.dynamic_stats
                )
            metrics.end_timer('post-optimize')

    def coverage_metric(self, dyn_stats):
        """ Helper function for computing the coverage metrics.

        :param dict dyn_stats: the Dynamic Stats resource
        """
        if self.call_graph is None:
            return
        # Find the minimum coverage functions
        main_time = dyn_stats['main']['total']
        min_coverage_funcs = set(
            func for func in dyn_stats.keys() if
            dyn_stats[func]['total'] <= main_time and
            not any(self.call_graph.subsumption(func, cmp_func)
                    for cmp_func in dyn_stats.keys()))
        min_coverage_funcs_alt = min_coverage_funcs - self.call_graph.recursive

        # Find the maximum cut and the corresponding excluded functions
        excluded, _ = self.call_graph.coverage_max_cut()
        # print('excluded: {}'.format(excluded))
        tested_funcs = [func for func in dyn_stats.keys() if func not in excluded]
        # Find the maximum coverage functions
        max_coverage_funcs = set(
            func for func in tested_funcs if
            not any(self.call_graph.subsumption(cmp_func, func)
                    for cmp_func in tested_funcs))
        if not max_coverage_funcs:
            max_coverage_funcs = ['main']

        avg_min_level = sum(
            self.call_graph[func]['level'] for func in min_coverage_funcs) / len(min_coverage_funcs)
        avg_max_level = sum(
            self.call_graph[func]['level'] for func in max_coverage_funcs) / len(max_coverage_funcs)
        # Compute the coverage
        min_coverage = sum(dyn_stats[f]['total'] for f in min_coverage_funcs)
        min_coverage_alt = sum(dyn_stats[f]['total'] for f in min_coverage_funcs_alt)

        # for f in min_coverage_funcs:
        #     print('{}: {}, {}'.format(f, dyn_stats[f]['total'], dyn_stats[f]['count']))
        max_coverage = sum(dyn_stats[f]['total'] for f in max_coverage_funcs)

        metrics.add_metric('min_coverage_count', len(min_coverage_funcs))
        metrics.add_metric('min_coverage_alt_count', len(min_coverage_funcs_alt))
        metrics.add_metric('max_coverage_count', len(max_coverage_funcs))
        metrics.add_metric('min_coverage_avg_lvl', avg_min_level)
        metrics.add_metric('max_coverage_avg_lvl', avg_max_level)
        metrics.add_metric('main', dyn_stats['main']['total'])
        metrics.add_metric('min_coverage_abs', min_coverage)
        metrics.add_metric('max_coverage_abs', max_coverage)
        metrics.add_metric('min_coverage_relative', min_coverage / dyn_stats['main']['total'])
        metrics.add_metric('min_coverage_alt_relative', min_coverage_alt / dyn_stats['main']['total'])
        metrics.add_metric('max_coverage_relative', max_coverage / dyn_stats['main']['total'])

    def collected_points_metric(self, dyn_stats):
        """ Helper function for calculating the actually reached instrumentation points.

        :param dict dyn_stats: the Dynamic Stats resource
        """
        if self.call_graph is None:
            return
        collected_func = set(self.call_graph.cg_map.keys()) & set(dyn_stats.keys())
        metrics.add_metric('collected_func_cg_compare', len(collected_func))


# Create the Optimization object so that all the affected modules can use it
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
    elif runner_phase == 'after':
        Optimization.post_optimize_pipeline(**collect_params)
