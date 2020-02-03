"""Collection of helpers structures for fuzzing"""

import os
from collections import namedtuple

__author__ = 'Tomas Fiedor'


TimeSeries = namedtuple("TimeSeries", "x_axis y_axis")
RuleSet = namedtuple("RuleSet", "rules hits")


class Mutation:
    """
    :ivar str path: path to the workload
    :ivar list history: list of predecessors
    :ivar Mutation predecessor: predecessor of the mutation (form which we mutated)
    :ivar int cov: achieved coverage
    :ivar int deg_ratio: achieved degradation ration
    :ivar float fitness: fitness of the mutation
    """
    def __init__(self, path, history, predecessor, cov=0, deg_ratio=0, fitness=0):
        """
        :param str path: path to the workload
        :param list history: list of predecessors
        :param Mutation predecessor: predecessor of the mutation (form which we mutated)
        :param int cov: achieved coverage
        :param int deg_ratio: achieved degradation ration
        :param float fitness: fitness of the mutation
        """
        self.path = path
        self.history = history
        self.predecessor = predecessor
        self.cov = cov
        self.deg_ratio = deg_ratio
        self.fitness = fitness


class CoverageConfiguration:
    """Configuration of the coverage testing

    :ivar str gcno_path: path to the directory, where .gcno files are stored
    :ivar str source_path: path to the directory, where source codes are stored
    :ivar int gcov_version: version of the gcov utility
    :ivar list gcov_files: list of gcov files
    :ivar list source_files: list of source files
    """
    def __init__(self, **kwargs):
        """
        :param dict kwargs: set of keyword configurations
        """
        self.gcno_path = kwargs['gcno_path']
        self.source_path = kwargs['source_path']
        self.gcov_version = None
        self.gcov_files = []
        self.source_files = []


class FuzzingConfiguration:
    """Collection of (mostly persistent) configuration of the fuzzing process

    This encapsulates all of the possibly used configurations to be passed around functions, in
    order to reduce the number of local variables and parameters.

    :ivar int timeout: specifies how long the fuzzing should be running
    :ivar int hang_timeout: specifies how long the tested program should run with the mutations
    :ivar str output_dir: directory, where resulting logs, workloads etc. are generated
    :ivar str workloads_filter: regular expression used to filter workloads
    :ivar list regex_rules: list of user defined rules (described by regular expressions
    :ivar int max: maximal size of the generated workloads in B
    :ivar int max_size_ratio: maximal percentual increase in the size of the workloads
    :ivar int max_size_gain: the maximal increase in size of the mutated workload, in comparison
        with input seeds.
    :ivar int exec_limit: limit to number of execution of number of mutation per fuzzing loop
    :ivar int precollect_limit: limit for number of generated mutations per fuzzing loop
    :ivar str mutations_per_rule: strategy used for determining how many workloads will be generated
        per mutation rule.
    :ivar bool no_plotting: specifies if the result of the fuzzing should be plotted by graphs
    :ivar int cov_rate: threshold for the increase of the
    :ivar bool coverage_testing: specifies if the mutations should be tested for coverage also,
        or only using perun
    :ivar CoverageConfiguration coverage
    """
    def __init__(self, **kwargs):
        """
        :param dict kwargs: set of keyword configurations
        """
        self.timeout = kwargs['timeout']
        self.hang_timeout = kwargs['hang_timeout']
        self.output_dir = os.path.abspath(kwargs['output_dir'])
        self.workloads_filter = kwargs['workloads_filter']
        self.regex_rules = kwargs['regex_rules']
        self.max_size = kwargs.get('max', None)
        self.max_size_ratio = kwargs.get("max_size_ratio", None)
        self.max_size_gain = kwargs.get("max_size_gain")
        self.exec_limit = kwargs['exec_limit']
        self.precollect_limit = kwargs["interesting_files_limit"]
        self.mutations_per_rule = kwargs["mutations_per_rule"]
        self.no_plotting = kwargs['no_plotting']
        self.cov_rate = kwargs['coverage_increase_rate']
        self.coverage_testing = (kwargs.get("source_path") and kwargs.get("gcno_path")) is not None
        self.coverage = CoverageConfiguration(**kwargs)


class FuzzingProgress:
    """Collection of statistics and states used during fuzzing

    :ivar list faults: list of workloads leading to faults
    :ivar list hangs: list of workloads leading to hangs
    :ivar list interesting_workloads: list of potentially interesting workloads
    :ivar list parents: list of fitness values for parents
    :ivar list final_results: list of final results
    :ivar int timeout: timeout of the fuzzing
    :ivar dict stats: additional stats of fuzz testing
    """
    def __init__(self):
        """
        :param int timeout: timeout for the fuzzing
        """
        self.faults = []
        self.hangs = []
        self.interesting_workloads = []
        self.parents = []
        self.final_results = []

        # Time series plotting
        self.deg_time_series = TimeSeries([0], [0])
        self.cov_time_series = TimeSeries([0], [1.0])

        self.base_cov = 1

        self.stats = {
            "start_time": 0.0,
            "end_time": 0.0,
            "cov_execs": 0,
            "perun_execs": 0,
            "degradations": 0,
            "max_cov": 1.0,
            "worst_case": None,
            "hangs": 0,
            "faults": 0
        }

    def update_max_coverage(self):
        """Updates the maximal achieved coverage according to the parent fitness values"""
        self.stats["max_cov"] = self.parents[-1].cov / self.base_cov
